"""
Invariant (property) tests: the mathematics, not the narration.

The golden transcripts pin the *text* of specific runs. These tests pin the
*properties* that must hold across many runs the goldens never recorded:

  completeness  an honest prover is always accepted;
  soundness     a dishonest prover is accepted ONLY when the run's own event
                log records the lie being laundered -- a random challenge
                landing where a forged object agrees with the true one.

The second is the interesting one: it states the soundness bookkeeping as an
invariant over the log rather than a claim in a comment. It is only expressible
because the refactor made the protocol a library -- parties are injectable, the
verdict is a value rather than printed text, and Sink(renderer=None) runs the
whole thing silently. Small fields are used deliberately: over GF(5) laundering
is common, so both branches of the implication get exercised.
"""
from __future__ import annotations

import random
from itertools import product
from typing import List, Sequence

import pytest
from sympy import Poly, symbols
from sympy.polys.domains import GF

from gkr.ac import ArithmeticCircuit
from gkr.errors import CircuitError
from gkr.protocol import (
    Accepted,
    MachineProver,
    PolynomialOracle,
    RandomVerifier,
    Rejected,
    Sink,
    run_gkr,
    run_sum_check,
)
from gkr.protocol.gkr_events import (
    FoldLaunderAnnounced,
    FoldLaunderNote,
    InitialLieOdds,
    SumCheckLaunderNote,
    VacuousBridge,
)
from gkr.protocol.gkr_parties import GkrMachineProver
from gkr.protocol.gkr_support import _machine_claimed_outputs
from gkr.protocol.sumcheck_events import Laundered

# ----------------------------------------------------------------------------
# Headless helpers
# ----------------------------------------------------------------------------

def _random_poly(p: int, v: int, rng: random.Random) -> Poly:
    """A random polynomial in v variables over GF(p), degree <= 2 per variable."""
    F = GF(p, symmetric=False)
    X = symbols(f"X_:{v}")
    expr = 0
    for exponents in product(range(3), repeat=v):
        if sum(exponents) > 3:
            continue
        coeff = rng.randrange(p)
        if coeff:
            term = coeff
            for var, e in zip(X, exponents):
                term *= var**e
            expr += term
    return Poly(expr, *X, domain=F)


def _true_sum(g: Poly):
    F, X, v = g.domain, g.gens, len(g.gens)
    return F(sum(
        g.eval({X[k]: b_k for k, b_k in enumerate(b)})
        for b in product([F(0), F(1)], repeat=v)
    ))


def _run_sumcheck_headless(g: Poly, *, dishonest: bool, seed: int):
    """Run the protocol with no renderer at all; return (verdict, event log)."""
    random.seed(seed)
    F = g.domain
    sink = Sink()                      # renderer=None: silent
    H = _true_sum(g)
    prover = MachineProver(g, H, sink, dishonest_claim=dishonest)
    result = run_sum_check(
        field=F,
        gens=g.gens,
        degree_bounds=[int(g.degree(gen)) for gen in g.gens],
        prover=prover,
        verifier=RandomVerifier(F),
        oracle=PolynomialOracle(g),
        sink=sink,
    )
    return result, sink.log


class _ScriptedGkrProver(GkrMachineProver):
    """A machine prover whose claims are supplied rather than prompted for.

    Overriding one method is all it takes to make GKR headless -- the payoff of
    parties being objects the engine never introspects.
    """

    def __init__(self, ac, sink, *, dishonest: bool):
        super().__init__(ac, sink, secret_mode=False)
        self._dishonest = dishonest

    def claim_outputs(self, ctx):
        return _machine_claimed_outputs(self.ac, self._dishonest)


def _run_gkr_headless(ac, *, dishonest: bool, seed: int):
    random.seed(seed)
    sink = Sink()
    prover = _ScriptedGkrProver(ac, sink, dishonest=dishonest)
    result = run_gkr(ac, prover=prover, verifier=RandomVerifier(ac.field), sink=sink)
    return result, sink.log


