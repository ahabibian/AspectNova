from __future__ import annotations
from pathlib import Path
import re

p = Path("run_manifest_stage.py")
txt = p.read_text(encoding="utf-8")

# Add an alias helper if not present
if "_write_aliases" not in txt:
    helper = r'''
def _write_aliases(primary_path: Path, payload: str) -> None:
    """
    Write legacy+new filename aliases for manifest reports.
    We keep both dot and underscore variants to stabilize contracts.
    """
    name = primary_path.name

    aliases = set()

    # dot -> underscore
    aliases.add(name.replace(".", "_"))
    # underscore -> dot for the first two segments we care about
    # e.g. manifest_post_report_json -> (not used). Keep it simple:
    # handle known patterns:
    aliases.add(name.replace("manifest_post", "manifest.post").replace("manifest_pre", "manifest.pre"))

    # also handle report naming if primary already underscore:
    aliases.add(name.replace("manifest_post", "manifest.post").replace("manifest_pre", "manifest.pre"))

    for an in sorted(a for a in aliases if a and a != name):
        ap = primary_path.with_name(an)
        try:
            ap.write_text(payload, encoding="utf-8")
        except Exception:
            pass
'''
    # insert helper near top (after imports)
    txt = re.sub(r'(\nfrom pathlib import Path\n)', r'\1' + helper + '\n', txt, count=1)

# Now patch common write_text sites for manifest report outputs:
# We look for ".write_text(payload" patterns and call _write_aliases afterwards.

def add_alias_after_write(block: str) -> str:
    # block contains: some_path.write_text(payload, encoding="utf-8")
    # we add: _write_aliases(some_path, payload)
    m = re.search(r'(\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*.*Path.*\n)?\s*([A-Za-z_][A-Za-z0-9_\.]*)\.write_text\(\s*payload\s*,\s*encoding\s*=\s*"utf-8"\s*\)', block)
    return block

# More robust: after ANY line like: report_path.write_text(payload, encoding="utf-8")
# insert: _write_aliases(report_path, payload)
txt = re.sub(
    r'(?m)^(?P<indent>\s*)(?P<var>\w+)\.write_text\(\s*payload\s*,\s*encoding\s*=\s*"utf-8"\s*\)\s*$',
    r'\g<indent>\g<var>.write_text(payload, encoding="utf-8")\n\g<indent>_write_aliases(\g<var>, payload)',
    txt,
)

p.write_text(txt, encoding="utf-8")
print("PATCHED run_manifest_stage.py (write aliases) OK")
