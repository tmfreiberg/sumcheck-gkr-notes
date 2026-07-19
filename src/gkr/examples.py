"""
The worked examples from the notebooks.

Every interactive demo lives here: they are prompts plus narration wrapped
around a single call into the real code, which is a different job from the code
itself. Splitting them out leaves gkr.mle as ~175 lines of pure mathematics
with no I/O at all, and empties gkr.sumcheck completely.

    total_degree_example            degrees of a multivariate polynomial
    roots_example                   Schwartz-Zippel, empirically
    sum_check_example               a full sum-check run on a random g
    multilinear_extension_example   an MLE built two ways, and compared
    gkr_example                     a complete GKR run on the notes' circuit
"""
from __future__ import annotations

import time
from itertools import product
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np
from sympy import GF, Poly, Symbol, degree, isprime, symbols
from sympy.polys.domains.finitefield import FiniteField

from .ac import ArithmeticCircuit
from .mle import (
    evaluation_array,
    multilinear_extension,
)
from .mle_render import is_multilinear, print_compared_grids
from .prompts import choose_polynomial, choose_prime_field
from .protocol import (
    SPECTATOR_VIEW,
    Aborted,
    Accepted,
    Audience,
    MachineProver,
    PolynomialOracle,
    RandomVerifier,
    ScriptedVerifier,
    Sink,
    make_renderer,
    run_sum_check,
)
from .protocol.gkr_session import gkr
from .protocol.sumcheck_events import GroundTruthRevealed, ProtocolInitialized
from .protocol.sumcheck_session import sum_check
from .utils import (
    BLUE,
    GREEN,
    RED,
    RESET,
    YELLOW,
    TerminalOutput,
    display_aligned,
    out,
    stringify,
)


def total_degree_example(out=out, interactive: bool = True) -> None:
    """Show the total-degree and per-variable-degree notions on a worked example.

    interactive=True (default) loops, offering further examples with polynomials
    the user enters. interactive=False shows the single built-in example and
    returns -- the prompt-free path a rendered book or a stdin-closed run needs.
    """
    loop_counter: int = 0
    carry_on: bool = True
    while carry_on:
        if loop_counter == 0:
            # Default example
            X = symbols(f"X_:{3}")
            g = Poly((X[0] - X[1]) * (X[1] - X[2]), X, domain=GF(5, symmetric=False))
        else:
            g = choose_polynomial(out=out)
            if g is None:
                continue

        multilinear: str = 'multilinear' if is_multilinear(g) else 'non-multilinear'
        X_tuple = ', '.join([str(X) for X in g.gens])
        out.print(
            f"\n{BLUE}EXAMPLE {loop_counter + 1}.{RESET} The polynomial \n\n"
            f"g({X_tuple}) = {g.as_expr()} \n\n"
            f"is a {multilinear} polynomial in {g.domain}[{X_tuple}]."
        )
        out.print(f"\nThe total degree of g is deg(g) = {g.total_degree()}")
        for X in g.gens:
            out.print(f"\nThe degree of {X} in g is deg_{X}(g) = {degree(g, X)}.")
        if not interactive:
            break
        again = out.input("\nAnother example? (y/n)")
        loop_counter += 1
        if again == 'n':
            carry_on = False
        else:
            out.print("")

