"""
Command-line interface: `gkr sumcheck`, `gkr gkr`, `gkr example`.

Import discipline: every `gkr.*` import in this module is deferred into the
functions below. `gkr.utils.display` snapshots the colour palette at import
time (`_colors = get_colors()` at module level), so `--color` must reach the
environment before anything imports it. Importing lazily also keeps
`gkr --help` fast: it never loads sympy.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Callable, Dict, List, Optional, Tuple

__all__ = ["main"]

DEFAULT_PRIME = 331

CIRCUIT_EPILOG = """\
examples:
  gkr circuit "(3*2) + (4 + 1)"              the whole tour: values, MLEs, wiring, propagation
  gkr circuit "(3*2) + (4 + 1)" --view       ...and open the circuit diagram
  gkr circuit "(1+2)*(3+4); (5+6)" --pad     a multi-output circuit (--pad levels them)
  gkr circuit "(3*2)+(4+1)" --show values    just the gate values
  gkr circuit "5*4+3" --no-strict            see WHY this one is unsuitable for GKR
  gkr circuit "x+1" --no-strict              ...and this one (symbolic inputs)

quoting:
  Use DOUBLE quotes. cmd.exe does not treat ' as a quote character, so single
  quotes arrive as part of the expression -- or split it into pieces. This
  command rejoins the pieces and strips stray quotes, so all of these work:
      gkr circuit "(3*2) + (4 + 1)"
      gkr circuit (3*2) + (4 + 1)
      gkr circuit '(3*2) + (4 + 1)' 
"""

MLE_EPILOG = """\
examples:
  gkr mle -p 5 --values 1,2,3,4              the MLE of f(00)=1, f(01)=2, f(10)=3, f(11)=4
  gkr mle -p 5 --values 1,2,3,4 --array      ...and its values over all of GF(5)^2
  gkr mle -p 11 -v 3 --random --seed 1       a random function on {0,1}^3
  gkr mle -p 5 --values 1,2,3,4 --lagrange   build it twice, two ways, and compare

note:
  The MLE agrees with f on {0,1}^v and is the UNIQUE multilinear polynomial
  that does; --array shows how it behaves off the hypercube.
"""

EPILOG = """\
exit codes:
  0  the verifier accepted
  1  the verifier rejected
  2  the run was aborted (cancelled, or invalid input)

examples:
  gkr sumcheck                        run the sum-check protocol (prompts for g)
  gkr sumcheck -c -t proof.json       use the toy commitment; save the proof
  gkr sumcheck -S prover.txt          presentation mode: prover secrets go to a file
  gkr watch prover.txt                ...and, in a SECOND terminal, watch them arrive
  gkr gkr -C "(3*2) + (4 + 1)"        run GKR on a given circuit, no prompt
  gkr gkr -C "(1+2)*(3+4); (5+6)+(7*8)"  a multi-output circuit
  gkr gkr --seed 1 --no-secret        a reproducible run, everything shown
  gkr gkr -C "(3*2)+(4+1)" -S p.txt   presentation mode (watch p.txt in a second terminal)
  gkr circuit "(3*2) + (4 + 1)"       build a circuit and inspect it
  gkr mle -p 5 --values 1,2,3,4       build a multilinear extension
  gkr example roots                   a worked example from the notes
