# Sum-check and GKR notebooks

This repository contains a collection of **interactive mathematical notebooks**
explaining the **sum-check protocol**, **multilinear extensions**, **arithmetic
circuits**, and the **Goldwasser–Kalai–Rothblum (GKR) protocol**.

The emphasis is on _understanding_, _derivation_, and _mechanism_ rather than on
performance, production engineering, or system integration. The material is
intended for readers who want to see **why these protocols work**, how their
guarantees arise, and how complexity and soundness behave in concrete examples.

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

The scope may expand over time as additional related topics become relevant.

## Installation

The project is packaged as a standard Python package so that the notebooks can
focus on mathematics rather than setup code.

The only **system-level dependency** is **Graphviz**, which is required for
circuit and protocol visualizations.

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

### 4. Launch Jupyter

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

- The package also installs a small CLI entry point:

  ```bash
  gkr
  ```

  (This will expand over time.)

- Visualization features depend on Graphviz being available on your system. If
  you encounter rendering errors, verify that `dot` is accessible from the
  command line.

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
