"""Themes are data: one TOML file per theme in ./themes."""
import tomllib
from pathlib import Path

_DIR = Path(__file__).resolve().parent / "themes"
THEMES = {p.stem: tomllib.loads(p.read_text()) for p in sorted(_DIR.glob("*.toml"))}
DEFAULT = "kettlebells"
