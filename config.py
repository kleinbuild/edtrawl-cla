"""Loads and updates config.toml, which is gitignored and created from config.example.toml."""
import dataclasses
import json
import re
import shutil
import tomllib
from pathlib import Path

EXAMPLE = Path(__file__).with_name("config.example.toml")


@dataclasses.dataclass
class Config:
    home_key: str | None = None
    radius_miles: float = 20
    max_age_days: int = 90
    routing: str = "estimate"  # estimate | osrm
    osrm_url: str = "https://router.project-osrm.org"
    rush_scale_am: float = 0.75
    rush_scale_pm: float = 1.2
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_key: str | None = None
    match_accept: float = 0.90
    match_margin: float = 0.05


def _ensure(path):
    path = Path(path)
    if not path.exists():
        shutil.copyfile(EXAMPLE, path)
    return path


def load(path="config.toml"):
    # A missing home is not an error here: home_key stays None and the UI words what to do.
    with open(_ensure(path), "rb") as f:
        cfg = Config(**tomllib.load(f))  # an unknown or misspelt key raises instead of being ignored
    if cfg.routing not in ("estimate", "osrm"):
        raise ValueError(f"routing must be 'estimate' or 'osrm', not {cfg.routing!r}")
    return cfg


def set(key, value, path="config.toml"):
    """Rewrite the one line that sets `key` (uncommenting it if needed); every other byte is kept."""
    if key not in {f.name for f in dataclasses.fields(Config)}:
        raise KeyError(key)
    if value is None:  # TOML has no null; an unset setting is a commented-out line, edited by hand
        raise ValueError(f"{key} cannot be set to None")
    # json.dumps writes numbers and double-quoted strings in a form TOML also accepts.
    text = "true" if value is True else "false" if value is False else json.dumps(value)
    path = _ensure(path)
    with open(path, encoding="utf-8", newline="") as f:
        lines = f.readlines()
    pattern = re.compile(rf"\s*#?\s*{key}\s*=")
    for i, line in enumerate(lines):
        if pattern.match(line):
            ending = line[len(line.rstrip("\r\n")):]
            lines[i] = f"{key} = {text}{ending}"
            break
    else:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(f"{key} = {text}\n")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.writelines(lines)
