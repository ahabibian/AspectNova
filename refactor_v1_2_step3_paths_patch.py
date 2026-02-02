from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent
TOOLS = ROOT / "tools"

FILES = [
    TOOLS / "execute_cleanup_plan_v1_1.py",
    TOOLS / "restore_archive_v1_1.py",
]

def patch_file(p: Path) -> None:
    src = p.read_text(encoding="utf-8")

    # ensure import exists
    if "from core.storage.paths import WorkspacePaths" not in src:
        # insert after other core.storage imports if present
        m = re.search(r"(from core\.storage\.[^\n]+\n)+", src)
        if m:
            insert_at = m.end()
            src = src[:insert_at] + "from core.storage.paths import WorkspacePaths\n" + src[insert_at:]
        else:
            # fallback: insert after stdlib imports block
            m2 = re.search(r"(import [^\n]+\n)+\n", src)
            if not m2:
                raise RuntimeError(f"could not find import block in {p}")
            insert_at = m2.end()
            src = src[:insert_at] + "from core.storage.paths import WorkspacePaths\n\n" + src[insert_at:]

    # execute tool: replace manual join paths if they exist
    if p.name == "execute_cleanup_plan_v1_1.py":
        # replace the three path constructions in write_trace_contract (contracts_dir/archive_dir/contract_path)
        src = re.sub(
            r"contracts_dir\s*=\s*root\s*/\s*\"\.aspectnova\"\s*/\s*\"contracts\"\s*/\s*workspace_id\s*/\s*run_id",
            "paths = WorkspacePaths(root=root, workspace_id=workspace_id, run_id=run_id)\n    contracts_dir = paths.contracts_dir",
            src,
        )
        src = re.sub(
            r"archive_dir\s*=\s*root\s*/\s*\"\.aspectnova\"\s*/\s*\"archive\"\s*/\s*workspace_id\s*/\s*run_id",
            "archive_dir = paths.archive_dir",
            src,
        )
        src = re.sub(
            r"contract_path\s*=\s*contracts_dir\s*/\s*\"trace_contract\.json\"",
            "contract_path = paths.trace_contract_path",
            src,
        )

    if p.name == "restore_archive_v1_1.py":
        # replace zip/manifest locate logic if it uses ".aspectnova/.../payload.zip"
        src = re.sub(
            r"zip_path\s*=\s*root\s*/\s*\"\.aspectnova\"\s*/\s*\"archive\"\s*/\s*workspace_id\s*/\s*run_id\s*/\s*\"payload\.zip\"",
            "paths = WorkspacePaths(root=root, workspace_id=workspace_id, run_id=run_id)\n    zip_path = paths.payload_zip_path",
            src,
        )
        src = re.sub(
            r"manifest_path\s*=\s*root\s*/\s*\"\.aspectnova\"\s*/\s*\"archive\"\s*/\s*workspace_id\s*/\s*run_id\s*/\s*\"manifest\.json\"",
            "manifest_path = paths.manifest_path",
            src,
        )

    p.write_text(src, encoding="utf-8")
    print("OK:", p)

def main():
    for p in FILES:
        if not p.exists():
            raise SystemExit(f"missing: {p}")
        patch_file(p)

if __name__ == "__main__":
    main()
