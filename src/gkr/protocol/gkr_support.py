"""
GKR support: small helpers, interactive circuit selection, and claimed-output
utilities.

"""
from __future__ import annotations

import random
from typing import Dict, Optional, Sequence, Tuple, Union

from sympy import Poly, symbols
from sympy.polys.domains.finitefield import FiniteField
from sympy.polys.domains.modularinteger import ModularInteger

from ..ac import ArithmeticCircuit, CircuitError, DegenerateLayer
from ..mle import multilinear_extension
from ..prompts import choose_prime_field
from ..utils.display import RED, RESET, TerminalOutput, progress, stringify
from ..utils.display import out as default_out


def _label_bitlength(ac: ArithmeticCircuit, i: int) -> int:
    """Bit-length s_i of the gate labels at layer i (keys of W_dict[i])."""
    k = next(iter(ac.W_dict[i].keys()))
    return len(k)


def _eval_tilde(poly: Poly, coords: Sequence[Union[int, ModularInteger]], field: FiniteField) -> ModularInteger:
    """
    Evaluate a tilde_W-style polynomial at `coords`.

    Handles the s = 0 convention used by the ArithmeticCircuit class: a layer with a
    single gate labelled by the empty bitstring has a *constant* multilinear extension,
    stored as a constant Poly in one dummy variable.
    """
    if len(coords) == 0:
        return field.convert(poly.eval({poly.gens[0]: 0}))
    subs = {poly.gens[j]: int(coords[j]) for j in range(len(coords))}
    return field.convert(poly.eval(subs))


def _point_str(coords: Sequence[Union[int, ModularInteger]]) -> str:
    """Render a tuple of field elements as '(a, b, ...)' (or '()' when empty)."""
    return f"({stringify([int(c) for c in coords])})"


def _truncate_expr(poly: Poly, max_chars: int = 800) -> str:
    expr_str = str(poly.as_expr())
    if len(expr_str) > max_chars:
        expr_str = expr_str[:max_chars] + " ... (truncated)"
    return expr_str


def normalize_to_x_vars(poly: Poly, s: int) -> Poly:
    """
    Rename the generators of `poly` (a tilde_W-style polynomial in s variables)
    to the canonical x_0, ..., x_{s-1}.
    """
    if s == 0:
        # Constant polynomial in a dummy variable; keep as is.
        return poly
    x_syms = list(symbols(f"x_:{s}"))
    replacement = {poly.gens[j]: x_syms[j] for j in range(s)}
    return Poly(poly.as_expr().subs(replacement), *x_syms, domain=poly.domain)


DEFAULT_CIRCUIT = "(3*2) + (4 + 1)"


def validate_for_gkr(ac: ArithmeticCircuit) -> None:
    """Check the requirements GKR adds on top of being a well-formed circuit.

    Being an acyclic, strictly-layered, fan-in-two circuit whose wiring
    predicates and multilinear extensions exist is ArithmeticCircuit's own
    business -- it raises a CircuitError if any of that fails, so there is no
    such thing as a half-built circuit to inspect. What remains here is what
    the *protocol* needs from a circuit that is otherwise perfectly valid.

    Raises:
        CircuitError: if the circuit cannot be used for GKR.
    """
    # A circuit built with strict=False recorded its failures instead of raising:
    # good for exposition, but the protocol must not touch it.
    problems = getattr(ac, "problems", [])
    if problems:
        raise problems[0]

    if ac.depth is None or ac.depth < 1:
        raise CircuitError(
            "the circuit has depth 0: there is nothing to verify",
            hint="Give a circuit with at least one gate, e.g. '(3*2) + (4 + 1)'.",
        )
    for layer in range(1, ac.depth + 1):
        if _label_bitlength(ac, layer) == 0:
            raise DegenerateLayer(
                f"layer {layer} consists of a single gate (s_{layer} = 0)"
            )


