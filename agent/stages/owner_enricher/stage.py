from pathlib import Path
from ..stage_base import Stage
from .enrich_owner import enrich
import json


class OwnerEnricherStage(Stage):
    name = "owner_enricher"
    version = "1.1.0"

    def run(self, input_path: Path, output_dir: Path, run_id: str):
        scan_v1 = Path("runs") / run_id / "output" / "scan_result.canonical.v1.json"
        if not scan_v1.exists():
            raise FileNotFoundError(f"missing scan canonical v1: {scan_v1}")

        out_pack = output_dir / "evidence_pack.v1+owner.json"

        stats = enrich(input_path, scan_v1, out_pack, run_id)

        (output_dir / "owner_enricher.stats.json").write_text(
            json.dumps(stats, indent=2),
            encoding="utf-8"
        )
        return stats
