import sys
from pathlib import Path

path = Path(sys.argv[1])
content = sys.stdin.read()
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(content, encoding="utf-8")
print("WROTE", path)