def choose_arithmetic_circuit(
    *,
    out: TerminalOutput = default_out,
    max_attempts: int = 3,
) -> Optional[ArithmeticCircuit]:
    """
    Interactively choose a prime field and an arithmetic circuit.

    The circuit is entered as one or more expressions separated by ';' (each expression
    is one output gate). Returns an ArithmeticCircuit, or None if the user cancels or
    the attempts are exhausted.
    """
    # ---- prime field ----
    # choose_prime_field retries and returns None on cancel/exhaustion.
    field: Optional[FiniteField] = choose_prime_field(out=out)
    if field is None:
        return None
    p = int(field.mod)

    # ---- circuit ----
    out.print(
        f"\nEnter your arithmetic circuit over {field} as one or more expressions "
        f"separated by ';' (each expression is one output gate)."
    )
    out.print(
        "\nUse integer constants and the binary operators + and *. Keep expressions "
        "fairly simple: the circuit must be strictly layered (every path from an "
        "output to an input has the same length), and layer sizes that are powers "
        "of two are safest."
    )
    out.print(
        "\nFor example, '5*4 + 3' is not strictly layered (the input 3 sits one "
        "layer too high), but '5*4 + (3 + 0)' is."
    )

    for attempt in range(1, max_attempts + 1):
        raw = out.input(
            f"\nEnter your circuit (or press Enter for the default '{DEFAULT_CIRCUIT}'; "
            "type 'cancel' to abort): "
        ).strip()
        if raw.lower() == "cancel":
            return None
        if not raw:
            raw = DEFAULT_CIRCUIT
        expr_strings = [s.strip() for s in raw.split(";") if s.strip()]
        try:
            with progress(
                "\nBuilding the circuit, its wiring predicates, and their multilinear "
                    "extensions. For larger circuits this can take a minute...",
                out=out,
            ):
                ac = ArithmeticCircuit(*expr_strings, prime=p, out=out)
            validate_for_gkr(ac)
        except CircuitError as e:
            out.print(f"\n{RED}This circuit cannot be used{RESET}: {e}.")
            if e.hint:
                out.print(f"\n{e.hint}")
            if attempt < max_attempts:
                out.print(f"Try again ({attempt}/{max_attempts}).")
            continue
        except Exception as e:
            out.print(f"\nCould not build the circuit: {e}")
            ac = None

        if ac is not None:
            return ac

    out.print(f"\n{RED}Too many failed attempts.{RESET}")
    return None


def _claimed_output_mle(ac: ArithmeticCircuit, claims: Dict[Tuple[int, ...], int]) -> Poly:
    """
    The multilinear extension W-tilde*_0 (the notebook's notation) of the *claimed* output function.

    The claimed output function maps a gate label b in {0,1}^{s_0} to the claimed value
    of that output gate (and to 0 for labels that do not correspond to actual gates;
    this is public information, since the circuit topology is public).

    If the claims coincide with the true outputs, then W-tilde*_0 = W-tilde_0 (uniqueness
    of multilinear extensions).
    """
    F = ac.field
    s0 = _label_bitlength(ac, 0)
    if s0 == 0:
        X = symbols("x_:1")
        return Poly(int(F.convert(claims[()])), X, domain=F)
    return multilinear_extension(F, s0, lambda b: int(F.convert(claims.get(tuple(b), 0))))


def _machine_claimed_outputs(
    ac: ArithmeticCircuit,
    dishonest_claim: bool,
) -> Dict[Tuple[int, ...], int]:
    """The machine prover's claimed outputs: the truth, or the truth with one gate corrupted."""
    F = ac.field
    p = int(F.mod)
    claims = {label: int(v) for label, v in ac.W_dict[0].items()}
    if dishonest_claim:
        label = random.choice(sorted(claims.keys()))
        true_value = claims[label]
        false_value = true_value
        while false_value == true_value:
            false_value = random.randrange(p)
        claims[label] = false_value
    return claims