def roots(poly: Poly, time_out: Optional[float] = 60) -> Tuple[Set[Tuple[int, ...]], bool]:
    """
    Finds the roots of a polynomial over its defined finite field, with an optional timeout.

    This function iterates over all possible v-tuples of elements in the field
    associated with the polynomial's domain and evaluates the polynomial at each
    tuple. If the polynomial evaluates to zero at a tuple, that tuple is added
    to the set of roots. If the specified timeout is exceeded, the search is
    terminated.

    Args:
        poly (Poly): The polynomial to evaluate, represented as a SymPy Poly object
                     defined over a finite field.
        time_out (float, optional): Maximum time allowed for root finding in seconds.
                                    Defaults to None (no timeout).

    Returns:
        Tuple[Set[Tuple[int, ...]], bool]: A tuple containing the set of roots and a boolean
                                           indicating if the loop was terminated early.
    """
    # Extract the finite field from the polynomial's domain
    field = poly.domain
    if field.has_CharacteristicZero:
        raise ValueError("The polynomial must be defined over a finite field.")
    if not isprime(field.mod):
        raise ValueError("Sorry, 'we're using SymPy and can only handle prime fields at present.")

    # Get the list of variables in the polynomial
    variables = poly.gens
    num_vars = len(variables)

    # Prepare the set to store roots
    root_set: Set[Tuple[int, ...]] = set()

    # Initialize timing if time_out is specified
    if time_out is not None:
        tic = time.time()

    # Iterate over all possible v-tuples of elements in the field
    for values in product(range(field.mod), repeat=num_vars):
        # Check if the time limit has been exceeded
        if time_out is not None and time.time() - tic > time_out:
            return root_set, True  # Early termination

        # Create a dictionary mapping variables to values in the tuple
        eval_point = {var: field(val) for var, val in zip(variables, values)}

        # Evaluate the polynomial at the current tuple
        if poly.eval(eval_point) == 0:
            root_set.add(values)

    return root_set, False  # Completed without early termination

def _domain_power_str(g: Poly, v: int) -> str:
    """
    Human-friendly string for the ambient space of tuples.

    We want to convey: tuples in (GF(p))^v (Cartesian power),
    and avoid the misleading GF(p)**(v) which reads like GF(p^v).
    """
    return f"({g.domain})^({v})"

def _fmt_prob_fraction(num_roots: int, p: int, v: int) -> str:
    """
    Format the probability as an exact fraction plus a decimal approximation.
    """
    denom = p**v
    prob = num_roots / denom
    return f"{num_roots}/{p}**{v} = {prob}"

def _fmt_sz_bound(d: int, p: int) -> str:
    """
    Format the Schwartz-Zippel upper bound d/#F as exact fraction plus decimal.
    """
    bound = d / p
    return f"{d}/{p} = {bound}"

