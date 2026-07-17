"""Make the package importable from a source checkout (tests that import
`gkr` directly, rather than driving a subprocess, need src/ on the path)."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))