"""


def _version() -> str:
    try:
        from importlib.metadata import version

        return version("gkr")
    except Exception:  # not installed (e.g. run from a source checkout)
        return "0.1.0+source"


def _add_common(parser: argparse.ArgumentParser) -> None:
    """Flags shared by the protocol subcommands."""
    parser.add_argument(
        "-t", "--transcript", metavar="PATH",
        help="save the proof (prover messages + verifier challenges) as JSON",
    )
    parser.add_argument(
        "--seed", type=int, metavar="N",
        help="seed the RNG: the same seed and the same answers reproduce a run exactly",
    )
    parser.add_argument(
        "--secret", action=argparse.BooleanOptionalAction, default=None,
        help="render only the verifier's view (default: on when you play verifier alone)",
    )
    parser.add_argument(
        "--color", choices=["auto", "always", "never"], default=None,
        help="colourise output (default: auto, i.e. when writing to a terminal)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gkr",
        description="Interactive sum-check and GKR protocols, for the notes.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-V", "--version", action="version", version=f"gkr {_version()}")
    sub = parser.add_subparsers(dest="cmd", required=True, metavar="<command>")

    # -- sumcheck ------------------------------------------------------------
    p_sc = sub.add_parser(
        "sumcheck", aliases=["sc"],
        help="run the sum-check protocol",
        description=(
            "Run the sum-check protocol on a multivariate polynomial g over a prime "
            "field. You will be prompted for g (or accept the default), and for who "
            "you want to play: prover, verifier, both, or neither."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_sc.add_argument(
        "-S", "--secrets-to", metavar="PATH", dest="secrets_to",
        help=(
            "presentation mode: you play prover at a shared screen; the true H and "
            "the cheat advice are appended to PATH instead (watch it with tail -f)"
        ),
    )
    p_sc.add_argument(
        "-c", "--commitment", action="store_true",
        help="use the toy polynomial commitment (P commits to g, opens it at the end)",
    )
    _add_common(p_sc)

    # -- gkr -----------------------------------------------------------------
    p_gkr = sub.add_parser(
        "gkr",
        help="run the GKR protocol",
        description=(
            "Run the GKR protocol on a layered arithmetic circuit. Without --circuit "
            "you will be prompted for one. Separate multiple outputs with ';'. Every "
            "input must sit at the bottom layer: pad with '(3 + 0)' or '(3*1)' if "
            "necessary."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_gkr.add_argument(
        "-C", "--circuit", action="append", metavar="EXPR",
        help="circuit expression, e.g. '(3*2) + (4 + 1)'; repeatable, or ';'-separated",
    )
    p_gkr.add_argument(
        "--pad", action="store_true",
        help="pad shallow inputs with multiplications by 1 so every input sits at the bottom layer",
    )
    p_gkr.add_argument(
        "-p", "--prime", type=int, default=DEFAULT_PRIME, metavar="P",
        help=f"order of the prime field (default: {DEFAULT_PRIME}); only used with --circuit",
    )
    p_gkr.add_argument(
        "-S", "--secrets-to", metavar="PATH", dest="secrets_to",
        help=(
            "presentation mode: you play prover at a shared screen; the true output "
            "values and the cheat advice are appended to PATH ('gkr watch PATH' in a "
            "second terminal)"
        ),
    )
    _add_common(p_gkr)

    # -- watch ---------------------------------------------------------------
    # ------------------------------------------------------------------ circuit
    p_circuit = sub.add_parser(
        "circuit",
        help="build an arithmetic circuit and inspect it",
        description=(
            "Build the arithmetic circuit for an expression and print what the "
            "GKR protocol needs from it: gate values, the layer MLEs W-tilde_i, "
            "the wiring predicates and their MLEs, and the verification "
            "propagation equation. This is notebook 03 at the command line."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=CIRCUIT_EPILOG,
    )
    p_circuit.add_argument(
        "expression", metavar="EXPR", nargs="+",
        help=(
            'an arithmetic expression, e.g. "(3*2) + (4 + 1)"; separate multiple '
            "outputs with ';'. Quote it, or don't: cmd.exe does not treat ' as a "
            "quote, so the pieces are rejoined either way"
        ),
    )
    p_circuit.add_argument(
        "-p", "--prime", type=int, default=DEFAULT_PRIME, metavar="P",
        help=f"order of the prime field (default: {DEFAULT_PRIME})",
    )
    p_circuit.add_argument(
        "--pad", action="store_true",
        help="pad the circuit so every layer has a power-of-two width",
    )
    p_circuit.add_argument(
        "--show", nargs="+", metavar="SECTION",
        choices=["values", "mles", "wiring", "wiring-mles", "propagation",
                 "propagation-mle", "topology", "all"],
        default=["all"],
        help=(
            "which sections to print: values, mles, wiring, wiring-mles, "
            "propagation, propagation-mle, topology, all (default: all)"
        ),
    )
    p_circuit.add_argument(
        "--view", action="store_true",
        help="also render the circuit graph and open it in the default viewer",
    )
    p_circuit.add_argument(
        "--format", default="svg", metavar="FMT",
        help="image format for --view (default: svg)",
    )
    p_circuit.add_argument(
        "--strict", action=argparse.BooleanOptionalAction, default=True,
        help=(
            "--no-strict builds as much as possible and reports what is wrong, "
            "instead of refusing; use it to see WHY a circuit is unsuitable for GKR"
        ),
    )
    p_circuit.add_argument(
        "--color", choices=["auto", "always", "never"], default=None,
        help="colour output (default: auto)",
    )

    # ---------------------------------------------------------------------- mle
    p_mle = sub.add_parser(
        "mle",
        help="build the multilinear extension of a function on {0,1}^v",
        description=(
            "Build the multilinear extension of a function given by its values "
            "on the Boolean hypercube {0,1}^v, and optionally show its "
            "evaluations over the whole of GF(p)^v. This is notebook 02 at the "
            "command line."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=MLE_EPILOG,
    )
    p_mle.add_argument(
        "-p", "--prime", type=int, required=True, metavar="P",
        help="order of the prime field",
    )
    p_mle.add_argument(
        "--values", metavar="LIST",
        help=(
            "comma-separated values of f on {0,1}^v in lexicographic order of "
            "the bitstrings, e.g. '1,2,3,4' for v=2 gives f(00)=1, f(01)=2, "
            "f(10)=3, f(11)=4"
        ),
    )
    p_mle.add_argument(
        "-v", "--variables", type=int, metavar="V",
        help="number of variables (inferred from --values if omitted)",
    )
    p_mle.add_argument(
        "--random", action="store_true",
        help="use random values on the hypercube (requires -v)",
    )
    p_mle.add_argument(
        "--array", action="store_true",
        help="also print the evaluations over all of GF(p)^v",
    )
    p_mle.add_argument(
        "--lagrange", action="store_true",
        help="build it via the Lagrange basis as well, and check the two agree",
    )
    p_mle.add_argument(
        "--seed", type=int, metavar="N",
        help="seed the RNG for --random",
    )
    p_mle.add_argument(
        "--color", choices=["auto", "always", "never"], default=None,
        help="colour output (default: auto)",
    )

    p_watch = sub.add_parser(
        "watch",
        help="follow a secrets file written by 'sumcheck -S' (like tail -f)",
        description=(
            "Follow a prover-secrets file as it is written. Run this in a SECOND "
            "terminal -- one you can see and your audience cannot -- while the "
            "session itself runs in the first. Waits for the file to appear, then "
            "prints each line as it arrives. Ctrl-C to stop.\n\n"
            "This exists so the feature does not depend on having 'tail' (Unix) or "
            "knowing 'Get-Content -Wait' (PowerShell): it is the same on every platform."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_watch.add_argument("path", metavar="PATH", help="the file passed to 'sumcheck -S'")
    p_watch.add_argument(
        "-a", "--all", action="store_true",
        help="print the whole file first (default: only lines written from now on)",
    )

    # -- example -------------------------------------------------------------
    p_ex = sub.add_parser(
        "example",
        help="run a worked example from the notes",
        description="Run one of the worked examples from the notebooks.",
    )
    p_ex.add_argument(
        "which", choices=["sumcheck", "gkr", "roots", "total-degree", "mle"],
        help="which example to run",
    )
    p_ex.add_argument(
        "--color", choices=["auto", "always", "never"], default=None,
        help="colourise output (default: auto)",
    )
    p_ex.add_argument("--seed", type=int, metavar="N", help="seed the RNG")

    return parser


def _apply_environment(args: argparse.Namespace) -> None:
    """Colour must be set before any gkr import; the seed only before a run."""
    color = getattr(args, "color", None)
    if color is not None:
        os.environ["ZKNOTES_COLOR"] = color
    seed = getattr(args, "seed", None)
    if seed is not None:
        import random

        random.seed(seed)


def _exit_code(result: Optional[bool]) -> int:
    if result is None:
        return 2
    return 0 if result else 1


def _run_sumcheck(args: argparse.Namespace) -> int:
    from .protocol.sumcheck_session import sum_check

    result = sum_check(
        use_commitment=args.commitment,
        secret_mode=args.secret,
        secrets_to=args.secrets_to,
        save_transcript=args.transcript,
    )
    return _exit_code(result)


def _run_gkr(args: argparse.Namespace) -> int:
    from .protocol.gkr_session import gkr

    ac = None
    if args.circuit:
        from .ac import ArithmeticCircuit, CircuitError

        exprs: List[str] = []
        for chunk in args.circuit:
            exprs.extend(part.strip() for part in chunk.split(";") if part.strip())
        if not exprs:
            print("error: --circuit was empty", file=sys.stderr)
            return 2
        from .utils.display import progress

        try:
            with progress(
                "\nBuilding the circuit, its wiring predicates, and their multilinear "
                "extensions. For larger circuits this can take a minute..."
            ):
                ac = ArithmeticCircuit(*exprs, prime=args.prime, pad=args.pad)
            for note in ac.padding_notes:
                print(f"  {note}")
        except CircuitError as e:
            print(f"error: {e}.", file=sys.stderr)
            if e.hint:
                print(f"\n{e.hint}", file=sys.stderr)
            return 2
        except Exception as e:
            print(f"error: could not build the circuit: {e}", file=sys.stderr)
            return 2

    result = gkr(ac, secret_mode=args.secret, secrets_to=args.secrets_to,
                 save_transcript=args.transcript)
    return _exit_code(result)


def _run_watch(args: argparse.Namespace) -> int:
    """Follow a file, like `tail -f` / `Get-Content -Wait`, in pure Python.

    Polls rather than using platform notification APIs: the file is tiny, the
    reader is a human, and 200ms is imperceptible. Starts at EOF by default so a
    file left over from an earlier run does not scroll its secrets past you.
    """
    import time
    from pathlib import Path

    path = Path(args.path)
    existed = path.exists()
    if not existed:
        print(f"waiting for {path} ...", file=sys.stderr)
        while not path.exists():
            time.sleep(0.2)

    with open(path, "r", encoding="utf-8") as fh:
        # Skip to the end only if the file was ALREADY there when we started --
        # i.e. it may hold secrets from an earlier run that should not scroll
        # past. If we waited for it to appear, every line in it belongs to the
        # run we are here to watch, including the ones written in the moment
        # between the file appearing and this open().
        if existed and not args.all:
            fh.seek(0, 2)
        while True:
            line = fh.readline()
            if line:
                sys.stdout.write(line)
                sys.stdout.flush()
            else:
                time.sleep(0.2)


def _run_example(args: argparse.Namespace) -> int:
    from .examples import (
        gkr_example,
        multilinear_extension_example,
        roots_example,
        sum_check_example,
        total_degree_example,
    )

    table: Dict[str, Callable[[], object]] = {
        "sumcheck": sum_check_example,
        "gkr": gkr_example,
        "roots": roots_example,
        "total-degree": total_degree_example,
        "mle": multilinear_extension_example,
    }
    table[args.which]()
    return 0


def _run_circuit(args: argparse.Namespace) -> int:
    from .ac import ArithmeticCircuit
    from .errors import CircuitError
    from .utils.display import out

    # A shell may hand us the expression in pieces: cmd.exe does not treat ' as
    # a quote character, so "gkr circuit '(3*2) + (4 + 1)'" arrives as five
    # arguments with stray quotes on the ends. Rejoin, then strip any quote the
    # shell left behind.
    expression = " ".join(args.expression).strip()
    for q in ("'", '"'):
        if len(expression) > 1 and expression.startswith(q) and expression.endswith(q):
            expression = expression[1:-1].strip()

    # ';' separates the outputs of a multi-output circuit, exactly as for
    # `gkr gkr -C`. ArithmeticCircuit takes one string per output.
    exprs = [part.strip() for part in expression.split(";") if part.strip()]
    if not exprs:
        print("error: the expression was empty", file=sys.stderr)
        return 2

    sections = args.show
    if "all" in sections:
        sections = ["topology", "values", "mles", "wiring", "wiring-mles",
                    "propagation", "propagation-mle"]

    try:
        ac = ArithmeticCircuit(
            *exprs, prime=args.prime, pad=args.pad, strict=args.strict, out=out
        )
    except CircuitError as e:
        # A refusal is the answer, not a crash: say what is wrong and how to see more.
        print(f"\n{e}", file=sys.stderr)
        if getattr(e, "hint", None):
            print(f"\n{e.hint}", file=sys.stderr)
        print("\nTry --no-strict to build as far as possible and see the details.",
              file=sys.stderr)
        return 2

    if ac.problems:
        # --no-strict: the circuit is built but unsuitable. That IS the lesson,
        # so print the diagnosis and then show whatever sections survive.
        out.print(ac.describe_problems())
        out.print(
            "\nThis circuit is not suitable for GKR. Sections below are shown "
            "where the half-built circuit can still answer."
        )

    printers = {
        "topology": ac.print_topological_order,
        "values": ac.print_gate_values,
        "mles": ac.print_tilde_W,
        "wiring": ac.print_wiring_predicates,
        "wiring-mles": ac.print_wiring_predicate_mles,
        "propagation": ac.print_verification_propagation_equation,
        "propagation-mle": lambda: ac.print_verification_propagation_equation(mle=True),
    }
    for name in sections:
        try:
            printers[name]()
        except (AttributeError, KeyError, ValueError):
            # A half-built circuit (--no-strict) never got its gate values or
            # wiring, so these sections simply do not exist. Say that, rather
            # than leaking whichever attribute happened to be missing.
            print(f"\n[{name}] not available for this circuit "
                  f"(it could not be built completely).", file=sys.stderr)

    if args.view:
        path = ac.view(which="bitstring", format=args.format, open_file=True)
        out.print(f"\nCircuit diagram written to: {path}")

    if hasattr(out, "flush"):
        out.flush()
    return 0


def _run_mle(args: argparse.Namespace) -> int:
    import random
    from itertools import product

    from sympy import GF

    from .mle import multilinear_extension, multilinear_extension_using_lagrange_basis
    from .mle_render import print_evaluation_array, print_mle
    from .utils.display import out, print_header

    if args.seed is not None:
        random.seed(args.seed)

    field = GF(args.prime, symmetric=False)

    if args.values is not None:
        try:
            values = [int(x) for x in args.values.split(",")]
        except ValueError:
            print("--values must be a comma-separated list of integers, e.g. '1,2,3,4'",
                  file=sys.stderr)
            return 2
        v = (len(values) - 1).bit_length() if len(values) > 1 else 0
        if len(values) != 2 ** v:
            print(f"--values has {len(values)} entries; a function on {{0,1}}^v needs a "
                  f"power of two (1, 2, 4, 8, ...)", file=sys.stderr)
            return 2
        if args.variables is not None and args.variables != v:
            print(f"--values implies v={v}, but -v {args.variables} was given",
                  file=sys.stderr)
            return 2
    elif args.random:
        if args.variables is None:
            print("--random needs -v/--variables", file=sys.stderr)
            return 2
        v = args.variables
        values = [random.randrange(args.prime) for _ in range(2 ** v)]
    else:
        print("give either --values or --random (with -v)", file=sys.stderr)
        return 2

    hypercube: List[Tuple[int, ...]] = list(product([0, 1], repeat=v))
    table = {b: field(values[i]) for i, b in enumerate(hypercube)}

    print_header("The function on the hypercube", level=2, out=out)
    out.print("")
    for b, value in table.items():
        out.print(f"  f({''.join(str(x) for x in b)}) = {int(value)}")

    print_header("Its multilinear extension", level=2, out=out)
    tilde_f = multilinear_extension(field, v, lambda b: table[b])
    print_mle(tilde_f, name="f-tilde", out=out)

    if args.lagrange:
        # The same object by a different construction: agreement is a check on
        # both, and on the uniqueness claim that motivates the MLE.
        other = multilinear_extension_using_lagrange_basis(field, v, lambda b: table[b])
        same = (tilde_f - other).is_zero
        print_header("Built again, via the Lagrange basis", level=2, out=out)
        print_mle(other, name="f-tilde (Lagrange)", out=out)
        out.print(
            "\nThe two constructions agree: the multilinear extension is unique."
            if same else
            "\nThe two constructions DISAGREE, which should be impossible."
        )
        if not same:
            return 1

    if args.array:
        print_evaluation_array(tilde_f, out=out)

    if hasattr(out, "flush"):
        out.flush()
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _apply_environment(args)

    try:
        if args.cmd in ("sumcheck", "sc"):
            return _run_sumcheck(args)
        if args.cmd == "gkr":
            return _run_gkr(args)
        if args.cmd == "watch":
            return _run_watch(args)
        if args.cmd == "example":
            return _run_example(args)
        if args.cmd == "circuit":
            return _run_circuit(args)
        if args.cmd == "mle":
            return _run_mle(args)
    except (KeyboardInterrupt, EOFError):
        print("\nAborted.", file=sys.stderr)
        return 2
    except ValueError as e:
        # Prompt helpers in utils.polynomials signal bad input by raising
        # (e.g. choose_prime_field on a non-integer or non-prime). A CLI should
        # report that as a message, not a traceback. Making those prompts retry
        # and accept 'cancel' like every other prompt is a deliberate behaviour
        # change, queued for the re-narration/robustness pass.
        print(f"error: {e}", file=sys.stderr)
        return 2

    parser.error(f"unknown command: {args.cmd}")   # unreachable; argparse enforces
    return 2


if __name__ == "__main__":
    sys.exit(main())