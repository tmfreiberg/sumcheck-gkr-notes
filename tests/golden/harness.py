"""
Golden-transcript harness for the sum-check / GKR pedagogical protocols.

Each Scenario runs an interactive protocol in a *fresh subprocess* with:

  - a fixed RNG seed (machine choices: challenges, dishonest claims, coin flips),
  - PYTHONHASHSEED=0 (set-iteration order in circuit construction),
  - GKR_COLOR=always (ANSI colors captured, so color semantics are protected),
  - UTF-8 I/O forced (Windows-safe for W-tilde, alpha, rho, ...),
  - canned stdin (the user's answers to every prompt).

The captured stdout is compared byte-for-byte against a blessed transcript in
tests/golden/transcripts/. If a refactor intentionally changes narration, re-bless:

    python tests/golden/harness.py --bless            # all scenarios
    python tests/golden/harness.py --bless NAME ...   # specific ones

Other commands:

    python tests/golden/harness.py --list             # show scenarios
    python tests/golden/harness.py --check            # run + compare (like pytest)
    python tests/golden/harness.py --run NAME         # print a live transcript

Blessed transcripts are committed to git: a diff in review == a deliberate
narration change.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent            # tests/golden
REPO_ROOT = HERE.parents[1]                       # repository root
SRC_DIR = REPO_ROOT / "src"
TRANSCRIPT_DIR = HERE / "transcripts"
VERSIONS_FILE = HERE / "versions.json"

GOLDEN_SUFFIX = ".golden.txt"


# ----------------------------------------------------------------------------
# Scenarios
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    stdin: str            # canned answers, one per prompt, '\n'-terminated
    seed: int             # random.seed(...) in the child process
    code: str             # python statements that bind `res`
    expect: str           # repr of the expected return value: "True"|"False"|"None"
    timeout: int = 300


GKR = "from gkr.protocol.gkr_session import gkr\nres = gkr()"
SUMCHECK = "from gkr.protocol.sumcheck_session import sum_check\nres = sum_check()"
SUMCHECK_COMMIT = "from gkr.protocol.sumcheck_session import sum_check\nres = sum_check(use_commitment=True)"
GKR_PREBUILT = (
    "from gkr.ac import ArithmeticCircuit\n"
    "from gkr.protocol.gkr_session import gkr\n"
    "ac = ArithmeticCircuit('(3*2) + (4 + 1)', prime=331)\n"
    "res = gkr(ac)"
)

# NOTE on stdin scripts: prompts consume answers strictly in order. Dishonest
# user-prover runs consume a variable number of 'y' answers (laundering can end
# the forging early), so those scripts carry surplus 'y' lines; unread lines
# are harmless.

SCENARIOS: List[Scenario] = [
    # ------------------------------ GKR ------------------------------------
    Scenario(
        name="gkr_spectator_honest",
        description="Non-interactive, default circuit over GF(331), honest prover; accept.",
        stdin="n\n331\n\na\n",
        seed=101,
        code=GKR,
        expect="True",
    ),
    Scenario(
        name="gkr_spectator_dishonest",
        description="Non-interactive, dishonest machine prover; forced forging; reject at final check.",
        stdin="n\n331\n\nc\n",
        seed=102,
        code=GKR,
        expect="False",
    ),
    Scenario(
        name="gkr_prover_honest",
        description="User plays prover and claims the true output (11); accept.",
        stdin="y\ny\nn\n331\n\n11\n",
        seed=103,
        code=GKR,
        expect="True",
    ),
    Scenario(
        name="gkr_prover_dishonest_accepts_suggestions",
        description="User plays dishonest prover (claims 10), accepting every suggested cheat with 'y'.",
        stdin="y\ny\nn\n331\n\n10\n" + "y\n" * 12,
        seed=104,
        code=GKR,
        expect="False",
    ),
    Scenario(
        name="gkr_prover_bad_polynomial_rejected",
        description="Dishonest user-prover types an inconsistent g*_0; V rejects mid-sum-check.",
        stdin="y\ny\nn\n331\n\n10\n7*x_0 + 1\n",
        seed=105,
        code=GKR,
        expect="False",
    ),
    Scenario(
        name="gkr_verifier_secret_dishonest",
        description="User plays verifier (secret mode) against a dishonest machine prover, entering all challenges.",
        stdin="y\nn\ny\n331\n\nc\n5\n17\n23\n8\n99\n141\n7\n",
        seed=106,
        code=GKR,
        expect="False",
    ),
    Scenario(
        name="gkr_multi_output_dishonest",
        description="Two output gates (s_0 = 1) over GF(101); dishonest machine prover; reject.",
        stdin="n\n101\n(1+2)*(3+4); (5+6)+(7*8)\nc\n",
        seed=107,
        code=GKR,
        expect="False",
    ),
    Scenario(
        name="gkr_small_prime_false_positive",
        description="GF(5): a forged polynomial gets laundered and V accepts a false claim (FALSE POSITIVE narration).",
        stdin="n\n5\n\nc\n",
        seed=1,  # chosen so that laundering occurs; see bless-time verification
        code=GKR,
        expect="True",
    ),
    Scenario(
        name="gkr_cancel_aborts",
        description="Dishonest user-prover cancels at the first suggestion; protocol aborts with None.",
        stdin="y\ny\nn\n331\n\n10\ncancel\n",
        seed=109,
        code=GKR,
        expect="None",
    ),
    Scenario(
        name="gkr_invalid_circuit_retry",
        description="A non-strictly-layered circuit is rejected with hints; the retry (default circuit) proceeds.",
        stdin="n\n331\n5*4 + 3\n\nc\n",
        seed=110,
        code=GKR,
        expect="False",
    ),
    Scenario(
        name="gkr_prebuilt_circuit",
        description="gkr(ac) with a prebuilt ArithmeticCircuit (notebook usage); honest; accept.",
        stdin="n\na\n",
        seed=111,
        code=GKR_PREBUILT,
        expect="True",
    ),
    # ---------------------------- sum-check --------------------------------
    Scenario(
        name="sumcheck_spectator_honest",
        description="Non-interactive sum-check on x*y + x*z + z**2 over GF(331); honest; accept.",
        stdin="n\n331\nx*y + x*z + z**2\na\n",
        seed=112,
        code=SUMCHECK,
        expect="True",
    ),
    Scenario(
        name="sumcheck_prover_dishonest_accepts_suggestions",
        description="User plays dishonest prover on x*y + z**2 (claims 5), accepting suggestions with 'y'.",
        stdin="y\ny\nn\n331\nx*y + z**2\n5\n" + "y\n" * 4,
        seed=113,
        code=SUMCHECK,
        expect="False",
    ),
    Scenario(
        name="sumcheck_prover_lie_laundered",
        description=(
            "User plays dishonest prover over GF(5): claims H* = 2 when H = 1, accepts the "
            "suggested forgery, and r_0 lands on a root of g*_0 - g_0. The lie is laundered, "
            "P plays honestly thereafter, and V accepts a false claim. Covers the launder "
            "announcement (no other scenario reaches it) and a sum-check FALSE POSITIVE."
        ),
        stdin="y\ny\nn\n5\nx*y + z**2\n2\ny\n",
        seed=1,
        code=SUMCHECK,
        expect="True",
    ),
    Scenario(
        name="sumcheck_verifier_dishonest",
        description="User plays verifier (secret mode) against a dishonest machine prover, entering challenges 1,1,1.",
        stdin="y\nn\ny\n331\nx*y + x*z + z**2\nc\n1\n1\n1\n",
        seed=114,
        code=SUMCHECK,
        expect="False",
    ),
    Scenario(
        name="sumcheck_commitment_honest",
        description="Toy-commitment mode: honest prover and honest opening; accept.",
        stdin="n\n331\nx*y + z**2\na\na\n",
        seed=115,
        code=SUMCHECK_COMMIT,
        expect="True",
    ),
    # ------------------- cancelling at a challenge prompt -------------------
    # Regression tests: a user-verifier typing 'c' at a challenge prompt (an
    # option the prompt itself advertises) must abort cleanly, not crash.
    Scenario(
        name="sumcheck_verifier_cancels",
        description="User-verifier cancels at the first challenge prompt; graceful abort (None).",
        stdin="y\nn\ny\n331\nx*y + z**2\nc\nc\n",
        seed=116,
        code=SUMCHECK,
        expect="None",
    ),
    Scenario(
        name="gkr_verifier_cancels",
        description="User-verifier cancels at the first challenge prompt inside a GKR layer sum-check; graceful abort (None).",
        stdin="y\nn\ny\n331\n\nc\nc\n",
        seed=117,
        code=GKR,
        expect="None",
    ),
]

_BY_NAME: Dict[str, Scenario] = {s.name: s for s in SCENARIOS}


def get(name: str) -> Scenario:
    return _BY_NAME[name]


# ----------------------------------------------------------------------------
# Running
# ----------------------------------------------------------------------------

DRIVER_TEMPLATE = """\
import random
random.seed({seed})
{code}
print("RETURN VALUE:", res)
"""


def child_env() -> Dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(SRC_DIR) + (os.pathsep + existing if existing else "")
    env["PYTHONHASHSEED"] = "0"        # set-iteration order during circuit construction
    env["GKR_COLOR"] = "always"    # capture ANSI colors in the golden transcripts
    env["PYTHONUTF8"] = "1"            # Windows-safe unicode I/O
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run_scenario(scenario: Scenario) -> Tuple[str, subprocess.CompletedProcess]:
    """Run the scenario in a fresh interpreter; return (normalized stdout, process)."""
    driver = DRIVER_TEMPLATE.format(seed=scenario.seed, code=scenario.code)
    proc = subprocess.run(
        [sys.executable, "-c", driver],
        input=scenario.stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=child_env(),
        cwd=str(REPO_ROOT),
        timeout=scenario.timeout,
    )
    stdout = proc.stdout.replace("\r\n", "\n")
    return stdout, proc


def verify_run(scenario: Scenario, stdout: str, proc: subprocess.CompletedProcess) -> List[str]:
    """Sanity checks independent of the golden file. Returns a list of problems."""
    problems: List[str] = []
    if proc.returncode != 0:
        problems.append(f"child exited with code {proc.returncode}")
    if "Traceback" in stdout or "Traceback" in (proc.stderr or ""):
        problems.append("a Traceback appeared in the output")
    marker = f"RETURN VALUE: {scenario.expect}"
    if marker not in stdout:
        problems.append(f"expected final line {marker!r} not found")
    return problems


# ----------------------------------------------------------------------------
# Goldens
# ----------------------------------------------------------------------------

def golden_path(name: str) -> Path:
    return TRANSCRIPT_DIR / f"{name}{GOLDEN_SUFFIX}"


def load_golden(name: str) -> Optional[str]:
    path = golden_path(name)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


_ANSI_NAMES = {"31": "RED", "32": "GREEN", "33": "YELLOW", "34": "BLUE", "35": "PURPLE", "0": "/"}


def readable(s: str) -> str:
    """Replace ANSI escapes with visible tokens so diffs stay legible."""
    def sub(m: "re.Match[str]") -> str:
        return "\u27e8" + _ANSI_NAMES.get(m.group(1), m.group(1)) + "\u27e9"
    return re.sub(r"\x1b\[([0-9;]*)m", sub, s)


def diff_text(golden: str, actual: str, name: str, context: int = 3, max_lines: int = 80) -> str:
    lines = list(
        difflib.unified_diff(
            readable(golden).splitlines(keepends=True),
            readable(actual).splitlines(keepends=True),
            fromfile=f"{name} (blessed)",
            tofile=f"{name} (current)",
            n=context,
        )
    )
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"... ({len(lines) - max_lines} more diff lines)\n"]
    return "".join(lines)


def format_failure(scenario: Scenario, golden: str, actual: str) -> str:
    return (
        f"Transcript for '{scenario.name}' differs from the blessed golden.\n\n"
        + diff_text(golden, actual, scenario.name)
        + "\nIf this change is intentional, re-bless with:\n"
        + f"    python tests/golden/harness.py --bless {scenario.name}\n"
    )


def bless(names: Optional[List[str]] = None) -> None:
    targets = SCENARIOS if not names else [get(n) for n in names]
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    failures: List[str] = []
    for sc in targets:
        stdout, proc = run_scenario(sc)
        problems = verify_run(sc, stdout, proc)
        if problems:
            failures.append(f"{sc.name}: " + "; ".join(problems))
            print(f"[FAIL] {sc.name}: {'; '.join(problems)}")
            continue
        golden_path(sc.name).write_text(stdout, encoding="utf-8", newline="\n")
        print(f"[BLESSED] {sc.name}  ({len(stdout.splitlines())} lines)")
    _record_versions()
    if failures:
        raise SystemExit("Some scenarios failed sanity checks; goldens NOT written for those:\n"
                         + "\n".join(failures))


def _record_versions() -> None:
    try:
        import sympy
        sympy_version = sympy.__version__
    except Exception:
        sympy_version = "unknown"
    VERSIONS_FILE.write_text(
        json.dumps(
            {
                "python": platform.python_version(),
                "sympy": sympy_version,
                "note": "Versions at blessing time. Goldens can drift across SymPy versions "
                        "(expression string forms); if these differ from your environment, "
                        "expect to re-bless rather than chase phantom regressions.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def blessed_versions() -> Optional[Dict[str, str]]:
    if not VERSIONS_FILE.exists():
        return None
    return json.loads(VERSIONS_FILE.read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def _cmd_list() -> None:
    width = max(len(s.name) for s in SCENARIOS)
    for s in SCENARIOS:
        mark = "*" if golden_path(s.name).exists() else " "
        print(f"[{mark}] {s.name:<{width}}  seed={s.seed:<4}  expect={s.expect:<5}  {s.description}")
    print("\n[*] = blessed golden exists")


def _cmd_check() -> int:
    bad = 0
    for sc in SCENARIOS:
        stdout, proc = run_scenario(sc)
        problems = verify_run(sc, stdout, proc)
        golden = load_golden(sc.name)
        if problems:
            print(f"[FAIL] {sc.name}: {'; '.join(problems)}")
            bad += 1
        elif golden is None:
            print(f"[MISSING] {sc.name}: no golden; bless it first")
            bad += 1
        elif stdout != golden:
            print(f"[DIFF] {sc.name}:")
            print(diff_text(golden, stdout, sc.name))
            bad += 1
        else:
            print(f"[OK] {sc.name}")
    return bad


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="list scenarios")
    group.add_argument("--bless", nargs="*", metavar="NAME", help="regenerate goldens (all if no names given)")
    group.add_argument("--check", action="store_true", help="run all scenarios and compare to goldens")
    group.add_argument("--run", metavar="NAME", help="run one scenario and print its transcript (ANSI made readable)")
    args = parser.parse_args(argv)

    if args.list:
        _cmd_list()
    elif args.bless is not None:
        bless(args.bless or None)
    elif args.check:
        raise SystemExit(_cmd_check())
    elif args.run:
        sc = get(args.run)
        stdout, proc = run_scenario(sc)
        print(readable(stdout))
        problems = verify_run(sc, stdout, proc)
        if problems:
            raise SystemExit("Sanity problems: " + "; ".join(problems))


if __name__ == "__main__":
    main()