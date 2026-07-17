"""
Pytest wrapper around the golden-transcript harness.

Run from the repository root:

    pytest tests/ -q

If a test fails because a narration change was intentional, re-bless:

    python tests/golden/harness.py --bless <scenario_name>
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "golden"))
import harness  # noqa: E402


def _version_drift_warning() -> None:
    blessed = harness.blessed_versions()
    if blessed is None:
        return
    import platform
    try:
        import sympy
        current_sympy = sympy.__version__
    except Exception:
        current_sympy = "unknown"

    def major_minor(v: str) -> str:
        return ".".join(v.split(".")[:2])

    drift = []
    # Patch-level Python differences (3.12.3 vs 3.12.9) don't affect transcripts,
    # so only warn on major.minor drift. SymPy is compared exactly: its version
    # bumps *can* change printed expression forms.
    blessed_py = blessed.get("python", "")
    if major_minor(blessed_py) != major_minor(platform.python_version()):
        drift.append(f"python {blessed_py} -> {platform.python_version()}")
    if blessed.get("sympy") != current_sympy:
        drift.append(f"sympy {blessed.get('sympy')} -> {current_sympy}")
    if drift:
        warnings.warn(
            "Golden transcripts were blessed under different versions ("
            + ", ".join(drift)
            + "); expression string forms may differ. If diffs look cosmetic, re-bless.",
            stacklevel=1,
        )


_version_drift_warning()


@pytest.mark.parametrize("scenario", harness.SCENARIOS, ids=[s.name for s in harness.SCENARIOS])
def test_golden_transcript(scenario: "harness.Scenario") -> None:
    stdout, proc = harness.run_scenario(scenario)

    problems = harness.verify_run(scenario, stdout, proc)
    assert not problems, f"{scenario.name}: " + "; ".join(problems) + "\n--- stderr ---\n" + (proc.stderr or "")[:2000]

    golden = harness.load_golden(scenario.name)
    if golden is None:
        pytest.fail(
            f"No blessed golden for '{scenario.name}'. Generate it with:\n"
            f"    python tests/golden/harness.py --bless {scenario.name}"
        )
    if stdout != golden:
        pytest.fail(harness.format_failure(scenario, golden, stdout))


def test_runs_are_deterministic() -> None:
    """Two fresh subprocesses of the same seeded scenario must agree byte-for-byte.

    This guards the environment pinning itself (PYTHONHASHSEED, deterministic
    node naming in ac.py): if it fails, golden comparisons are meaningless.
    """
    scenario = harness.get("gkr_spectator_dishonest")
    first, _ = harness.run_scenario(scenario)
    second, _ = harness.run_scenario(scenario)
    assert first == second, "same seed, same stdin, different transcripts: determinism is broken"
