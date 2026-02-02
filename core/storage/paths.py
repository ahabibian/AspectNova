@'
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkspacePaths:
    root: Path
    workspace_id: str
    run_id: str

    @property
    def aspectnova_dir(self) -> Path:
        return self.root / ".aspectnova"

    @property
    def archive_dir(self) -> Path:
        return self.aspectnova_dir / "archive" / self.workspace_id / self.run_id

    @property
    def contracts_dir(self) -> Path:
        return self.aspectnova_dir / "contracts" / self.workspace_id / self.run_id

    @property
    def payload_zip_path(self) -> Path:
        return self.archive_dir / "payload.zip"

    @property
    def manifest_path(self) -> Path:
        return self.archive_dir / "manifest.json"

    @property
    def trace_contract_path(self) -> Path:
        return self.contracts_dir / "trace_contract.json"
'@ | Set-Content -Encoding UTF8 core\storage\paths.py