def roots_example(
    time_out: Optional[float] = None,
    out=out,
    interactive: bool = True,
    polynomials: "Optional[Sequence[Poly]]" = None,
) -> None:
    """
    Demo of Schwartz-Zippel: count roots (exactly if feasible, otherwise partially).

    - Prints the ambient space as (GF(p))^(v) to avoid confusion with extension fields.
    - When enumeration completes, compares observed probability to the SZ bound.
    - When timed out, labels the probability as a lower bound and reminds SZ is an upper bound.

    Three ways to drive it:
      * polynomials=[g1, g2, ...] runs exactly those, in order, and returns. This
        is the prompt-free path a rendered book uses; pass whatever polynomials
        you want to showcase (e.g. a small field where every root is found, then
        a larger one where the search times out).
      * interactive=False (no polynomials) runs the single built-in example.
      * interactive=True (default) runs the built-in example, then offers more
        from user input.
    """
    loop_counter: int = 0
    carry_on: bool = True

    while carry_on:
        # --- Choose polynomial ---
        if polynomials is not None:
            if loop_counter >= len(polynomials):
                break
            g = polynomials[loop_counter]
        elif loop_counter == 0:
            X = symbols("X_:3")
            g = Poly(X[0] * X[1] + X[2] ** 2, X, domain=GF(41, symmetric=False))
        else:
            g = choose_polynomial(out=out)
            if g is None:
                # User entered invalid input; restart loop without incrementing counter.
                continue

        zero_set, ran_out_of_time = roots(poly=g, time_out=time_out)
        zeros = sorted(zero_set)

        v = len(g.gens)
        p = int(g.domain.mod)
        d = int(g.total_degree())

        space_str = _domain_power_str(g, v)
        r_tuple = ", ".join([f"r_{j}" for j in range(v)])

        lhs_str = _fmt_prob_fraction(len(zeros), p, v)
        rhs_str = _fmt_sz_bound(d, p)

        # --- Header + probability statement ---
        if ran_out_of_time:
            out.print(
                f"\n{BLUE}EXAMPLE {loop_counter + 1}.{RESET} "
                f"In {GREEN}{time_out} seconds{RESET}, we found {len(zeros)} roots of {g.as_expr()} in {space_str}."
            )
            out.print(f"\n{GREEN}There may be more roots, so what follows is not a verification of Schwartz-Zippel.{RESET}")
            out.print(
                f"\nThus, if each of {r_tuple} is chosen independently and uniformly at random from {g.domain}, "
                f"then g({r_tuple}) = 0 with probability {GREEN}at least{RESET} {lhs_str} "
                f"(this is a lower bound). Schwartz-Zippel gives an upper bound."
            )
        else:
            out.print(
                f"\n{BLUE}EXAMPLE {loop_counter + 1}.{RESET} "
                f"The polynomial {g.as_expr()} has {len(zeros)} roots in {space_str}."
            )
            out.print(
                f"\nThus, if each of {r_tuple} is chosen independently and uniformly at random from {g.domain}, "
                f"then g({r_tuple}) = 0 with probability {lhs_str}."
            )

        # --- Degree + SZ bound ---
        out.print(f"\nThe polynomial has total degree d = {d}, and the Schwartz-Zippel bound is {rhs_str}.")

        # If we enumerated all roots, compare observed probability to the bound.
        if not ran_out_of_time:
            prob = len(zeros) / (p**v)
            bound = d / p
            eps = 1e-12
            if prob < bound - eps:
                rel = "below"
            elif prob > bound + eps:
                rel = "above"
            else:
                rel = "equal to (within rounding)"
            out.print(f"\nObserved probability is {rel} the Schwartz-Zippel upper bound.")

        # --- Print some roots ---
        truncate: int = 10
        if len(zeros) > truncate:
            out.print(f"\nHere are {truncate} of the roots:\n")
            to_print = [f"g{z} = 0" for z in zeros[:truncate]]
        else:
            if ran_out_of_time:
                out.print("\nHere are the roots we found before running out of time:\n")
            else:
                out.print("\nHere are the roots:\n")
            to_print = [f"g{z} = 0" for z in zeros]

        display_aligned(*to_print, out=out)

        # --- Continue? ---
        if polynomials is not None:
            loop_counter += 1
            continue          # run the whole list, prompt-free, then break at the top
        if not interactive:
            break
        again = out.input("\nAnother example? (y/n) ").strip().lower()
        loop_counter += 1
        if again == "n":
            carry_on = False

def _sum_check_scripted(scenario: dict, *, out=out) -> None:
    """Run one reproducible sum-check with a fixed claim and scripted challenges."""
    g: Poly = scenario["poly"]
    X = g.gens
    F = g.domain
    v = len(X)
    claim = int(scenario["claim"])
    challenges = list(scenario["challenges"])

    H = F(sum(
        g.eval({X[k]: b_k for k, b_k in enumerate(b)})
        for b in product([F(0), F(1)], repeat=v)
    ))
    degree_bounds = [int(g.degree(gen)) for gen in X]

    sink = Sink(make_renderer(out=out, field=F, view=SPECTATOR_VIEW))
    sink.emit(ProtocolInitialized(
        audience=Audience.PUBLIC, g=g,
        degree_bounds=tuple(degree_bounds), num_vars=v,
    ))
    dishonest = (int(F.convert(claim)) != int(F.convert(H)))
    prover = MachineProver(g, H, sink, dishonest_claim=dishonest, fixed_claim=claim)
    verifier = ScriptedVerifier(F, challenges, out=out)
    oracle = PolynomialOracle(g)
    result = run_sum_check(
        field=F, gens=X, degree_bounds=degree_bounds,
        prover=prover, verifier=verifier, oracle=oracle, sink=sink, out=out,
    )
    res = (None if isinstance(result.verdict, Aborted)
           else isinstance(result.verdict, Accepted))
    sink.emit(GroundTruthRevealed(
        audience=Audience.GROUND_TRUTH, g=g, gens_str=stringify(X), num_vars=v,
        true_sum=int(H), claimed_sum=int(F.convert(result.claim)),
        accepted=bool(res), use_commitment=False, dishonest_opening=False,
    ))
    if hasattr(out, "flush"):
        out.flush()


