# Using `gkr`: command-line interface and notebook API

This is a guide to running the protocols yourself — from a terminal with the
`gkr` command, or from a notebook or script with the Python functions. It
covers the things that are not obvious from `--help`: the presentation
workflow, the exit-code contract, quoting on Windows, and how the command line
and the notebook API line up.

Every subcommand also has its own `gkr <command> --help` with a worked example
block. This document is the map; `--help` is the detail.

---

## The six subcommands at a glance

| Command | What it does | Notebook |
|---|---|---|
| `gkr sumcheck` (`sc`) | Run the sum-check protocol on a polynomial `g`. | 01 |
| `gkr gkr` | Run the GKR protocol on a layered arithmetic circuit. | 04 |
| `gkr circuit "<expr>"` | Build a circuit and print everything GKR needs from it. | 03 |
| `gkr mle -p <p> --values <list>` | Build the multilinear extension of a function on `{0,1}^v`. | 02 |
| `gkr example <name>` | Run a fixed worked example from the notes, no prompts. | — |
| `gkr watch <path>` | Follow a prover-secrets file (like `tail -f`). | — |

The four protocol/object commands mirror the four chapters of the
[book](https://tmfreiberg.github.io/sumcheck-gkr-notes/): reading the chapter
and running its command side by side is the intended way to use both.

---

## Playing a role

By default the two protocol commands are **interactive**: when you start a run,
you are asked who you want to be —

- **prover** — you supply the messages; the verifier is automated and checks
  you.
- **verifier** — you issue the challenges and decide accept/reject; the prover
  is automated.
- **both** — you play the whole conversation with yourself, which is the
  clearest way to see how the pieces fit.
- **neither** — sit back and watch an automated prover and verifier run the
  protocol, with every step narrated.

When you play the **prover**, you are asked whether to be **honest** or
**dishonest**. A dishonest prover starts from a false claim; the code then
suggests, at each round, a polynomial consistent with everything said so far,
so the protocol can proceed to the end — where the verifier will *almost
always* catch the lie in the final check. Over a small enough field it
occasionally does not, and you see a false claim accepted: that rare event is
the soundness error made concrete, not a bug.

## Seeing only what the verifier sees

The verifier does not know the prover's secrets — the true sum in sum-check, the
true output values in GKR, or the per-round cheat advice. The `--secret` /
`--no-secret` flag controls whether those prover-private quantities are printed:

- `--secret` renders only the verifier's view.
- `--no-secret` shows everything, including the ground-truth ledger and the
  cheat advice — useful when you are reading a run to understand it.

The default is adaptive: when you play the verifier alone, secrecy is **on**, so
the screen does not spoil the very thing you are trying to check. Otherwise it
is off.

---

## Presentation mode (two terminals)

You can play the prover in front of an audience on a shared screen without that
screen revealing what only the prover may know. The trick is to send the
prover-private material — the true sum and the per-round cheat advice — to a
file that only you can see on a second screen.

The cheat advice cannot be prepared in advance: it depends on the random
challenges the audience calls out during the run. So the second terminal is
genuinely live.

Start the watcher **first**, in a terminal only you can see:

```bash
gkr watch prover.txt          # waits for the file, then streams it
```

Then start the session on the shared screen:

```bash
gkr sumcheck -S prover.txt    # or: gkr gkr -C "(3*2)+(4+1)" -S prover.txt
```

The shared screen shows the verifier's view; everything prover-private is
appended to `prover.txt`, which scrolls up on your private screen as each round
happens.

`gkr watch` exists so this does not depend on having `tail` (Unix) or knowing
`Get-Content -Wait` (PowerShell); it behaves the same on every platform. By
default it starts at the end of the file, so a file left over from an earlier
run does not scroll its old secrets past you — pass `-a`/`--all` to print the
whole file first.

The same thing works from a notebook or script:

```python
from gkr import sum_check, gkr
sum_check(secrets_to="prover.txt")
gkr(some_circuit, secrets_to="prover.txt")
```

---

## Exit codes

The protocol commands report the verifier's verdict through the process exit
code, so runs can be scripted:

| Code | Meaning |
|---|---|
| `0` | the verifier **accepted** |
| `1` | the verifier **rejected** |
| `2` | the run was **aborted** — cancelled, or invalid input |

An honest run exits `0`; a dishonest run that gets caught exits `1`; a dishonest
run that slips through (the rare false positive) exits `0`, because from the
verifier's side it *was* an accept. Aborting a prompt with Ctrl-C, or giving
input that cannot be parsed, exits `2`.

---

## Reproducible runs

`--seed N` seeds the random number generator. The same seed and the same
answers reproduce a run exactly — the same challenges, the same automated
choices. This is what the golden-transcript tests rely on, and it is useful for
sharing or re-examining a particular run:

```bash
gkr gkr --seed 1 --no-secret         # a fully-shown, reproducible GKR run
```

---

## Saving the proof

`-t PATH` / `--transcript PATH` writes the public transcript — the prover's
messages and the verifier's challenges, i.e. the *proof* — as JSON. This is the
object a non-interactive verifier would check, separated from the narration:

```bash
gkr sumcheck -c -t proof.json        # run with the toy commitment, save the proof
```

---

## `gkr circuit`: inspecting a circuit

`gkr circuit "<expr>"` builds the arithmetic circuit for an expression and
prints what GKR needs from it: the gate values, the layer multilinear
extensions `W̃_i`, the wiring predicates and their MLEs, and the verification
propagation equation. With no `--show`, it prints everything.

```bash
gkr circuit "(3*2) + (4 + 1)"              # the whole tour
gkr circuit "(3*2)+(4+1)" --show values    # just the gate values
gkr circuit "(1+2)*(3+4); (5+6)" --pad     # a multi-output circuit
gkr circuit "(3*2)+(4+1)" --view           # also open the circuit diagram
```

`--show` takes any of: `topology`, `values`, `mles`, `wiring`, `wiring-mles`,
`propagation`, `propagation-mle`, or `all`.

### Seeing *why* a circuit is unsuitable

GKR needs a layered circuit whose inputs all sit at the bottom layer, with fan-in
two and gates that are all `+` or `×`. By default `gkr circuit` **refuses** a
circuit that violates this and tells you what is wrong. `--no-strict` instead
builds as far as it can and reports the problems, so you can see the diagnosis:

```bash
gkr circuit "5*4+3" --no-strict            # WHY this one is unsuitable
gkr circuit "x+1"  --no-strict             # ...and this one (symbolic inputs)
```

`--pad` (on both `circuit` and `gkr`) inserts trivial multiplications by 1 so
that shallow inputs are pushed down to the bottom layer, which is often what a
circuit needs to become GKR-suitable.

---

## `gkr mle`: multilinear extensions

`gkr mle` builds the multilinear extension of a function given by its values on
the Boolean hypercube `{0,1}^v`, listed in lexicographic order of the
bitstrings. The number of variables is inferred from the number of values (which
must be a power of two):

```bash
gkr mle -p 5 --values 1,2,3,4              # f(00)=1, f(01)=2, f(10)=3, f(11)=4
gkr mle -p 5 --values 1,2,3,4 --array      # ...and its values over all of GF(5)^2
gkr mle -p 11 -v 3 --random --seed 1       # a random function on {0,1}^3
gkr mle -p 5 --values 1,2,3,4 --lagrange   # build it twice, two ways, and compare
```

`--array` shows how the extension behaves *off* the hypercube — the whole point
of the construction. `--lagrange` builds the same object a second way (via the
Lagrange basis) and checks the two agree, which is a check on the uniqueness
that characterises the MLE.

---

## `gkr example`: fixed worked examples

`gkr example <name>` runs one of the worked examples from the notes with no
prompts — handy for a quick look, and the same code paths the book executes:

```bash
gkr example sumcheck       # a full sum-check run
gkr example gkr            # a full GKR run
gkr example roots          # counting roots / Schwartz–Zippel
gkr example total-degree   # total degree of a polynomial
gkr example mle            # a multilinear extension
```

---

## Quoting expressions (read this on Windows)

Use **double** quotes around circuit expressions. `cmd.exe` does not treat `'`
as a quote character, so single quotes arrive as part of the expression — or
split it into pieces. The `circuit` and `gkr` commands defensively rejoin split
pieces and strip stray quotes, so in practice all of these work:

```bash
gkr circuit "(3*2) + (4 + 1)"      # recommended
gkr circuit (3*2) + (4 + 1)        # rejoined
gkr circuit '(3*2) + (4 + 1)'      # stray quotes stripped
```

But `"..."` is the form to rely on, especially if an expression contains
characters your shell would otherwise interpret.

---

## Colour

`--color auto|always|never` controls colourised output; the default is `auto`
(colour when writing to a terminal, plain when redirected to a file or pipe).
The environment variable `GKR_COLOR` does the same globally, which is what the
book's automated build sets to `never` for clean, monochrome cell output.

---

## The notebook / script API

Everything above is also available as plain Python, which is how the notebooks
drive it. The functions keep the substantive logic; the notebooks and the CLI
are thin surfaces over them.

```python
from gkr import (
    sum_check,                    # run sum-check (interactive by default)
    gkr,                          # run GKR
    ArithmeticCircuit,            # build and inspect a circuit
    multilinear_extension,        # MLE via the tilde-beta construction
    multilinear_extension_using_lagrange_basis,   # ...and via the Lagrange basis
    evaluation_array,             # MLE values over the whole field
)

# A circuit, built directly:
circuit = ArithmeticCircuit("(3*2) + (4 + 1)", prime=331)

# Run GKR on it, sending prover-private output to a file (presentation mode):
gkr(circuit, secrets_to="prover.txt")

# Run sum-check with the toy commitment and save the proof:
sum_check(use_commitment=True, save_transcript="proof.json")
```

The worked examples are functions too, and take parameters so they can run
non-interactively (which is how the book executes them at build time):

```python
from gkr import (
    sum_check_example,
    gkr_example,
    roots_example,
    total_degree_example,
    multilinear_extension_example,
)

gkr_example()                     # honest run
gkr_example(dishonest=True)       # dishonest run, caught at the end
```

The keyword arguments that make these run without prompts — `interactive`,
`scenario`, `examples`, `polynomials`, `secrets_to`, `use_commitment`,
`save_transcript` — are documented in the function docstrings and demonstrated
throughout the book's executable cells.