def _laundering_events(log: Sequence) -> List:
    """Every way a lie can become true mid-protocol.

    sum-check: a challenge hits a root of a forged round polynomial (Laundered,
    emitted by the prover that noticed).

    GKR: the layer engine records the same fact independently, from its own
    omniscient check that the terminal claim gamma equals the true bridging
    value (SumCheckLaunderNote). That is the canonical GKR-level record, and it
    is the one to trust: the inner prover's per-round detection cannot fire on
    the LAST round of a layer sum-check, because legacy GKR mode returns before
    the final-check block and the port reproduces that silence (see
    docs/refactor-design.md). Additionally in GKR: rho_0 lands where the
    claimed-output MLE agrees with the true one; the bridging equation is
    vacuous (A = M = 0 = gamma); or tau hits a root of q* - q.
    """
    out = []
    for e in log:
        if isinstance(e, Laundered):
            out.append(e)
        elif isinstance(e, (SumCheckLaunderNote, FoldLaunderNote,
                            FoldLaunderAnnounced, VacuousBridge)):
            out.append(e)
        elif isinstance(e, InitialLieOdds) and e.laundered_at_start:
            out.append(e)
    return out


# ----------------------------------------------------------------------------
# Sum-check
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("p", [5, 7, 11, 331])
@pytest.mark.parametrize("v", [2, 3])
def test_completeness_sumcheck(p: int, v: int) -> None:
    """An honest prover is always accepted."""
    rng = random.Random(f"{p}-{v}")
    for trial in range(5):
        g = _random_poly(p, v, rng)
        result, log = _run_sumcheck_headless(g, dishonest=False, seed=trial)
        assert isinstance(result.verdict, Accepted), (
            f"honest prover rejected: p={p}, v={v}, trial={trial}, g={g.as_expr()}"
        )
        assert not _laundering_events(log), "an honest run cannot launder a lie"


@pytest.mark.parametrize("p,v", [(5, 2), (5, 3), (7, 2), (11, 3), (331, 2)])
def test_soundness_sumcheck(p: int, v: int) -> None:
    """A dishonest prover is accepted only if the log records a laundering.

    This is the soundness bookkeeping, stated as an invariant: acceptance of a
    false claim implies a random challenge landed on a root of a forged
    polynomial.
    """
    rng = random.Random(f"snd-{p}-{v}")
    for trial in range(10):
        g = _random_poly(p, v, rng)
        if _true_sum(g) is None:
            continue
        result, log = _run_sumcheck_headless(g, dishonest=True, seed=trial)
        laundered = _laundering_events(log)
        if isinstance(result.verdict, Accepted):
            assert laundered, (
                f"FALSE POSITIVE with no laundering recorded: p={p}, v={v}, "
                f"trial={trial}, g={g.as_expr()}"
            )
        else:
            assert isinstance(result.verdict, Rejected)
            assert not laundered, (
                f"lie was laundered yet V rejected: p={p}, v={v}, trial={trial}"
            )


def test_soundness_is_not_vacuous_over_tiny_fields() -> None:
    """Both branches of the soundness implication must actually occur.

    Over GF(5) a dishonest prover should sometimes get away with it (a
    laundered lie) and usually not -- otherwise the test above proves nothing.
    """
    rng = random.Random("vacuity")
    accepted = rejected = 0
    for trial in range(40):
        g = _random_poly(5, 2, rng)
        result, log = _run_sumcheck_headless(g, dishonest=True, seed=trial)
        if isinstance(result.verdict, Accepted):
            accepted += 1
            assert _laundering_events(log)
        else:
            rejected += 1
    assert rejected > 0, "no dishonest run was ever caught: the test is vacuous"
    assert accepted > 0, (
        "no dishonest run ever succeeded over GF(5): the soundness implication "
        "is never exercised on its interesting branch"
    )


def test_challenges_recorded_match_the_log() -> None:
    """The returned challenge vector is exactly what the log says was sampled."""
    from gkr.protocol.sumcheck_events import ChallengeSampled

    rng = random.Random("challenges")
    g = _random_poly(331, 3, rng)
    result, log = _run_sumcheck_headless(g, dishonest=False, seed=3)
    sampled = [e.value for e in log if isinstance(e, ChallengeSampled)]
    assert list(result.challenges) == sampled


def test_same_seed_reproduces_the_run() -> None:
    rng = random.Random("determinism")
    g = _random_poly(331, 3, rng)
    a, _ = _run_sumcheck_headless(g, dishonest=True, seed=11)
    b, _ = _run_sumcheck_headless(g, dishonest=True, seed=11)
    c, _ = _run_sumcheck_headless(g, dishonest=True, seed=12)
    assert a.challenges == b.challenges and a.claim == b.claim
    assert (a.challenges, a.claim) != (c.challenges, c.claim)


