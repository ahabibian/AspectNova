from pathlib import Path
from ..stage_base import Stage
from .builder_scan import build

class EvidenceBuilderStage(Stage):
    name = "evidence_builder"
    version = "1.0.0"

    def run(self, input_path: Path, output_dir: Path, run_id: str):
        return build(input_path, run_id, output_dir)
