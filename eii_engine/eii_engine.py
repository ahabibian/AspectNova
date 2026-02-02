from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


ENGINE_VERSION = "eii-engine-1.0.0"


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class EIIConfig:
    region: str
    energy_per_tb_month_kwh: float          # kWh / TB / month
    co2_g_per_kwh: float                    # grams CO2 per kWh
    electricity_price_sek_per_kwh: float    # SEK per kWh
    reclaimable_fraction_default: float     # 0..1 (v1 simple)
    data_source: str                        # static/user/provider


def parse_config(cfg: Dict[str, Any]) -> EIIConfig:
    # Minimal strict parsing (keep deterministic, fail fast)
    return EIIConfig(
        region=str(cfg["region"]),
        energy_per_tb_month_kwh=float(cfg["energy_per_tb_month_kwh"]),
        co2_g_per_kwh=float(cfg["co2_g_per_kwh"]),
        electricity_price_sek_per_kwh=float(cfg["electricity_price_sek_per_kwh"]),
        reclaimable_fraction_default=float(cfg["reclaimable_fraction_default"]),
        data_source=str(cfg["data_source"]),
    )


def _bytes_to_gb(n: int) -> float:
    return n / (1024 ** 3)


def _bytes_to_tb_decimal(n: int) -> float:
    # For energy baselines it's common to use decimal TB (1e12)
    return n / 1e12


def _ext_of_path(p: str) -> str:
    ext = Path(p).suffix.lower().lstrip(".")
    return ext if ext else "(none)"


def compute_aggregates(scan_result: Dict[str, Any]) -> Tuple[int, int, float, Dict[str, float]]:
    files: List[Dict[str, Any]] = scan_result.get("files", [])
    total_bytes = 0
    by_ext_bytes: Dict[str, int] = {}

    for f in files:
        size = int(f["size"])
        total_bytes += size

        ext = _ext_of_path(str(f["path"]))
        by_ext_bytes[ext] = by_ext_bytes.get(ext, 0) + size

    file_count = len(files)
    total_gb = _bytes_to_gb(total_bytes)

    by_ext_gb = {k: _bytes_to_gb(v) for k, v in by_ext_bytes.items()}
    return file_count, total_bytes, total_gb, by_ext_gb


def compute_energy_monthly(total_bytes: int, cfg: EIIConfig) -> Tuple[float, float, float]:
    storage_tb = _bytes_to_tb_decimal(total_bytes)
    energy_kwh = storage_tb * cfg.energy_per_tb_month_kwh
    co2_kg = energy_kwh * (cfg.co2_g_per_kwh / 1000.0)  # g->kg
    cost_sek = energy_kwh * cfg.electricity_price_sek_per_kwh
    return energy_kwh, co2_kg, cost_sek


def score_eii_v1(total_bytes: int, file_count: int, by_ext_gb: Dict[str, float]) -> Tuple[int, str, List[str]]:
    """
    v1 rule-based score (explainable).
    No access-frequency yet. No ML. Deterministic.
    """
    drivers: List[str] = []

    gb = _bytes_to_gb(total_bytes)

    # Simple scaling: more GB => higher score (worse)
    # You can tune these thresholds later -> engine_version bump; schema stays same.
    if gb < 50:
        base = 15
        drivers.append("Low overall storage footprint")
    elif gb < 200:
        base = 35
        drivers.append("Moderate overall storage footprint")
    elif gb < 800:
        base = 60
        drivers.append("High overall storage footprint")
    else:
        base = 80
        drivers.append("Very high overall storage footprint")

    # Many files adds operational overhead and often waste
    if file_count > 200_000:
        base += 10
        drivers.append("Very high file count")
    elif file_count > 50_000:
        base += 6
        drivers.append("High file count")
    elif file_count > 10_000:
        base += 3
        drivers.append("Moderate file count")

    # Heuristic: temp-like extensions are strong waste indicators (v1)
    temp_exts = ["tmp", "log", "bak", "cache"]
    temp_gb = sum(by_ext_gb.get(e, 0.0) for e in temp_exts)
    if temp_gb >= 20:
        base += 10
        drivers.append("Large volume of temp/log-like files")
    elif temp_gb >= 5:
        base += 5
        drivers.append("Notable temp/log-like files")

    value = max(0, min(100, int(round(base))))

    # Grade mapping (simple, explainable)
    if value <= 20:
        grade = "A"
    elif value <= 40:
        grade = "B"
    elif value <= 65:
        grade = "C"
    elif value <= 85:
        grade = "D"
    else:
        grade = "E"

    # Keep drivers short
    drivers = drivers[:8] if drivers else ["Score derived from size and file-type mix"]
    return value, grade, drivers