# ----------------------------------------------------------------------------
# GKR
# ----------------------------------------------------------------------------

CIRCUITS = [
    ("(3*2) + (4 + 1)", 331),
    ("(3*2) + (4 + 1)", 11),
    ("(1+2)*(3+4); (5+6)+(7*8)", 101),   # multi-output: s_0 = 1, so rho_0 is non-trivial
]

# Building an ArithmeticCircuit is by far the most expensive thing here (the
# multi-output circuit takes ~55s: graphviz parse, networkx layering, and the
# multilinear extensions of every layer). The protocol runs themselves are
# milliseconds. Cache per (expression, prime) so the parametrised tests share
# one build instead of one each; the circuit is never mutated by a run.
_CIRCUIT_CACHE: dict = {}


def _circuit(expr: str, p: int) -> ArithmeticCircuit:
    key = (expr, p)
    if key not in _CIRCUIT_CACHE:
        _CIRCUIT_CACHE[key] = ArithmeticCircuit(
            *[e.strip() for e in expr.split(";")], prime=p
        )
    return _CIRCUIT_CACHE[key]


@pytest.mark.parametrize("expr,p", CIRCUITS)
def test_completeness_gkr(expr: str, p: int) -> None:
    """Honest claimed outputs are always accepted."""
    ac = _circuit(expr, p)
    for seed in range(3):
        result, log = _run_gkr_headless(ac, dishonest=False, seed=seed)
        assert result.status == "accept", f"honest GKR rejected: {expr} mod {p}, seed={seed}"
        assert not result.initial_claim_false
        assert not _laundering_events(log)


@pytest.mark.parametrize("expr,p", CIRCUITS)
def test_soundness_gkr(expr: str, p: int) -> None:
    """False claimed outputs are accepted only if the log records a laundering."""
    ac = _circuit(expr, p)
    for seed in range(6):
        result, log = _run_gkr_headless(ac, dishonest=True, seed=seed)
        assert result.initial_claim_false
        laundered = _laundering_events(log)
        if result.status == "accept":
            assert laundered, (
                f"FALSE POSITIVE with no laundering recorded: {expr} mod {p}, seed={seed}"
            )
        else:
            assert result.status == "reject"
            assert not laundered, (
                f"a laundered lie was rejected anyway: {expr} mod {p}, seed={seed} -- "
                f"once the carried claim becomes true, honest play should carry the run"
            )


def test_gkr_false_positives_occur_over_a_tiny_field() -> None:
    """Over GF(5) the small-field false positive must actually happen, or the
    GKR soundness test above never exercises its interesting branch."""
    ac = _circuit("(3*2) + (4 + 1)", 5)
    outcomes = {"accept": 0, "reject": 0}
    for seed in range(30):
        result, log = _run_gkr_headless(ac, dishonest=True, seed=seed)
        outcomes[result.status] = outcomes.get(result.status, 0) + 1
        if result.status == "accept":
            assert _laundering_events(log)
    assert outcomes["reject"] > 0, "no dishonest GKR run was ever caught"
    assert outcomes["accept"] > 0, "no dishonest GKR run ever succeeded over GF(5)"


# ----------------------------------------------------------------------------
# Notation routing
# ----------------------------------------------------------------------------

