from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from datetime import datetime, timezone


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


class DVPackager:

    def __init__(self, run_output: Path) -> None:
        self.run_output = run_output.resolve()
        self.run_root = self.run_output.parent
        self.artifacts_dir = self.run_root.parent / "artifacts"

    def validate(self) -> None:
        if not self.run_output.exists():
            raise FileNotFoundError("run output directory not found")

    def collect_files(self):

        mapping = {
            "meta/run.meta.json": "run.meta.json",
            "report/dv_report.json": "dv_report.json",
            "report/dv_report.md": "dv_report.md",
            "plan/cleanup_plan.json": "cleanup_plan.json",
            "data/inventory.json": "inventory.json",
            "data/scores.json": "scores.json",
            "data/policy.eval.json": "policy.eval.json",
            "data/verdict.json": "verdict.json",
        }

        collected = []

        for target, source in mapping.items():
            src = self.run_output / source
            if src.exists():
                collected.append((src, target))

        return collected

    def build_manifest(self, collected):

        files = []

        for src, target in collected:

            files.append(
                {
                    "artifact_path": target,
                    "original_name": src.name,
                    "size_bytes": src.stat().st_size,
                    "sha256": sha256_file(src),
                }
            )

        return {
            "schema": "dv_artifact_manifest_v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "file_count": len(files),
            "files": files,
        }

    def package(self):

        self.validate()

        run_id = self.run_root.name

        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        artifact_path = self.artifacts_dir / f"dv_{run_id}.zip"

        collected = self.collect_files()

        manifest = self.build_manifest(collected)

        with zipfile.ZipFile(artifact_path, "w", compression=zipfile.ZIP_DEFLATED) as z:

            for src, target in collected:
                z.write(src, f"dv_artifact/{target}")

            manifest_bytes = json.dumps(
                manifest,
                indent=2,
                ensure_ascii=False
            ).encode("utf-8")

            z.writestr(
                "dv_artifact/manifest/artifact_manifest.json",
                manifest_bytes
            )

        return artifact_path, manifest


def parse_args():

    parser = argparse.ArgumentParser(description="DV Artifact Packager")

    parser.add_argument(
        "--output-dir",
        required=True,
        help="run output directory",
    )

    return parser.parse_args()


def main():

    args = parse_args()

    output_dir = Path(args.output_dir)

    try:

        packager = DVPackager(output_dir)

        artifact, manifest = packager.package()

        print("DV ARTIFACT CREATED")
        print(f"Artifact: {artifact}")
        print(f"Files packaged: {manifest['file_count']}")

        return 0

    except Exception as e:

        print(f"ERROR: {e}", file=sys.stderr)

        return 2


if __name__ == "__main__":
    raise SystemExit(main())