def sum_check_example(
    out=out,
    interactive: bool = True,
    scenario: "Optional[dict]" = None,
) -> None:
    """Demo of the sum-check protocol.

    Default: an honest machine prover over GF(5), verifier accepts.

    scenario={...} runs a single reproducible, prompt-free scripted run and
    returns. The dict keys are:
        poly        : a sympy Poly over a prime field (the polynomial g)
        claim       : the prover's claimed sum H* (an int); if it differs from
                      the true H, the prover is dishonest
        challenges  : the verifier's challenges r_0, r_1, ..., in order
    This is how a book reproduces a specific run -- a particular sequence of
    verifier choices -- with byte-identical output every time. See
    ScriptedVerifier.
    """
    if scenario is not None:
        _sum_check_scripted(scenario, out=out)
        return

    loop_counter: int = 0
    carry_on: bool = True
    while carry_on:
        if hasattr(out, "flush"):
            out.flush()
        out.print(f"\n{BLUE}EXAMPLE {loop_counter + 1}.{RESET} ")
        if loop_counter == 0:
            # Default example
            v: int = 3
            X: Tuple[Symbol, ...] = symbols(f"X_:{v}")
            F: FiniteField = GF(5, symmetric=False)
            multivariate_init: Poly = Poly((X[0] - X[1]) * (X[1] - X[2]), X, domain=F)
            # Calculate the true sum by evaluating the polynomial over all Boolean inputs
            H = F(sum(
                multivariate_init.eval({X[k]: b_k for k, b_k in enumerate(b)})
                for b in product([F(0), F(1)], repeat=v)
            ))

            # Run the protocol on the new engine (an honest machine prover,
            # a random verifier, the spectator view).
            degree_bounds = [int(multivariate_init.degree(gen)) for gen in X]
            sink = Sink(make_renderer(out=out, field=F, view=SPECTATOR_VIEW))
            sink.emit(ProtocolInitialized(
                audience=Audience.PUBLIC,
                g=multivariate_init,
                degree_bounds=tuple(degree_bounds),
                num_vars=v,
            ))
            prover = MachineProver(multivariate_init, H, sink)
            verifier = RandomVerifier(F, out=out)
            oracle = PolynomialOracle(multivariate_init)
            result = run_sum_check(
                field=F, gens=X, degree_bounds=degree_bounds,
                prover=prover, verifier=verifier, oracle=oracle,
                sink=sink, out=out,
            )
            res = (None if isinstance(result.verdict, Aborted)
                   else isinstance(result.verdict, Accepted))

            if res is None:
                out.print(f"\n{YELLOW}Protocol aborted (cancelled / too many invalid inputs).{RESET}")
                return

            out.print(f"\n{GREEN}Verifier accepted.{RESET}" if res
                      else f"\n{RED}Verifier rejected.{RESET}")

            # The epilogue sum_check() prints. This example drives the engine
            # directly rather than going through the session, so it has to emit
            # this itself.
            sink.emit(GroundTruthRevealed(
                audience=Audience.GROUND_TRUTH,
                g=multivariate_init,
                gens_str=stringify(X),
                num_vars=v,
                true_sum=int(H),
                claimed_sum=int(F.convert(result.claim)),
                accepted=bool(res),
                use_commitment=False,
                dishonest_opening=False,
            ))
        else:
            sum_check()
        if not interactive:
            break
        again = out.input("\nAnother example? (y/n)").strip().lower()
        loop_counter += 1
        if again == 'n':
            carry_on = False