def compute_optimization_potential_v1(total_bytes: int, monthly_energy_kwh: float, monthly_co2_kg: float, monthly_cost_sek: float, cfg: EIIConfig) -> Dict[str, float]:
    # v1: single global reclaimable fraction (later v2 uses rules per category)
    reclaimable_bytes = int(total_bytes * cfg.reclaimable_fraction_default)
    reclaimable_gb = _bytes_to_gb(reclaimable_bytes)

    # Assume proportional savings
    annual_energy_saving = (monthly_energy_kwh * 12.0) * cfg.reclaimable_fraction_default
    annual_co2_reduction = (monthly_co2_kg * 12.0) * cfg.reclaimable_fraction_default
    annual_cost_saving = (monthly_cost_sek * 12.0) * cfg.reclaimable_fraction_default

    return {
        "reclaimable_storage_gb": float(reclaimable_gb),
        "energy_saving_kwh_year": float(annual_energy_saving),
        "co2_reduction_kg_year": float(annual_co2_reduction),
        "cost_saving_sek_year": float(annual_cost_saving),
    }


def compute_eii(scan_result: Dict[str, Any], eii_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pure function:
      input: scan_result(v1) + eii_config(v1)
      output: eii_result(v1)
    No filesystem. No UI. No side effects.
    """
    cfg = parse_config(eii_config)

    file_count, total_bytes, total_gb, by_ext_gb = compute_aggregates(scan_result)
    monthly_energy_kwh, monthly_co2_kg, monthly_cost_sek = compute_energy_monthly(total_bytes, cfg)

    annual_energy_kwh = monthly_energy_kwh * 12.0
    annual_co2_kg = monthly_co2_kg * 12.0
    annual_cost_sek = monthly_cost_sek * 12.0

    score_value, score_grade, drivers = score_eii_v1(total_bytes, file_count, by_ext_gb)

    opt = compute_optimization_potential_v1(
        total_bytes=total_bytes,
        monthly_energy_kwh=monthly_energy_kwh,
        monthly_co2_kg=monthly_co2_kg,
        monthly_cost_sek=monthly_cost_sek,
        cfg=cfg,
    )

    # Build result (schema-aligned)
    return {
        "schema_id": "eii-result",
        "schema_version": "v1",
        "generated_at": _utc_now_iso_z(),
        "source_scan": {
            "schema_id": str(scan_result.get("schema_id", "")),
            "schema_version": str(scan_result.get("schema_version", "")),
            "generated_at": str(scan_result.get("generated_at", "")),
            "root": str(scan_result.get("root", "")),
        },
        "engine_version": ENGINE_VERSION,
        "aggregates": {
            "file_count": int(file_count),
            "total_size_bytes": int(total_bytes),
            "total_size_gb": float(total_gb),
            "by_extension_gb": by_ext_gb,
        },
        "energy_impact": {
            "monthly": {
                "energy_kwh": float(monthly_energy_kwh),
                "co2_kg": float(monthly_co2_kg),
                "cost_sek": float(monthly_cost_sek),
            },
            "annual": {
                "energy_kwh": float(annual_energy_kwh),
                "co2_kg": float(annual_co2_kg),
                "cost_sek": float(annual_cost_sek),
            },
        },
        "eii_score": {
            "value": int(score_value),
            "grade": str(score_grade),
            "explanation": {"primary_drivers": drivers},
        },
        "optimization_potential": opt,
        "assumptions": {
            "region": cfg.region,
            "energy_per_tb_month_kwh": cfg.energy_per_tb_month_kwh,
            "co2_g_per_kwh": cfg.co2_g_per_kwh,
            "electricity_price_sek_per_kwh": cfg.electricity_price_sek_per_kwh,
            "reclaimable_fraction_default": cfg.reclaimable_fraction_default,
            "data_source": cfg.data_source,
        },
    }
