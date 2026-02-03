from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class WorkspacePaths:
    """
    Canonical workspace path builder for v1.2+.

    Layout:
      <root>/.aspectnova/archive/<workspace_id>/<run_id>/payload.zip
      <root>/.aspectnova/archive/<workspace_id>/<run_id>/manifest.json
      <root>/.aspectnova/contracts/<workspace_id>/<run_id>/trace_contract.json
    """
    root: Path
    workspace_id: str
    run_id: str

    @property
    def aspectnova_root(self) -> Path:
        return Path(self.root) / ".aspectnova"

    @property
    def archive_dir(self) -> Path:
        return self.aspectnova_root / "archive" / self.workspace_id / self.run_id

    @property
    def contracts_dir(self) -> Path:
        return self.aspectnova_root / "contracts" / self.workspace_id / self.run_id

    @property
    def payload_zip_path(self) -> Path:
        return self.archive_dir / "payload.zip"

    @property
    def manifest_path(self) -> Path:
        return self.archive_dir / "manifest.json"

    @property
    def trace_contract_path(self) -> Path:
        return self.contracts_dir / "trace_contract.json"