def multilinear_extension_example(
    show_result: bool = True,
    compare: bool = False,
    *,
    out: TerminalOutput = out,
    examples: "Optional[Sequence[dict]]" = None,
    interactive: bool = True,
) -> Optional[Tuple[List[Poly], List[np.ndarray]]]:
    """
    Demo: build MLEs of functions f : {0,1}^v -> GF(p).

    Interactive (default): EXAMPLE 1 and 2 are fixed defaults over GF(11), v=2;
    after that the user supplies further examples. If compare=True, consecutive
    examples with matching (p, v) are compared.

    Prompt-free (a rendered book): pass examples=[...] where each entry is a dict
        {"p": prime, "v": num_vars, "values": {bitstring: int, ...}}
    Those examples are run in order and the function returns -- no input() is
    called. compare=True still compares consecutive matching (p, v) pairs.
    interactive=False with no examples runs just the two canned defaults.
    """
    mle: List[Poly] = []
    grid: List[np.ndarray] = []
    pee: List[int] = []
    vee: List[int] = []

    scripted = examples is not None
    n_examples = len(examples) if examples is not None else 0

    loop_counter: int = 0

    while True:
        # ----------------------------
        # Choose (p, v) for this example
        # ----------------------------
        if scripted:
            assert examples is not None and n_examples is not None
            if loop_counter >= n_examples:
                break
            spec = examples[loop_counter]
            p = int(spec["p"])
            v = int(spec["v"])
            out.print(f"\n{BLUE}EXAMPLE {loop_counter + 1}.{RESET}")
        elif loop_counter in {0, 1}:
            p = 11
            v = 2
            out.print(f"\n{BLUE}EXAMPLE {loop_counter + 1}.{RESET}")
        else:
            out.print(f"\n{BLUE}EXAMPLE {loop_counter + 1}.{RESET}")
            field = choose_prime_field(
                out=out, prompt="Enter a prime p (we will work over GF(p), or 'cancel' to abort): "
            )
            if field is None:
                return None     # cancelled or too many invalid inputs
            p = int(field.mod)

            v = int(out.input("Enter a positive integer v (we extend f : {0,1}^v -> GF(p)): ").strip())
            if v <= 0:
                out.print(f"{RED}Invalid input: v must be a positive integer.{RESET}")
                continue

        pee.append(p)
        vee.append(v)

        field = GF(p, symmetric=False)

        # nicer formatting than **v
        out.print(f"\nWe extend a function f : {{0,1}}^{v} -> {field} to a function f̃ : {field}^{v} -> {field}.\n")

        # ----------------------------
        # Collect function values on {0,1}^v
        # ----------------------------
        func_values: Dict[Tuple[int, ...], Any] = {}

        # The first two examples are canned, so a reader can just run the cell.
        # The second differs in one value, which is what makes compare=True
        # interesting: the two MLEs then agree on some points and not others.
        _CANNED = {
            0: {(0, 0): 1, (0, 1): 2, (1, 0): 3, (1, 1): 4},
            1: {(0, 0): 1, (0, 1): 2, (1, 0): 3, (1, 1): 3},
        }
        if scripted:
            assert examples is not None
            for point in product([0, 1], repeat=v):
                value = int(examples[loop_counter]["values"][point])
                func_values[point] = field(value)
                out.print(f"The function value for input {point} is: {value}")
        elif loop_counter in _CANNED:
            for point, value in _CANNED[loop_counter].items():
                func_values[point] = field(value)
                out.print(f"The function value for input {point} is: {value}")

        else:
            for bitstring in product([0, 1], repeat=v):
                user_input = out.input(f"Enter the function value for input {bitstring}: ").strip()
                try:
                    user_value = int(user_input)
                except ValueError:
                    out.print(f"{RED}Invalid input: function values must be integers.{RESET}")
                    break
                func_values[bitstring] = field(user_value)
            else:
                # only runs if the for-loop did NOT break
                pass
            # If the loop broke, restart this example without incrementing loop_counter
            if len(func_values) != 2**v:
                continue

        def explicit_function(inputs: Tuple[int, ...]):
            return func_values[inputs]

        # ----------------------------
        # Compute MLE and (optionally) show grid
        # ----------------------------
        extended_func = multilinear_extension(field=field, v=v, func=explicit_function)
        mle.append(extended_func)

        eval_array = evaluation_array(polynomial=extended_func)
        grid.append(eval_array)

        if show_result:
            X_str: str = stringify(symbols(f"x_:{v}"))
            out.print(f"\nThe multilinear extension of this function is:\n\n{YELLOW}f̃({X_str}) = {extended_func.as_expr()}{RESET}")

        if show_result and v <= 2 and p < 50:
            out.print("\nIn the following array, entry (i,j) is f̃(i,j):\n")
            out.print(eval_array)

        # ----------------------------
        # Compare consecutive examples if requested and compatible
        # ----------------------------
        if compare and len(mle) >= 2:
            if pee[-1] == pee[-2] and vee[-1] == vee[-2]:
                p_cmp = pee[-1]
                v_cmp = vee[-1]

                out.print(f"\nThe multilinear extension of the first function "
                      f"({BLUE}EXAMPLE {loop_counter}{RESET}) is: {YELLOW}{mle[-2].as_expr()}{RESET}.")
                out.print(f"\nThe multilinear extension of the second function "
                      f"({BLUE}EXAMPLE {loop_counter + 1}{RESET}) is: {YELLOW}{mle[-1].as_expr()}{RESET}.")
                out.print(f"\nThe multilinear extensions can agree on at most {v_cmp * p_cmp**(v_cmp - 1)} "
                      f"out of {p_cmp**v_cmp} points.")

                if v_cmp <= 2 and p_cmp < 50:
                    agree = (grid[-2] == grid[-1]).sum()
                    out.print(f"\nIndeed, they agree on {GREEN}{agree} points{RESET}, as shown below.\n")

                    print_compared_grids(
                        grid[-2], grid[-1],
                        (f"EXAMPLE {loop_counter}", f"EXAMPLE {loop_counter + 1}"),
                        out=out,
                    )
            else:
                out.print(f"\n{YELLOW}Compare skipped: last two examples used different (p, v).{RESET}")

        # ----------------------------
        # Prompt to continue (ALWAYS reachable)
        # ----------------------------
        if scripted:
            loop_counter += 1
            continue        # run the whole list prompt-free; break at the top
        if not interactive:
            break
        again = out.input("\nAnother example? (y/n) ").strip().lower()
        loop_counter += 1
        if again != "y":
            break
    return mle, grid

def gkr_example(
    expression: str = "(3*2) + (4 + 1)",
    *,
    prime: int = 2 ** 31 - 1,
    dishonest: bool = False,
    out: TerminalOutput = out,
) -> Optional[bool]:
    """A complete GKR run on a fixed circuit, start to finish, with no prompts.

    The default circuit is the one worked through in the notes: two layers, a
    single output gate, inputs 3, 2, 4, 1. The prover is honest by default;
    dishonest=True corrupts the claimed output, so the reader can watch the lie
    propagate down the layers and be caught -- or, occasionally, laundered.

    The field is the Mersenne prime 2^31 - 1, big enough that a lie surviving to
    the end is genuinely improbable rather than merely unlikely (see the
    soundness discussion in the notes).

    Returns True (V accepted), False (V rejected), or None (aborted).
    """
    ac = ArithmeticCircuit(expression, prime=prime, out=out)
    return gkr(
        ac,
        interactive=False,
        dishonest_claim=dishonest,
        secret_mode=False,
        out=out,
    )