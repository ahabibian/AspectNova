import sys
import json
from pathlib import Path

import yaml

# ---- Contract Root Resolver ----

def get_contract_root() -> Path:
    import os
    env = os.getenv("ASPECTNOVA_CONTRACTS_ROOT")
    if env:
        root = Path(env)
        if root.exists():
            return root

    repo_root = Path(__file__).resolve().parents[2]
    canonical = repo_root / "contracts"

    if canonical.exists():
        return canonical

    legacy = repo_root / "agent" / "contracts"
    return legacy


# ---- Helpers ----

def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_stage_name(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


# ---- Validation Logic ----

def validate_stage_registry(root: Path):

    registry = root / "registry" / "stage_contracts.v2.yml"

    if not registry.exists():
        print(f"[ERROR] Stage registry not found: {registry}")
        return False

    data = load_yaml(registry)

    if "stages" not in data:
        print("[ERROR] 'stages' key missing in registry")
        return False

    seen = set()

    default_base = data.get("defaults", {}).get("base")

    for stage in data["stages"]:
        raw_name = stage.get("id") or stage.get("name") or ""
        name = normalize_stage_name(raw_name)

        if not name:
            print(f"[ERROR] Empty stage identifier in entry: {stage}")
            return False

        if name in seen:
            print(f"[ERROR] Duplicate stage: {name}")
            return False

        seen.add(name)

        stage_base = stage.get("base", default_base)
        if not stage_base:
            print(f"[ERROR] Stage missing base and no default base defined: {name}")
            return False

    print(f"[OK] Stage registry validated ({len(seen)} stages)")
    return True


def validate_schema_set(root: Path):

    schemas_root = root / "schemas"

    if not schemas_root.exists():
        print("[ERROR] schemas root missing")
        return False

    schema_files = list(schemas_root.rglob("*.json"))

    if not schema_files:
        print("[ERROR] no schema files found")
        return False

    ok = True

    for f in schema_files:
        try:
            load_json(f)
        except Exception as e:
            print(f"[ERROR] Invalid JSON schema: {f} -> {e}")
            ok = False

    if ok:
        print(f"[OK] Schemas validated ({len(schema_files)} files)")

    return ok


# ---- Main CLI ----

def main():

    root = get_contract_root()

    print(f"[INFO] Using contract root: {root}")

    ok_registry = validate_stage_registry(root)
    ok_schemas = validate_schema_set(root)

    if ok_registry and ok_schemas:
        print("[SUCCESS] Contract validation passed")
        sys.exit(0)

    print("[FAIL] Contract validation failed")
    sys.exit(2)


if __name__ == "__main__":
    main()