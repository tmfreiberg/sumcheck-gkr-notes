from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Union

from . import utils


def _find_project_root(start: Optional[Path] = None) -> Path:
    """Walk upward from `start` (default: cwd) until a marker file appears.
    Works in notebooks, scripts, and editable installs; falls back to the
    package location."""
    markers = {"pyproject.toml", "README.md"}
    cur = (start or Path.cwd()).resolve()
    for p in [cur, *cur.parents]:
        if any((p / m).exists() for m in markers):
            return p
    return Path(__file__).resolve().parents[2]


def init(*, verbose: bool = False, root: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Environment helpers for notebooks and demos: project paths, the shared
    print helpers, and the colour palette. No sys.path manipulation."""
    project_root = Path(root).resolve() if root else _find_project_root()

    env: Dict[str, Any] = {
        "PROJECT_PATH": project_root,
        "SCRIPTS_PATH": project_root / "src" / "gkr",
        "NOTEBOOKS_PATH": project_root / "notebooks",
        "print_header": utils.print_header,
        "display_aligned": utils.display_aligned,
        "RED": utils.RED,
        "GREEN": utils.GREEN,
        "YELLOW": utils.YELLOW,
        "PINK": utils.PINK,
        "BLUE": utils.BLUE,
        "PURPLE": utils.PURPLE,
        "RESET": utils.RESET,
    }

    if verbose:
        utils.print_header("Project paths")
        for name in ("PROJECT_PATH", "SCRIPTS_PATH", "NOTEBOOKS_PATH"):
            print(f"{name} = {env[name]}")

    return env