def test_no_unrouted_notation_symbols() -> None:
    """No renderer may hard-code a protocol symbol.

    This guards the one failure class the golden transcripts are blind to: a
    hard-coded 'W̃_0' renders identically to n.W(0), so every golden passes --
    but the symbol no longer answers to the Notation, and a re-notated
    renderer (LaTeX, ASCII) would silently emit the wrong thing for it. Only a
    source scan can catch it. (Seven such escapees survived the routing pass
    precisely because their goldens were byte-identical.)
    """
    import re
    from pathlib import Path

    raw = {
        r"W\\u0303": "W-tilde (use n.W(i))",
        r"\\u03c1": "rho (use n.rho(i))",
        r"\\u03b1": "alpha (use n.alpha(i))",
        r"\\u03c4": "tau (use n.tau(i))",
        r"\\u03b3": "gamma (use n.gamma())",
        r"\\u2113": "ell (use n.ell())",
        r"add\\u0303": "add-tilde (use n.add(i))",
        r"mult\\u0303": "mult-tilde (use n.mult(i))",
        r"q\*_": "q-star (use n.q(i, star=True))",
        r"z\*_": "z-star (use n.z_x(star=True) / n.z_y(star=True))",
        r"g\*_": "g-star (use n.g(j, star=True))",
    }
    src_dir = Path(__file__).resolve().parent.parent / "src" / "gkr" / "protocol"
    offenders = []
    for path in (src_dir / "sumcheck_render.py", src_dir / "gkr_render.py"):
        text = path.read_text(encoding="utf-8")
        in_docstring = False
        for lineno, line in enumerate(text.splitlines(), 1):
            if line.count('"""') == 1:
                in_docstring = not in_docstring
                continue
            if in_docstring or line.lstrip().startswith("#"):
                continue
            for pattern, advice in raw.items():
                if re.search(pattern, line):
                    offenders.append(f"{path.name}:{lineno}: hard-coded {advice}\n    {line.strip()[:100]}")
    assert not offenders, "notation must route through the Notation composers:\n" + "\n".join(offenders)


# ----------------------------------------------------------------------------
# Presentation mode: the secrets channel
# ----------------------------------------------------------------------------

