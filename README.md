# Sum-check and GKR notes

## 📖 [Read the book → tmfreiberg.github.io/sumcheck-gkr-notes](https://tmfreiberg.github.io/sumcheck-gkr-notes)

**The rendered book is the main event.** These are interactive, executable notes
on the **sum-check protocol**, **multilinear extensions**, **arithmetic
circuits**, and the **Goldwasser–Kalai–Rothblum (GKR) protocol** — with every
theorem numbered and cross-linked, every citation resolved, and every worked
example run live so you can read the actual output. Start there.

> The `.md` files in this repository are the *source*. They render as plain
> markup on GitHub; the [book site](https://tmfreiberg.github.io/sumcheck-gkr-notes)
> is where they display properly.

These notes are for people *learning* sum-check and GKR who want each step
spelled out in detail. The emphasis is on _understanding_, _derivation_, and
_mechanism_ rather than on performance or production engineering: **why these
protocols work**, how their guarantees arise, and how complexity and soundness
behave in concrete examples.

The exposition follows Justin Thaler's presentation in his book
[_Proofs, Arguments, and Zero-Knowledge_](https://people.cs.georgetown.edu/jthaler/ProofsArgsAndZK.pdf)
(Foundations and Trends in Privacy and Security, Now Publishers, 2022),
supplemented with additional background, full proofs, and interactive examples.

They come with a companion Python package (`gkr`) that turns the protocols into
something you can *play*. In the book, at a Jupyter notebook, or from the command
line, you can take the role of the **prover**, the **verifier**, or neither and
just watch — with each round narrated as it happens: the polynomials sent, the
checks performed, the random challenges drawn, and (when you play a *dishonest*
prover) exactly where the lie is caught, or, over a small enough field, the rare
occasion it slips through. See the
[worked examples in the book](https://tmfreiberg.github.io/sumcheck-gkr-notes)
and the [command-line interface](#command-line-interface) below.

This project is best thought of as a set of **working notes with executable
examples**, not as a textbook or a cryptographic framework.

## What this repository is (and is not)

**It is:**

- A mathematically precise, implementation-adjacent explanation of sum-check and
  GKR
- Interactive demonstrations designed to make abstract arguments concrete
- Small-scale code intended for experimentation and pedagogy
- Focused on clarity, structure, and correctness

**It is not:**

- A production-ready prover or verifier
- A performance-optimized implementation
- A substitute for peer-reviewed protocol specifications

## Current notebook topics

The notebooks currently cover (but are not limited to):

- **Sum-check protocol**
  - Correctness, soundness, and error bounds
  - Degree tracking and verifier efficiency
  - Explicit examples over finite fields

- **Multilinear extensions**
  - Boolean hypercubes and interpolation
  - Why multilinearity is essential in interactive proofs

- **Arithmetic circuits**
  - Circuits as structured polynomials
  - Gate labeling, wiring predicates, and propagation identities

- **GKR protocol**
  - High-level structure and intuition
  - How sum-check is used layer-by-layer
  - Folding and claim reduction
  - Completeness, and a proof of the soundness error bound, with the union
    bound checked against Monte Carlo over a deliberately tiny field

The scope may expand over time as additional related topics become relevant.

## Installation

The project is packaged as a standard Python package so that the notebooks can
focus on mathematics rather than setup code.

Python **3.10 or later** is required. The only **system-level dependency** is
**Graphviz**, which is required for circuit and protocol visualizations.

### 1. System prerequisite: Graphviz

Graphviz must be installed at the OS level.

#### macOS

```bash
brew install graphviz

```

#### Linux (Debian / Ubuntu)

```bash
sudo apt update
sudo apt install graphviz
```

#### Windows

1. Download Graphviz from:
   [https://graphviz.org/download/](https://graphviz.org/download/)
2. Install it and ensure the `dot` executable is added to your `PATH`
3. Verify installation:

```powershell
dot -V
```

### 2. Create a Python environment (recommended)

You can use either **conda** or **pip + venv**. Conda is recommended if you want
a fully reproducible environment.

#### Option A: Conda (recommended)

```bash
conda env create -f environment.yaml
conda activate gkr
```

#### Option B: pip + venv

```bash
# Create a virtual environment
python -m venv .venv
```

Activate it:

- **Windows (PowerShell)**

  ```powershell
  .venv\Scripts\Activate.ps1
  ```

- **macOS / Linux**

  ```bash
  source .venv/bin/activate
  ```

### 3. Install the package (editable mode)

From the project root:

```bash
pip install -e .
```

Editable mode (`-e`) ensures that changes to the source code are immediately
reflected in notebooks and scripts without reinstallation.

#### Optional extras

- Notebook support (recommended):

  ```bash
  pip install -e ".[notebook]"
  ```

- Colored terminal output (nice to have):

  ```bash
  pip install -e ".[colors]"
  ```

- Everything:

  ```bash
  pip install -e ".[notebook,colors]"
  ```

- Development tools (pytest, ruff, mypy) — only needed to run the test suite:

  ```bash
  pip install -e ".[dev]"
  ```

### 4. Read the notes

The rendered book lives at
**[tmfreiberg.github.io/sumcheck-gkr-notes](https://tmfreiberg.github.io/sumcheck-gkr-notes)**
and needs nothing installed to read. To run the material yourself — editing
examples, trying your own polynomials and circuits — launch Jupyter:

```bash
jupyter notebook
```

or, if you prefer:

```bash
jupyter lab
```

The notebooks can import the package directly; no additional initialization is
required.

### Notes

- Visualization features depend on Graphviz being available on your system. If
  you encounter rendering errors, verify that `dot` is accessible from the
  command line.

## Command-line interface

Everything the notebooks show can also be run from a terminal, via the `gkr`
command installed with the package:

```bash
gkr sumcheck                          # run the sum-check protocol
gkr gkr                               # run the GKR protocol
gkr circuit "(3*2) + (4 + 1)"         # build an arithmetic circuit and inspect it
gkr mle -p 5 --values 1,2,3,4         # build a multilinear extension
gkr example gkr                       # a complete worked example, no prompts
gkr watch prover.txt                  # follow a prover-secrets file (see below)
```

Each subcommand has its own `--help` with examples. By default the protocols are
interactive: you can play the prover, the verifier, or neither and watch. A few
flags worth knowing:

```bash
gkr sumcheck -c                       # use the toy polynomial commitment
gkr gkr -C "(1+2)*(3+4); (5+6)" --pad # a given circuit; --pad levels the layers
gkr gkr -t proof.json                 # write the public transcript (the proof) as JSON
gkr circuit "5*4+3" --no-strict       # see WHY a circuit is unsuitable for GKR
gkr mle -p 5 --values 1,2,3,4 --array # ...and its values over all of GF(5)^2
```

Quote expressions with **double** quotes: `cmd.exe` does not treat `'` as a
quote character.

### Presentation mode

You can play the prover in front of an audience without the shared screen
revealing what only the prover may know — the true sum, and the per-round cheat
advice, which depends on the challenges the audience has just called out and so
cannot be prepared in advance.

Run the watcher in a second terminal that only you can see:

```bash
gkr watch prover.txt                  # start this FIRST; it waits for the file
```

and the session in the first:

```bash
gkr sumcheck -S prover.txt            # or: gkr gkr -S prover.txt
```

The shared screen shows the verifier's view; everything prover-private is
appended to `prover.txt` instead. The same works from a notebook or script via
`sum_check(secrets_to="prover.txt")` and `gkr(secrets_to="prover.txt")`.

## Development

The test suite pins both the mathematics and the narration:

```bash
pip install -e ".[dev]"
pytest                                # 83 tests; a few minutes
ruff check .
mypy src/gkr
```

- `tests/test_golden.py` compares 18 recorded sessions against
  `tests/golden/transcripts/*.golden.txt`, **byte for byte**.
- `tests/test_invariants.py` checks protocol properties (completeness,
  soundness, the audience routing, the narrated soundness bound) rather than
  fixed output.
- `tests/test_transcript.py` cross-checks the JSON proof against the narration.
- `tests/test_circuits.py` pins the arithmetic-circuit layer.

**The golden transcripts are generated artifacts.** When a change to the
narration is intentional, review the diff and then re-record them:

```bash
python tests/golden/harness.py --bless               # all scenarios
python tests/golden/harness.py --bless NAME [NAME…]  # just these
```

Never edit a golden file by hand — a hand-copied file loses its trailing newline
and produces a baffling diff. Note also that `tests/golden/transcripts/` is
covered by a `.gitattributes` rule that disables line-ending normalization; the
byte-for-byte comparison depends on it.

## Provenance and attribution

Portions of this project were originally developed while the author was employed
at Inference Labs Inc., and an earlier version of the work lived in the
repository:
[https://github.com/inference-labs-inc/n-ary_notebooks](https://github.com/inference-labs-inc/n-ary_notebooks).

The material here has since been reorganized, extended, and maintained
independently as a personal educational project. The original repository was
released under the MIT License, and this repository remains MIT-licensed as
well.

This repository is not affiliated with or endorsed by Inference Labs Inc.

## License

This project is released under the _MIT License_. See the `LICENSE` file at the
repository root for full terms.