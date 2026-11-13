"""Render every theme from the fixture into docs/samples/ (used by the README)."""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
from cards42 import profile, render  # noqa: E402
from cards42.themes import THEMES  # noqa: E402

user = json.loads((root / "tests/fixtures/user.json").read_text())
out = root / "docs/samples"
out.mkdir(parents=True, exist_ok=True)
for name, theme in THEMES.items():
    (out / f"{name}.svg").write_text(render.render(profile.from_api(user), theme))
print(f"wrote {len(THEMES)} samples to {out}")