def _child_env(**overrides) -> dict:
    """The same determinism settings the golden harness pins for its children.

    PYTHONHASHSEED in particular: without it, set-iteration order varies between
    runs and machines. A test that drives an interactive session through a fixed
    stdin script is exactly as order-sensitive as a golden transcript, so it
    needs the same environment.
    """
    import os
    env = {
        **os.environ,
        "PYTHONPATH": "src",
        "PYTHONHASHSEED": "0",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    env.update(overrides)
    return env


def _run_session(code: str, stdin: str, **env_overrides):
    import subprocess
    import sys
    from pathlib import Path
    return subprocess.run(
        [sys.executable, "-c", code],
        input=stdin, capture_output=True, text=True, encoding="utf-8",
        env=_child_env(**env_overrides),
        cwd=str(Path(__file__).resolve().parent.parent),
        timeout=300,
    )


# The prompts a user-prover session asks, in order. The stdin below has exactly
# one answer per prompt: a stray token shifts every later answer by one, and the
# run then desynchronises in a platform-dependent way rather than failing loudly.
#
#   1 interactive?  2 play prover?  3 play verifier?  4 prime  5 polynomial
#   6 claim H*      7 round 0 g*    8 round 1 g*      9 opening
_PROVER_STDIN = "y\ny\nn\n331\n2*X_0^2 + X_0 X_1\n7\ny\ny\na\n"


def test_secrets_channel_separates_prover_private_from_the_screen(tmp_path) -> None:
    """The presentation-mode property: with secrets_to=..., the shared screen
    carries no PROVER_PRIVATE narration (no true H, no cheat advice) and the
    secrets file carries exactly that -- while the ground-truth reveal, which is
    the audience's payoff, stays on the screen."""
    secrets = tmp_path / "prover.txt"
    code = (
        "import random; random.seed(9)\n"
        "from gkr import sum_check\n"
        f"print('RETURN:', sum_check(use_commitment=True, secrets_to=r'{secrets}'))"
    )
    # colour ON, so that the channel's ANSI-stripping is actually exercised
    proc = _run_session(code, _PROVER_STDIN, ZKNOTES_COLOR="always")
    assert "RETURN:" in proc.stdout, (
        "the session did not run to completion -- stdin is out of step with the "
        f"prompts:\n{proc.stdout[-600:]}\n{proc.stderr[-400:]}"
    )
    screen = proc.stdout
    channel = secrets.read_text(encoding="utf-8")

    # the screen: a neutral prompt, and no prover secrets
    assert "enter your claim H* for the value of H:" in screen
    assert "the true value is" not in screen.lower()
    for secret in ("In fact", "Your goal", "as many roots"):
        assert secret not in screen, f"secret leaked to the shared screen: {secret!r}"

    # the channel: the true H and the live cheat advice, colour stripped
    assert "The true value is H = 5." in channel
    assert "START INVISIBLE TO VERIFIER" in channel
    assert "\x1b[" in screen, "colour was expected on the screen for this run"
    assert "\x1b[" not in channel, "the secrets channel must strip ANSI"

    # the reveal is the audience's payoff: it belongs on the shared screen
    assert "GROUND TRUTH" in screen
    assert "GROUND TRUTH" not in channel


def test_prover_secret_mode_without_a_channel_is_refused() -> None:
    """The contradiction is refused rather than silently resolved one way."""
    proc = _run_session(
        "from gkr import sum_check; print('RETURN:', sum_check(secret_mode=True))",
        "y\ny\nn\n",
        ZKNOTES_COLOR="never",
    )
    assert "RETURN: None" in proc.stdout
    assert "nowhere" in proc.stdout and "secrets_to" in proc.stdout


def test_watch_follows_a_secrets_file_written_after_it_starts(tmp_path) -> None:
    """`gkr watch` is the second terminal, and it is normally started BEFORE the
    session that writes the file. So a file that did not exist when watching
    began must be shown from its first line: seeking to EOF (correct for a file
    left over from an earlier run) would silently swallow the very run you are
    there to watch.
    """
    import subprocess
    import sys
    import threading
    import time
    from pathlib import Path

    from gkr.protocol.secrets import SecretsChannel

    repo = Path(__file__).resolve().parent.parent
    secrets = tmp_path / "late.txt"
    watcher = subprocess.Popen(
        [sys.executable, "-m", "gkr._cli", "watch", str(secrets)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=_child_env(), cwd=str(repo),
    )

    # Drain stdout as lines arrive. Collecting only at the end via communicate()
    # would lose them: terminate() kills the child, and whatever had not yet
    # crossed the pipe goes with it.
    lines: list = []
    reader = threading.Thread(target=lambda: lines.extend(watcher.stdout), daemon=True)
    reader.start()

    try:
        # Handshake, not a sleep: the watcher announces itself on stderr once it
        # is polling. A fixed delay races interpreter start-up and fails on a
        # loaded machine -- which is how the eager-import regression in
        # gkr/__init__.py first showed up.
        ready = watcher.stderr.readline()
        assert "waiting for" in ready, f"watcher did not start: {ready!r}"

        channel = SecretsChannel(secrets)
        channel.print("The true value is H = 42.")
        channel.flush()

        deadline = time.time() + 10
        while time.time() < deadline and not any("H = 42." in line for line in lines):
            time.sleep(0.05)
        channel.close()
    finally:
        watcher.terminate()
        reader.join(timeout=5)
        watcher.wait(timeout=5)

    seen = "".join(lines)
    assert "The true value is H = 42." in seen, (
        "the watcher missed lines written after it attached; it must not seek to "
        f"EOF on a file it waited for. Saw: {seen!r}"
    )


def test_importing_the_package_does_not_load_the_world() -> None:
    """`import gkr` must stay cheap: the CLI defers its own imports so that
    `gkr --help` is instant, but `python -m gkr._cli` loads gkr/__init__ first,
    so an eager front door there is paid by every invocation. It also gets paid
    by every notebook cell that only wanted a name. Resolution is lazy (PEP 562).
    """

    code = (
        "import sys, gkr\n"
        "heavy = [m for m in ('sympy', 'networkx', 'graphviz', 'pydot') if m in sys.modules]\n"
        "print(','.join(heavy))"
    )
    proc = _run_session(code, "")
    loaded = proc.stdout.strip()
    assert loaded == "", f"`import gkr` eagerly loaded: {loaded}"

    # ...but the names still resolve
    proc = _run_session("from gkr import sum_check, ArithmeticCircuit; print('OK')", "")
    assert "OK" in proc.stdout, proc.stderr[-400:]


def test_gkr_secrets_channel_separates_prover_private_from_the_screen(tmp_path) -> None:
    """The same presentation-mode property as for sum_check, for GKR: with
    secrets_to=..., the shared screen carries no PROVER_PRIVATE narration (no
    true output value, no cheat advice) and the file carries exactly that.
    """
    secrets = tmp_path / "gkr_prover.txt"
    #    1 interactive  2 prover  3 verifier  4 claim W_0()  5..11 accept advice
    stdin = "y\ny\nn\n99\ny\ny\ny\ny\ny\ny\ny\ny\n"
    code = "\n".join([
        "import random; random.seed(4)",
        "from gkr import gkr",
        "from gkr.ac import ArithmeticCircuit",
        "ac = ArithmeticCircuit('(3*2) + (4 + 1)', prime=2**31 - 1)",
        f"print('RETURN:', gkr(ac, secrets_to=r'{secrets}'))",
    ])
    proc = _run_session(code, stdin, ZKNOTES_COLOR="always")
    assert "RETURN:" in proc.stdout, (
        f"the session did not run to completion:\n{proc.stdout[-500:]}\n{proc.stderr[-300:]}"
    )
    screen = proc.stdout
    channel = secrets.read_text(encoding="utf-8")

    assert "enter your claim for output gate" in screen
    for secret in ("The true value of W_0", "In fact", "INVISIBLE TO VERIFIER"):
        assert secret not in screen, f"secret leaked to the shared screen: {secret!r}"

    assert "The true value of W_0() is 11." in channel
    assert "INVISIBLE TO VERIFIER" in channel
    assert "\x1b[" not in channel, "the secrets channel must strip ANSI"


def test_gkr_prover_secret_mode_without_a_channel_is_refused() -> None:
    code = "\n".join([
        "from gkr import gkr",
        "from gkr.ac import ArithmeticCircuit",
        "ac = ArithmeticCircuit('(3*2) + (4 + 1)', prime=2**31 - 1)",
        "print('RETURN:', gkr(ac, secret_mode=True))",
    ])
    proc = _run_session(code, "y\ny\nn\n", ZKNOTES_COLOR="never")
    assert "RETURN: None" in proc.stdout
    assert "nowhere" in proc.stdout and "secrets_to" in proc.stdout


def test_gkr_example_runs_to_completion_without_any_input() -> None:
    """The notebooks' worked example must be readable, not playable: a reader
    runs the cell and reads. Both honesty settings run with stdin closed --
    `interactive` and `dishonest_claim` default to None ("ask"), and supplying
    them settles the question silently."""
    for dishonest, expected in [(False, "RETURN: True"), (True, "RETURN: False")]:
        code = "\n".join([
            "import random; random.seed(1)",
            "from gkr import gkr_example",
            f"print('RETURN:', gkr_example(dishonest={dishonest}))",
        ])
        proc = _run_session(code, "")          # no stdin at all
        assert expected in proc.stdout, (
            f"gkr_example(dishonest={dishonest}) did not complete:\n"
            f"{proc.stdout[-400:]}\n{proc.stderr[-300:]}"
        )
        assert "GROUND TRUTH" in proc.stdout, "a worked example must show the truth"


# ----------------------------------------------------------------------------
# The CLI's circuit and mle subcommands: notebooks 02 and 03 at the terminal
# ----------------------------------------------------------------------------

def _run_cli(*args: str):
    """Run the CLI in a child process with stdin closed: these subcommands must
    not prompt."""
    import subprocess
    import sys
    from pathlib import Path
    return subprocess.run(
        [sys.executable, "-m", "gkr._cli", *args],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
        env=_child_env(), cwd=str(Path(__file__).resolve().parent.parent), timeout=300,
    )


def test_cli_circuit_prints_the_notebook_tour() -> None:
    """`gkr circuit EXPR` reaches everything notebook 03 shows."""
    proc = _run_cli("circuit", "(3*2) + (4 + 1)")
    assert proc.returncode == 0, proc.stderr[-400:]
    for expected in (
        "TOPOLOGICAL ORDERING",
        "GATE VALUES",
        "MULTILINEAR EXTENSIONS OF GATE-VALUE FUNCTIONS",
        "ADDITION WIRING PREDICATES",
        "W_0() = 11",                       # the circuit really was evaluated
    ):
        assert expected in proc.stdout, f"missing section: {expected!r}"


def test_cli_circuit_show_selects_sections() -> None:
    proc = _run_cli("circuit", "(3*2) + (4 + 1)", "--show", "values")
    assert proc.returncode == 0, proc.stderr[-300:]
    assert "GATE VALUES" in proc.stdout
    assert "WIRING" not in proc.stdout, "--show values should not print the wiring"


def test_cli_circuit_refuses_an_unsuitable_circuit_but_explains_it() -> None:
    """The default refuses; --no-strict shows WHY, which is the pedagogy."""
    strict = _run_cli("circuit", "5*4+3")
    assert strict.returncode == 2
    assert "bottom layer" in strict.stderr
    assert "--no-strict" in strict.stderr, "a refusal should say how to learn more"

    loose = _run_cli("circuit", "5*4+3", "--no-strict", "--show", "values")
    assert loose.returncode == 0
    assert "not suitable for GKR" in loose.stdout
    assert "InputsNotAtBottom" in loose.stdout
    # a half-built circuit says so, without leaking an AttributeError
    assert "not available for this circuit" in loose.stderr
    assert "has no attribute" not in loose.stderr


def test_cli_circuit_pad_rescues_the_unsuitable_circuit() -> None:
    proc = _run_cli("circuit", "5*4+3", "--pad", "--show", "values")
    assert proc.returncode == 0, proc.stderr[-300:]
    assert "GATE VALUES" in proc.stdout
    assert "not suitable" not in proc.stdout


def test_cli_mle_builds_the_extension_and_its_array() -> None:
    proc = _run_cli("mle", "-p", "5", "--values", "1,2,3,4", "--array")
    assert proc.returncode == 0, proc.stderr[-300:]
    # f(00)=1, f(01)=2, f(10)=3, f(11)=4 over GF(5) extends to 2*x_0 + x_1 + 1
    assert "2*x_0 + x_1 + 1" in proc.stdout
    assert "EVALUATIONS OVER GF(5)^2" in proc.stdout
    assert "f(00) = 1" in proc.stdout
    assert "mod 5" not in proc.stdout, "sympy's ModularInteger repr should not leak"


def test_cli_mle_lagrange_agrees_with_the_direct_construction() -> None:
    """Two constructions of the same object: agreement is the uniqueness claim."""
    proc = _run_cli("mle", "-p", "5", "--values", "1,2,3,4", "--lagrange")
    assert proc.returncode == 0, proc.stderr[-300:]
    assert "The two constructions agree" in proc.stdout
    assert proc.stdout.count("2*x_0 + x_1 + 1") == 2, "both should give the same polynomial"


def test_cli_mle_rejects_bad_input_with_a_message_not_a_traceback() -> None:
    for args, expected in [
        (["mle", "-p", "5", "--values", "1,2,3"], "power of two"),
        (["mle", "-p", "5"], "either --values or --random"),
        (["mle", "-p", "5", "--random"], "needs -v"),
        (["mle", "-p", "5", "--values", "a,b"], "comma-separated list of integers"),
    ]:
        proc = _run_cli(*args)
        assert proc.returncode == 2, f"{args} should exit 2"
        assert expected in proc.stderr, f"{args}: expected {expected!r}"
        assert "Traceback" not in proc.stderr, f"{args} leaked a traceback"


def test_padding_levels_every_output_not_just_each_expression() -> None:
    """A circuit is only as shallow as its DEEPEST output. Padding each output
    against its own depth leaves a shallow output's inputs above the bottom
    layer, which is exactly what GKR refuses."""
    exprs = ("(1+2)*(3+4)", "(5+6)")          # depths 2 and 1

    with pytest.raises(CircuitError):
        ArithmeticCircuit(*exprs, prime=331)

    ac = ArithmeticCircuit(*exprs, prime=331, pad=True)
    assert ac.depth == 2
    assert len(ac.padding_notes) == 2, "both shallow inputs should be padded"
    # padding must not change what the circuit computes
    assert {k: int(v) for k, v in ac.W_dict[0].items()} == {(0,): 21, (1,): 11}


def test_cli_circuit_accepts_the_expression_however_the_shell_splits_it() -> None:
    """cmd.exe does not treat ' as a quote, so an expression can arrive in
    pieces, with stray quotes attached. All of these mean the same circuit."""
    for argv in (
        ["(3*2) + (4 + 1)"],                       # one properly quoted argument
        ["(3*2)", "+", "(4", "+", "1)"],           # unquoted, split by the shell
        ["'(3*2)", "+", "(4", "+", "1)'"],         # single-quoted under cmd.exe
    ):
        proc = _run_cli("circuit", *argv, "--show", "values")
        assert proc.returncode == 0, f"{argv}: {proc.stderr[-300:]}"
        assert "W_0() = 11" in proc.stdout, f"{argv} did not build the circuit"


def test_cli_circuit_splits_multiple_outputs_on_semicolons() -> None:
    proc = _run_cli("circuit", "(1+2)*(3+4); (5+6)", "--pad", "--show", "values")
    assert proc.returncode == 0, proc.stderr[-300:]
    assert "W_0(0) = 21" in proc.stdout
    assert "W_0(1) = 11" in proc.stdout