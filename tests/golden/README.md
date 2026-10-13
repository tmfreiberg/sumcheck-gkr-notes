# Golden-transcript harness

The interactive transcripts *are* the product of this project. This harness
freezes them: every scenario below runs a full protocol in a fresh subprocess
with pinned randomness and canned stdin, and compares the captured output
byte-for-byte against a blessed transcript in `transcripts/`.

These tests tell you immediately whether behavior or narration drifted, and
*you* decide when a change is intentional, by re-blessing.

## Quickstart

From the repository root:

    pytest tests/ -q                          # run everything (goldens + determinism)
    python tests/golden/harness.py --list     # show the scenario matrix
    python tests/golden/harness.py --run NAME # watch one scenario (ANSI made readable)
    python tests/golden/harness.py --check    # like pytest, but standalone
    python tests/golden/harness.py --bless    # regenerate ALL goldens
    python tests/golden/harness.py --bless NAME [NAME ...]   # regenerate some

On Windows, `py` in place of `python` works the same; run from the repo root.

## How determinism is achieved

The harness sets, in the child process only (you don't need to set anything):

- `random.seed(<scenario seed>)` — machine choices: verifier challenges,
  dishonest claims, coin flips, forged-value fallbacks.
- `PYTHONHASHSEED=0` — set-iteration order during circuit construction.
- `GKR_COLOR=always` — ANSI colors are captured, so the color semantics
  (green = true, red = lie, yellow = aside, purple = header) are protected too.
- `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8` — Windows-safe unicode (W̃, α, ρ, τ).

It also depends on `src/gkr/ac.py` naming circuit nodes deterministically
("n0", "n1", ... in first-visit order). Before this, node names were memory
addresses, so the *bitstring labels assigned to gates permuted from run to
run* — reproducibility was impossible, and "gate (0,1)" meant a different gate
each time you ran the same circuit.

## Workflow

1. Change the code.
2. `pytest tests/ -q`.
3. A failing golden shows a unified diff with ANSI rendered as `⟨RED⟩`,
   `⟨GREEN⟩`, etc. If the change is a bug — fix it. If it's intentional —
   `--bless` that scenario and commit the new golden; the git diff of the
   transcript *is* the review artifact for the narration change.

`versions.json` records the Python and SymPy versions at blessing time.
SymPy version bumps can change expression string forms; the pytest run warns
(without failing) when your versions differ from the blessed ones, so you can
re-bless rather than chase phantom regressions.

The repository's `.gitattributes` keeps the goldens byte-stable on every
checkout with this line; keep it whatever else changes there:

    tests/golden/transcripts/*.golden.txt -text

## Adding a scenario

Append a `Scenario` to `SCENARIOS` in `harness.py`: a name, the stdin script
(one line per prompt; surplus lines are harmless for variable-length prompt
sequences), a seed, the driver code binding `res`, and the expected return
value. Then `--bless` it. The bless step refuses to write a golden whose run
crashed or whose return value doesn't match `expect`, so a wrong seed is
caught at bless time rather than silently frozen.
