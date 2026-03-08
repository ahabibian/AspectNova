from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import stat
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional


DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "runs",
}

DEFAULT_EXCLUDE_SUFFIXES = {
    ".tmp",
    ".log",
}

HASH_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def iso_from_timestamp(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def safe_mime_type(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def compute_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def is_hidden(path: Path) -> bool:
    if path.name.startswith("."):
        return True
    try:
        attrs = path.stat().st_file_attributes  # Windows only
        return bool(attrs & stat.FILE_ATTRIBUTE_HIDDEN)
    except Exception:
        return False


@dataclass
class FileRecord:
    rel_path: str
    abs_path: str
    size_bytes: int
    extension: str
    mime_type: str
    created_at_utc: str
    modified_at_utc: str
    is_hidden: bool
    is_symlink: bool
    sha256: Optional[str] = None


@dataclass
class ScanError:
    path: str
    error_type: str
    message: str


@dataclass
class RunMeta:
    run_id: str
    workspace_root: str
    started_at_utc: str
    finished_at_utc: str
    total_files_scanned: int
    total_dirs_seen: int
    total_errors: int
    scanner_version: str
    deterministic_ordering: bool
    hash_small_files: bool
    hash_max_file_size_bytes: int


class WorkspaceScanner:
    def __init__(
        self,
        workspace: Path,
        output_dir: Path,
        exclude_dirs: Optional[set[str]] = None,
        exclude_suffixes: Optional[set[str]] = None,
        hash_small_files: bool = True,
        hash_max_size_bytes: int = HASH_MAX_FILE_SIZE_BYTES,
    ) -> None:
        self.workspace = workspace.resolve()
        self.output_dir = output_dir.resolve()
        self.exclude_dirs = exclude_dirs or set(DEFAULT_EXCLUDE_DIRS)
        self.exclude_suffixes = exclude_suffixes or set(DEFAULT_EXCLUDE_SUFFIXES)
        self.hash_small_files = hash_small_files
        self.hash_max_size_bytes = hash_max_size_bytes

        self.records: List[FileRecord] = []
        self.errors: List[ScanError] = []
        self.total_dirs_seen = 0

    def should_skip_file(self, path: Path) -> bool:
        return path.suffix.lower() in self.exclude_suffixes

    def iter_files(self) -> Iterable[Path]:
        for root, dirs, files in os.walk(self.workspace, topdown=True):
            root_path = Path(root)

            dirs[:] = sorted(d for d in dirs if d not in self.exclude_dirs)
            files[:] = sorted(files)

            self.total_dirs_seen += 1

            for file_name in files:
                path = root_path / file_name
                if self.should_skip_file(path):
                    continue
                yield path

    def build_file_record(self, path: Path) -> FileRecord:
        st = path.stat()
        rel_path = path.relative_to(self.workspace).as_posix()

        sha256_value: Optional[str] = None
        if self.hash_small_files and st.st_size <= self.hash_max_size_bytes:
            sha256_value = compute_sha256(path)

        return FileRecord(
            rel_path=rel_path,
            abs_path=str(path),
            size_bytes=st.st_size,
            extension=path.suffix.lower(),
            mime_type=safe_mime_type(path),
            created_at_utc=iso_from_timestamp(st.st_ctime),
            modified_at_utc=iso_from_timestamp(st.st_mtime),
            is_hidden=is_hidden(path),
            is_symlink=path.is_symlink(),
            sha256=sha256_value,
        )

    def scan(self) -> tuple[list[FileRecord], list[ScanError]]:
        for path in self.iter_files():
            try:
                record = self.build_file_record(path)
                self.records.append(record)
            except Exception as e:
                self.errors.append(
                    ScanError(
                        path=str(path),
                        error_type=type(e).__name__,
                        message=str(e),
                    )
                )

        self.records.sort(key=lambda r: r.rel_path)
        self.errors.sort(key=lambda e: e.path)
        return self.records, self.errors

    def write_outputs(self) -> RunMeta:
        self.output_dir.mkdir(parents=True, exist_ok=True)

        run_id = self.output_dir.parent.name
        started_at = utc_now_iso()

        self.scan()

        inventory_path = self.output_dir / "inventory.json"
        errors_path = self.output_dir / "errors.json"

        inventory_payload = {
            "schema_version": "v1",
            "workspace_root": str(self.workspace),
            "generated_at_utc": utc_now_iso(),
            "files": [asdict(r) for r in self.records],
        }

        errors_payload = {
            "schema_version": "v1",
            "generated_at_utc": utc_now_iso(),
            "errors": [asdict(e) for e in self.errors],
        }

        inventory_path.write_text(
            json.dumps(inventory_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        errors_path.write_text(
            json.dumps(errors_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        finished_at = utc_now_iso()

        run_meta = RunMeta(
            run_id=run_id,
            workspace_root=str(self.workspace),
            started_at_utc=started_at,
            finished_at_utc=finished_at,
            total_files_scanned=len(self.records),
            total_dirs_seen=self.total_dirs_seen,
            total_errors=len(self.errors),
            scanner_version="dv-scanner-v1",
            deterministic_ordering=True,
            hash_small_files=self.hash_small_files,
            hash_max_file_size_bytes=self.hash_max_size_bytes,
        )

        run_meta_path = self.output_dir / "run.meta.json"
        run_meta_path.write_text(
            json.dumps(asdict(run_meta), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return run_meta


def build_run_output_dir(base_runs_dir: Path) -> Path:
    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    return base_runs_dir / run_id / "output"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Data Verdict Workspace Scanner")
    parser.add_argument(
        "--workspace",
        required=True,
        help="Path to workspace root",
    )
    parser.add_argument(
        "--runs-dir",
        default="runs",
        help="Base runs directory (default: runs)",
    )
    parser.add_argument(
        "--no-hash",
        action="store_true",
        help="Disable sha256 hashing for small files",
    )
    parser.add_argument(
        "--hash-max-mb",
        type=int,
        default=10,
        help="Hash only files up to this size in MB (default: 10)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    workspace = Path(args.workspace)
    runs_dir = Path(args.runs_dir)

    if not workspace.exists():
        print(f"ERROR: workspace does not exist: {workspace}", file=sys.stderr)
        return 2

    if not workspace.is_dir():
        print(f"ERROR: workspace is not a directory: {workspace}", file=sys.stderr)
        return 2

    output_dir = build_run_output_dir(runs_dir)

    scanner = WorkspaceScanner(
        workspace=workspace,
        output_dir=output_dir,
        hash_small_files=not args.no_hash,
        hash_max_size_bytes=args.hash_max_mb * 1024 * 1024,
    )

    run_meta = scanner.write_outputs()

    print("DV SCAN COMPLETE")
    print(f"Run ID: {run_meta.run_id}")
    print(f"Workspace: {run_meta.workspace_root}")
    print(f"Files scanned: {run_meta.total_files_scanned}")
    print(f"Directories seen: {run_meta.total_dirs_seen}")
    print(f"Errors: {run_meta.total_errors}")
    print(f"Output: {output_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
