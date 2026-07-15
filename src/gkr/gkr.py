from __future__ import annotations

import random
from dataclasses import dataclass, field as dataclass_field
from typing import Dict, List, Optional, Sequence, Tuple, Union

from sympy import Poly, Symbol, symbols
from sympy.polys.domains import Domain
from sympy.polys.domains.finitefield import FiniteField
from sympy.polys.domains.modularinteger import ModularInteger

from .utils.display import (
    TerminalOutput,
    out as default_out,
    print_header,
    display_aligned,
    stringify,
    display as _ipython_display,
    _in_notebook,
    RED,
    GREEN,
    YELLOW,
    BLUE,
    RESET,
)
from .utils.polynomials import random_field_element, choose_prime_field, parse_poly

from .ac import ArithmeticCircuit, replace_symbols_in_polynomial
from .mle import multilinear_extension
from .sumcheck import sum_check_recursion


"""
START: SMALL HELPERS
"""


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


"""
END: SMALL HELPERS
"""


"""
START: CIRCUIT SELECTION
"""

DEFAULT_CIRCUIT = "(3*2) + (4 + 1)"


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
    field: Optional[FiniteField] = None
    for attempt in range(1, max_attempts + 1):
        try:
            field = choose_prime_field(out=out)
            break
        except Exception as e:
            out.print(f"\nCould not construct a prime field: {e}")
            if attempt < max_attempts:
                out.print(f"Try again ({attempt}/{max_attempts}).")
    if field is None:
        return None
    p = int(field.mod)

    # ---- circuit ----
    out.print(
        f"\nEnter your arithmetic circuit over {field} as one or more expressions "
        f"separated by ';' (each expression is one output gate)."
    )
    out.print(
        f"\nUse integer constants and the binary operators + and *. Keep expressions "
        f"fairly simple: the circuit must be strictly layered (every path from an "
        f"output to an input has the same length), and layer sizes that are powers "
        f"of two are safest."
    )
    out.print(
        f"\nFor example, '5*4 + 3' is not strictly layered (the input 3 sits one "
        f"layer too high), but '5*4 + (3 + 0)' is."
    )

    for attempt in range(1, max_attempts + 1):
        raw = out.input(
            f"\nEnter your circuit (or press Enter for the default '{DEFAULT_CIRCUIT}'; "
            f"type 'cancel' to abort): "
        ).strip()
        if raw.lower() == "cancel":
            return None
        if not raw:
            raw = DEFAULT_CIRCUIT
        expr_strings = [s.strip() for s in raw.split(";") if s.strip()]
        try:
            ac = ArithmeticCircuit(*expr_strings, prime=p, out=out)
        except Exception as e:
            out.print(f"\nCould not build the circuit: {e}")
            ac = None

        problem: Optional[str] = None
        if ac is not None:
            if not getattr(ac, "is_dag", False):
                problem = "the circuit is not a directed acyclic graph"
            elif not getattr(ac, "fan_in_two", False):
                problem = "some gate does not have fan-in exactly 2"
            elif not all(hasattr(ac, attr) for attr in ("W_dict", "tilde_W", "tilde_add", "tilde_mult")):
                problem = (
                    "the gate values / wiring predicates / multilinear extensions could not be "
                    "constructed (see the message above)"
                )
            elif ac.depth is None or ac.depth < 1:
                problem = "the circuit has depth 0 (there is nothing to verify)"
            else:
                # Interior and input layers must have at least one label bit
                # (a single-gate *interior* layer would make the layer sum-check degenerate).
                for layer in range(1, ac.depth + 1):
                    if _label_bitlength(ac, layer) == 0:
                        problem = f"layer {layer} consists of a single gate (s_{layer} = 0)"
                        break

        if ac is not None and problem is None:
            return ac

        out.print(f"\n{RED}This circuit cannot be used{RESET}" + (f": {problem}." if problem else "."))
        out.print(
            "\nHints: every input must sit at the bottom layer (pad with things like "
            "'(3 + 0)' or '(3*1)' if necessary), and layers whose sizes are powers of "
            "two are safest."
        )
        if attempt < max_attempts:
            out.print(f"Try again ({attempt}/{max_attempts}).")

    out.print(f"\n{RED}Too many failed attempts.{RESET}")
    return None


"""
END: CIRCUIT SELECTION
"""


"""
START: CLAIMED OUTPUTS
"""


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


"""
END: CLAIMED OUTPUTS
"""


"""
START: DISHONEST-PROVER HELPERS (GKR LEVEL)
"""


def dishonest_folding_values(
    *,
    field: FiniteField,
    A: Union[int, ModularInteger],
    M: Union[int, ModularInteger],
    gamma: Union[int, ModularInteger],
    z_x_true: Union[int, ModularInteger],
    z_y_true: Union[int, ModularInteger],
    max_tries: int = 200,
) -> Optional[Tuple[ModularInteger, ModularInteger, Optional[str]]]:
    """
    Choose claimed endpoints (z*_x, z*_y) satisfying the bridging equation

        gamma = A*(z*_x + z*_y) + M*z*_x*z*_y   (in GF(p)),

    preferring to keep one endpoint TRUE (one lie instead of two). Keeping, say,
    z*_x = z_x plants t = 0 as a root of q* - q for free at the next step.

    Returns (z_x_star, z_y_star, kept) where kept is:
        "x"    -- z*_x is the true value (only z*_y is a lie),
        "y"    -- z*_y is the true value (only z*_x is a lie),
        "both" -- both endpoints are the TRUE values (only possible in the degenerate
                  case A = M = 0 and gamma = 0, where the bridging equation is vacuous:
                  the lie is laundered),
        None   -- both endpoints are lies (generic fallback).

    Returns None if no endpoints can satisfy the equation (A = M = 0 but gamma != 0):
    the prover is caught no matter what.
    """
    p = int(field.mod)
    A_i = int(field.convert(A))
    M_i = int(field.convert(M))
    g_i = int(field.convert(gamma))
    zx_t = int(field.convert(z_x_true))
    zy_t = int(field.convert(z_y_true))

    if A_i == 0 and M_i == 0:
        if g_i % p != 0:
            return None  # impossible: caught
        # Vacuous constraint: claim the TRUTH and the lie evaporates.
        return field.convert(zx_t), field.convert(zy_t), "both"

    # Try to keep z*_x = z_x (true): solve gamma = A*(zx + zy) + M*zx*zy for zy.
    denom = (A_i + M_i * zx_t) % p
    if denom != 0:
        zy = ((g_i - A_i * zx_t) % p) * pow(denom, -1, p) % p
        return field.convert(zx_t), field.convert(zy), "x"

    # Symmetric: keep z*_y = z_y (true) and solve for zx.
    denom = (A_i + M_i * zy_t) % p
    if denom != 0:
        zx = ((g_i - A_i * zy_t) % p) * pow(denom, -1, p) % p
        return field.convert(zx), field.convert(zy_t), "y"

    # Generic fallback: random zx until solvable.
    for _ in range(max_tries):
        zx = random.randrange(p)
        denom = (A_i + M_i * zx) % p
        if denom == 0:
            if (A_i * zx) % p == g_i:
                return field.convert(zx), field.convert(random.randrange(p)), None
            continue
        zy = ((g_i - A_i * zx) % p) * pow(denom, -1, p) % p
        return field.convert(zx), field.convert(zy), None
    return None


def dishonest_q_polynomial(
    *,
    q_true: Poly,
    zx_star: Union[int, ModularInteger],
    zy_star: Union[int, ModularInteger],
    deg_bound: int,
    field: FiniteField,
    t: Symbol,
) -> Tuple[Poly, List[int]]:
    """
    Construct a forged restriction q*(t) with

        q*(0) = z*_x,   q*(1) = z*_y,   deg(q*) <= deg_bound,

    agreeing with the true q at as many points as possible.

    Construction: q* = q + h, where

        h(t) = (alpha*t + beta) * prod_j (t - t_j),

    the t_j being k = min(deg_bound - 1, p - 2) distinct planted points outside {0, 1},
    and (alpha, beta) solving h(0) = z*_x - q(0), h(1) = z*_y - q(1). Then

        deg(h) <= k + 1 <= deg_bound,

    and the roots of q* - q = h are EXACTLY the planted points t_j together with the
    root of the linear factor (-beta/alpha, when alpha != 0) -- a complete list, by
    construction. In particular, if z*_x = q(0) (the kept-true endpoint), then beta = 0
    and t = 0 is one of the roots.

    Returns (q_star, roots) where roots is the sorted, complete list of roots of
    q* - q in GF(p).
    """
    F = field
    p = int(F.mod)
    q0 = int(F.convert(q_true.eval({t: 0})))
    q1 = int(F.convert(q_true.eval({t: 1})))
    delta0 = (int(F.convert(zx_star)) - q0) % p
    delta1 = (int(F.convert(zy_star)) - q1) % p

    k = max(min(deg_bound - 1, p - 2), 0)
    planted = [(2 + j) % p for j in range(k)]
    # (For p > k + 1 these are distinct and avoid {0, 1}; the circuit-entry validation
    #  keeps the toy parameters well inside that regime.)

    P0 = 1
    P1 = 1
    for t_j in planted:
        P0 = (P0 * (0 - t_j)) % p
        P1 = (P1 * (1 - t_j)) % p

    beta = (delta0 * pow(P0, -1, p)) % p
    alpha = ((delta1 * pow(P1, -1, p)) - beta) % p

    h_expr = (alpha * t + beta)
    for t_j in planted:
        h_expr = h_expr * (t - t_j)
    q_star = Poly(q_true.as_expr() + h_expr, t, domain=F)

    roots = set(planted)
    if alpha != 0:
        roots.add((-beta * pow(alpha, -1, p)) % p)
    return q_star, sorted(int(z) for z in roots)


"""
END: DISHONEST-PROVER HELPERS (GKR LEVEL)
"""


"""
START: LAYER TRANSITION
"""


@dataclass
class LayerTransitionResult:
    status: str                        # "continue" | "accept" | "reject" | "abort"
    i: int
    lie_on_entry: bool = False
    laundered: bool = False            # did the lie become TRUE at some point in this layer?
    rho_next: Tuple = ()
    alpha_next: Union[int, ModularInteger] = 0
    notes: List[str] = dataclass_field(default_factory=list)
    # transcript details (kept for inspection / future refactor)
    r_x: Tuple = ()
    r_y: Tuple = ()
    gamma: Optional[int] = None
    A: Optional[int] = None
    M: Optional[int] = None
    z_x_true: Optional[int] = None
    z_y_true: Optional[int] = None
    zx_star: Optional[int] = None
    zy_star: Optional[int] = None
    q: Optional[Poly] = None
    q_star: Optional[Poly] = None
    tau: Optional[int] = None


def _prompt_endpoint_pair(
    *,
    field: FiniteField,
    suggestion: Tuple[ModularInteger, ModularInteger],
    i: int,
    out: TerminalOutput,
    max_attempts: int = 3,
) -> Optional[Tuple[ModularInteger, ModularInteger]]:
    """Let a user-prover accept the suggested (z*_x, z*_y) with 'y', type their own pair, or cancel."""
    prompt = (
        f"\nEnter 'y' to send the suggested pair, type your own as 'z*_x, z*_y' "
        f"(two integers), or type 'cancel' to abort: "
    )
    for attempt in range(1, max_attempts + 1):
        raw = out.input(prompt).strip()
        if raw.lower() == "cancel":
            return None
        if raw.lower() == "y":
            return suggestion
        parts = [s for s in raw.replace(",", " ").split() if s]
        try:
            if len(parts) != 2:
                raise ValueError("expected exactly two integers")
            zx = field.convert(int(parts[0]))
            zy = field.convert(int(parts[1]))
            return zx, zy
        except Exception as e:
            out.print(f"\nCould not parse the pair: {e}")
            if attempt < max_attempts:
                out.print(f"Try again ({attempt}/{max_attempts}).")
    return None


def _prompt_q_polynomial(
    *,
    field: FiniteField,
    suggestion: Poly,
    t: Symbol,
    i: int,
    out: TerminalOutput,
    max_attempts: int = 3,
) -> Optional[Poly]:
    """Let a user-prover accept the suggested q* with 'y', type their own polynomial in t, or cancel."""
    prompt = (
        f"\nEnter 'y' to send the suggested polynomial, type your own q*_{i + 1}(t), "
        f"or type 'cancel' to abort: "
    )
    for attempt in range(1, max_attempts + 1):
        raw = out.input(prompt).strip()
        if raw.lower() == "cancel":
            return None
        if raw.lower() == "y":
            return suggestion
        try:
            return parse_poly(raw, field=field, gens=[t], preferred_order=None, strict=True)
        except Exception as e:
            out.print(f"\nCould not parse polynomial: {e}")
            if attempt < max_attempts:
                out.print(f"Try again ({attempt}/{max_attempts}).")
    return None


def gkr_layer_transition(
    ac: ArithmeticCircuit,
    *,
    i: int,
    rho_i: Tuple[Union[int, ModularInteger], ...],
    alpha_i: Union[int, ModularInteger],
    final_layer: bool,
    user_is_prover: bool = False,
    user_is_verifier: bool = False,
    secret_mode: bool = False,
    show_steps: bool = True,
    initial_claim_false: bool = False,
    out: TerminalOutput = default_out,
) -> LayerTransitionResult:
    """
    One layer of the GKR protocol: the sum-check over Thaler's identity at layer i,
    followed by either

      - the FOLDING step (P supplies claimed endpoints z*_x, z*_y and a restriction
        q*_{i+1} of W-tilde_{i+1} to the line through r_x and r_y; V folds the two
        endpoint claims into one via a random tau), when i < d - 1; or

      - the FINAL CHECK (V evaluates W-tilde_d at r_x and r_y directly from the
        public inputs and checks the bridging equation), when i = d - 1.

    The carried claim beta*_i may be false; in that case the prover is FORCED to forge
    (round polynomials inside the sum-check, then endpoints and q* at the folding step)
    to keep the transcript consistent -- unless a verifier challenge launders the lie.
    """
    F: FiniteField = ac.field
    p = int(F.mod)
    d: int = ac.depth
    s_i = _label_bitlength(ac, i)
    s_next = _label_bitlength(ac, i + 1)
    m = 2 * s_next  # number of sum-check variables/rounds

    res = LayerTransitionResult(status="reject", i=i)

    # ------------------------------------------------------------------
    # Build the Thaler-identity summand g(x, y)
    # ------------------------------------------------------------------
    add_i = replace_symbols_in_polynomial(ac.tilde_add[i], v=s_i, w=s_next)
    mult_i = replace_symbols_in_polynomial(ac.tilde_mult[i], v=s_i, w=s_next)

    z_syms = list(symbols(f"z_:{s_i}"))
    x_syms = list(symbols(f"x_:{s_next}"))
    y_syms = list(symbols(f"y_:{s_next}"))

    z_subs = {z_syms[j]: int(rho_i[j]) for j in range(s_i)}
    add_xy = Poly(add_i.as_expr().subs(z_subs), *(x_syms + y_syms), domain=F)
    mult_xy = Poly(mult_i.as_expr().subs(z_subs), *(x_syms + y_syms), domain=F)

    W_next = normalize_to_x_vars(ac.tilde_W[i + 1], s_next)
    Wx_expr = W_next.as_expr().subs({W_next.gens[j]: x_syms[j] for j in range(s_next)})
    Wy_expr = W_next.as_expr().subs({W_next.gens[j]: y_syms[j] for j in range(s_next)})

    g_expr = add_xy.as_expr() * (Wx_expr + Wy_expr) + mult_xy.as_expr() * (Wx_expr * Wy_expr)
    g_poly = Poly(g_expr, *(x_syms + y_syms), domain=F)

    # ------------------------------------------------------------------
    # Truth (omniscient bookkeeping) and the carried claim
    # ------------------------------------------------------------------
    alpha_i = F.convert(int(alpha_i))
    w_i_true = _eval_tilde(ac.tilde_W[i], rho_i, F)
    lie_active = bool(alpha_i != w_i_true)
    res.lie_on_entry = lie_active

    # ------------------------------------------------------------------
    # Preamble
    # ------------------------------------------------------------------
    print_header(f"GKR layer {i} \u2192 {i + 1}: sum-check", level=1, out=out)

    xy_ = stringify(x_syms + y_syms)
    x_ = stringify(x_syms)
    y_ = stringify(y_syms)

    out.print(
        f"\nAt the start of this layer, V holds \u03c1_{i} = {_point_str(rho_i)} and the "
        f"carried claim \u03b1_{i} = {int(alpha_i)} (the claim being that "
        f"W\u0303_{i}(\u03c1_{i}) = \u03b1_{i})."
    )
    out.print(
        f"\nBy Thaler's identity,\n\nW\u0303_{i}(\u03c1_{i}) = sum g({xy_}) over "
        f"({xy_}) in {{0,1}}^{m},\n\nwhere\n\ng({xy_}) := "
        f"add\u0303_{i}(\u03c1_{i},{x_},{y_})\u00b7[W\u0303_{i + 1}({x_}) + W\u0303_{i + 1}({y_})] "
        f"+ mult\u0303_{i}(\u03c1_{i},{x_},{y_})\u00b7[W\u0303_{i + 1}({x_})\u00b7W\u0303_{i + 1}({y_})]."
    )
    out.print(
        f"\nV can evaluate add\u0303_{i} and mult\u0303_{i} anywhere (the wiring is public), "
        f"but NOT W\u0303_{i + 1}, so V cannot evaluate g pointwise. So we run the sum-check "
        f"protocol on g, with claimed sum H* := \u03b1_{i} = {int(alpha_i)}, deferring "
        f"the evaluation of g."
    )

    degree_bounds = [2] * m
    out.print(
        f"\nFor soundness, V relies on degree bounds per variable (this is public "
        f"information): {degree_bounds}. (Each variable has degree \u2264 1 in the wiring "
        f"MLE and \u2264 1 in W\u0303_{i + 1}, hence degree \u2264 2 in g.)"
    )

    if not secret_mode:
        out.print(
            f"\n{YELLOW}We display g for the reader. In the protocol, V cannot compute g "
            f"(it involves W\u0303_{i + 1}):{RESET}\n\ng({xy_}) = {_truncate_expr(g_poly)}."
        )
        if lie_active:
            out.print(
                f"\n{RED}The carried claim is false: in fact W\u0303_{i}(\u03c1_{i}) = "
                f"{int(w_i_true)} \u2260 {int(alpha_i)} = \u03b1_{i}. To survive this "
                f"sum-check, P is forced to forge round polynomials.{RESET}"
            )

    # ------------------------------------------------------------------
    # The sum-check itself
    # ------------------------------------------------------------------
    r: List[Union[int, ModularInteger]] = []
    dishonest = [lie_active]
    sum_check_recursion.call_count = 0
    gamma = sum_check_recursion(
        g_init=g_poly,
        g=g_poly,
        H_star=alpha_i,
        r=r,
        dishonest=dishonest,
        user_is_verifier=user_is_verifier,
        user_is_prover=user_is_prover,
        show_steps=show_steps,
        skip_show_step=True,          # GKR prints its own preamble; skip the generic init block
        secret_mode=secret_mode,
        degree_bounds=degree_bounds,
        return_final_value=True,      # no oracle check here: the bridging equation judges truth
        show_final_check=False,
        out=out,
    )

    if gamma is None:
        res.status = "abort"
        return res
    if gamma is False:
        out.print(f"\n{RED}Protocol failed during the layer {i} sum-check.{RESET}")
        res.status = "reject"
        res.notes.append(f"Layer {i}: V rejected during the sum-check.")
        return res

    gamma_F = F.convert(int(gamma))
    r_x = tuple(r[:s_next])
    r_y = tuple(r[s_next:])
    res.r_x, res.r_y, res.gamma = r_x, r_y, int(gamma_F)

    # Public wiring values at (rho_i, r_x, r_y)
    xy_subs = {x_syms[j]: int(r_x[j]) for j in range(s_next)}
    xy_subs.update({y_syms[j]: int(r_y[j]) for j in range(s_next)})
    A_val = F.convert(add_xy.eval(xy_subs))
    M_val = F.convert(mult_xy.eval(xy_subs))
    res.A, res.M = int(A_val), int(M_val)

    # True endpoint values (omniscient bookkeeping)
    z_x_true = _eval_tilde(ac.tilde_W[i + 1], r_x, F)
    z_y_true = _eval_tilde(ac.tilde_W[i + 1], r_y, F)
    res.z_x_true, res.z_y_true = int(z_x_true), int(z_y_true)

    true_bridge = F.convert(A_val * (z_x_true + z_y_true) + M_val * z_x_true * z_y_true)
    transcript_consistent_with_truth = bool(gamma_F == true_bridge)

    laundered_in_sumcheck = lie_active and transcript_consistent_with_truth
    if laundered_in_sumcheck:
        res.laundered = True
        res.notes.append(
            f"Layer {i}: a sum-check challenge hit a root of a forged polynomial; "
            f"the lie was laundered (\u03b3 = g(r_x, r_y))."
        )
    if lie_active:
        res.notes.append(
            f"Layer {i}: the carried claim was false (\u03b1_{i} = {int(alpha_i)}, "
            f"true value {int(w_i_true)}); P forged round polynomials in the sum-check."
        )

    # ------------------------------------------------------------------
    # Post-sum-check narration
    # ------------------------------------------------------------------
    out.print(
        f"\nUnlike in the standalone sum-check protocol, V does not now evaluate "
        f"g(r_x, r_y): g involves W\u0303_{i + 1}, which V does not know. The transcript's "
        f"terminal claim is\n\n\u03b3 := g*_{m - 1}(r_{m - 1}) = {int(gamma_F)},\n\nthe claim "
        f"being that \u03b3 = g(r_x, r_y), where r_x = {_point_str(r_x)} and r_y = {_point_str(r_y)}."
    )
    out.print(
        f"\nV computes the (public) wiring values at this point:\n"
    )
    display_aligned(
        f"A = add\u0303_{i}(\u03c1_{i}, r_x, r_y) = {int(A_val)}",
        f"M = mult\u0303_{i}(\u03c1_{i}, r_x, r_y) = {int(M_val)}",
        out=out,
    )
    out.print(
        f"\nUnpacking the definition of g, the claim \u03b3 = g(r_x, r_y) says exactly that\n\n"
        f"\u03b3 = A\u00b7[W\u0303_{i + 1}(r_x) + W\u0303_{i + 1}(r_y)] "
        f"+ M\u00b7[W\u0303_{i + 1}(r_x)\u00b7W\u0303_{i + 1}(r_y)]   (the 'bridging equation')."
    )

    if not secret_mode and laundered_in_sumcheck:
        out.print(
            f"\n{YELLOW}During this sum-check, a verifier challenge hit a root of a forged "
            f"polynomial: the terminal claim \u03b3 now equals the true value g(r_x, r_y). "
            f"The lie has been laundered, and P can proceed honestly.{RESET}"
        )

    # ==================================================================
    # FINAL LAYER: no folding -- V checks the bridging equation directly
    # ==================================================================
    if final_layer:
        print_header("Final check", level=2, out=out)
        out.print(
            f"\nLayer {d} is the input layer. The inputs are public, so V can compute "
            f"W\u0303_{d} -- and hence both endpoint values -- directly, with no help from P:"
        )
        display_aligned(
            f"z_x = W\u0303_{d}(r_x) = {int(z_x_true)}",
            f"z_y = W\u0303_{d}(r_y) = {int(z_y_true)}",
            out=out,
        )
        rhs = F.convert(A_val * (z_x_true + z_y_true) + M_val * z_x_true * z_y_true)
        out.print(f"\nV checks the bridging equation \u03b3 = A\u00b7(z_x + z_y) + M\u00b7z_x\u00b7z_y:\n")
        display_aligned(
            f"\u03b3 = {int(gamma_F)}",
            f"A\u00b7(z_x + z_y) + M\u00b7z_x\u00b7z_y = {int(rhs)}",
            out=out,
        )
        if gamma_F == rhs:
            out.print(
                f"\nP passes the final verification, and V {GREEN}ACCEPTS{RESET} P's claimed output(s)."
            )
            if initial_claim_false:
                out.print(
                    f"\n{RED}P HAS DECEIVED V: THE CLAIMED OUTPUT(S) ARE IN FACT FALSE.{RESET}"
                )
                out.print(
                    f"\n{YELLOW}P GOT LUCKY:{RESET} at some point a random verifier challenge "
                    f"happened to land where a forged object agreed with the true one. Over a "
                    f"large field, this success event should be rare."
                )
            res.status = "accept"
            return res
        else:
            out.print(
                f"\nP fails the final verification, and V {RED}REJECTS{RESET} P's claimed output(s)."
            )
            out.print(
                f"\n{YELLOW}Interpretation: P can often keep each layer locally consistent, "
                f"but the final evaluation against the public inputs ties the entire transcript "
                f"to the true circuit and typically catches a lie.\n{RESET}"
            )
            res.status = "reject"
            res.notes.append(f"Layer {i}: the final check against the public inputs failed.")
            return res

    # ==================================================================
    # MIDDLE LAYER: bridging + folding
    # ==================================================================
    print_header(f"Layer {i} folding", level=1, out=out)

    out.print(
        f"\nV cannot check the bridging equation alone: it involves W\u0303_{i + 1}(r_x) and "
        f"W\u0303_{i + 1}(r_y), which V cannot compute. So P supplies claimed values\n\n"
        f"z*_x (the claim: z*_x = W\u0303_{i + 1}(r_x))   and   z*_y (the claim: z*_y = W\u0303_{i + 1}(r_y))."
    )

    prover_must_cheat = not transcript_consistent_with_truth

    t = symbols("t")

    # The line \u2113(t) := (1 - t)\u00b7r_x + t\u00b7r_y and the TRUE restriction q(t) := W\u0303_{i+1}(\u2113(t)).
    line_subs = {
        W_next.gens[j]: ((1 - t) * int(r_x[j]) + t * int(r_y[j]))
        for j in range(s_next)
    }
    q = Poly(W_next.as_expr().subs(line_subs), t, domain=F)
    res.q = q

    zx_star: ModularInteger
    zy_star: ModularInteger
    kept: Optional[str] = None
    caught_impossible = False

    if not prover_must_cheat:
        zx_star, zy_star = z_x_true, z_y_true
        if not secret_mode and lie_active and laundered_in_sumcheck:
            out.print(
                f"\n{YELLOW}Since the lie has been laundered, the TRUE values now satisfy the "
                f"bridging equation: P sends them and plays honestly from here.{RESET}"
            )
    else:
        suggestion = dishonest_folding_values(
            field=F, A=A_val, M=M_val, gamma=gamma_F,
            z_x_true=z_x_true, z_y_true=z_y_true,
        )
        if suggestion is None:
            caught_impossible = True
            if not secret_mode:
                out.print(
                    f"\n{RED}No pair (z*_x, z*_y) can satisfy the bridging equation: A = M = 0 "
                    f"at this point while \u03b3 \u2260 0. P is caught, no matter what P sends.{RESET}"
                )
            zx_star, zy_star = z_x_true, z_y_true
        else:
            zx_s, zy_s, kept = suggestion
            if kept == "both":
                # Vacuous bridging constraint: the truth satisfies it; the lie evaporates.
                zx_star, zy_star = zx_s, zy_s
                res.laundered = True
                res.notes.append(
                    f"Layer {i} folding: A = M = 0 and \u03b3 = 0, so the bridging equation was "
                    f"vacuous; P claimed the true values and the lie was laundered."
                )
                if not secret_mode:
                    out.print(
                        f"\n{YELLOW}Here A = M = 0 and \u03b3 = 0, so the bridging equation is "
                        f"vacuous: P can claim the TRUE values, and the lie is laundered.{RESET}"
                    )
            elif user_is_prover:
                out.print(f"\n{RED}=== START INVISIBLE TO VERIFIER ==={RESET}")
                out.print(
                    f"\nIn fact,\n\n{GREEN}W\u0303_{i + 1}(r_x) = {int(z_x_true)}   and   "
                    f"W\u0303_{i + 1}(r_y) = {int(z_y_true)}{RESET},"
                )
                out.print(
                    f"\nbut these true values do NOT satisfy the bridging equation (your \u03b3 is "
                    f"a surviving lie), so you must lie about at least one endpoint."
                )
                out.print(
                    f"\nWhatever pair you send must satisfy\n\n"
                    f"{int(gamma_F)} = {int(A_val)}\u00b7(z*_x + z*_y) + {int(M_val)}\u00b7z*_x\u00b7z*_y."
                )
                if kept == "x":
                    out.print(
                        f"\nFor example, keep z*_x = W\u0303_{i + 1}(r_x) = {int(zx_s)} (true) and "
                        f"take {RED}z*_y = {int(zy_s)}{RESET}. Lying about only one endpoint "
                        f"will plant t = 0 as a root of q*_{i + 1} - q_{i + 1} at the next step "
                        f"for free."
                    )
                elif kept == "y":
                    out.print(
                        f"\nFor example, keep z*_y = W\u0303_{i + 1}(r_y) = {int(zy_s)} (true) and "
                        f"take {RED}z*_x = {int(zx_s)}{RESET}. Lying about only one endpoint "
                        f"will plant t = 1 as a root of q*_{i + 1} - q_{i + 1} at the next step "
                        f"for free."
                    )
                else:
                    out.print(
                        f"\nFor example, take {RED}(z*_x, z*_y) = ({int(zx_s)}, {int(zy_s)}){RESET}."
                    )
                pair = _prompt_endpoint_pair(field=F, suggestion=(zx_s, zy_s), i=i, out=out)
                out.print(f"\n{RED}=== END INVISIBLE TO VERIFIER ==={RESET}")
                if pair is None:
                    out.print(f"\n{RED}Input cancelled or invalid too many times. Aborting this run.{RESET}")
                    res.status = "abort"
                    return res
                zx_star, zy_star = pair
            else:
                zx_star, zy_star = zx_s, zy_s
                if not secret_mode:
                    if kept == "x":
                        forged = f"keeps z*_x true and forges z*_y"
                    elif kept == "y":
                        forged = f"keeps z*_y true and forges z*_x"
                    else:
                        forged = f"forges both endpoints"
                    out.print(
                        f"\n{RED}The true endpoint values fail the bridging equation (\u03b3 is a "
                        f"surviving lie), so P {forged}, choosing a pair consistent with \u03b3.{RESET}"
                    )
            if kept in ("x", "y") and not caught_impossible:
                res.notes.append(
                    f"Layer {i} folding: P kept z*_{kept} true and forged the other endpoint."
                )
            elif kept is None and not caught_impossible:
                res.notes.append(f"Layer {i} folding: P forged both endpoints.")

    res.zx_star, res.zy_star = int(zx_star), int(zy_star)

    # ------------------------------------------------------------------
    # V's bridging check
    # ------------------------------------------------------------------
    out.print(f"\nP sends z*_x = {int(zx_star)} and z*_y = {int(zy_star)}.")
    rhs = F.convert(A_val * (zx_star + zy_star) + M_val * zx_star * zy_star)
    out.print(f"\nV checks the bridging equation \u03b3 = A\u00b7(z*_x + z*_y) + M\u00b7z*_x\u00b7z*_y:\n")
    display_aligned(
        f"\u03b3 = {int(gamma_F)}",
        f"A\u00b7(z*_x + z*_y) + M\u00b7z*_x\u00b7z*_y = {int(rhs)}",
        out=out,
    )
    if gamma_F != rhs:
        out.print(f"\nV {RED}REJECTS{RESET} (bridging equation failed). The protocol terminates.")
        res.status = "reject"
        res.notes.append(f"Layer {i} folding: the bridging equation failed.")
        return res
    out.print(f"\nV sees that P's claims so far are consistent.")

    # ------------------------------------------------------------------
    # The restriction q*_{i+1} along the line
    # ------------------------------------------------------------------
    out.print(
        f"\nWe now hold TWO claims about W\u0303_{i + 1} (at r_x and at r_y). To avoid the "
        f"number of claims doubling at every layer, V folds them into ONE, as follows."
    )
    out.print(
        f"\nLet \u2113(t) := (1 - t)\u00b7r_x + t\u00b7r_y (the line through r_x = \u2113(0) and "
        f"r_y = \u2113(1)), and let q_{i + 1}(t) := W\u0303_{i + 1}(\u2113(t)), a univariate "
        f"polynomial of degree \u2264 s_{i + 1} = {s_next}."
    )
    out.print(
        f"\nP supplies a polynomial q*_{i + 1} (the claim: q*_{i + 1} = q_{i + 1}). "
        f"V checks that\n\n(a) deg(q*_{i + 1}) \u2264 {s_next}, and "
        f"(b) q*_{i + 1}(0) = z*_x and q*_{i + 1}(1) = z*_y."
    )

    forged_q = prover_must_cheat and not caught_impossible and kept != "both"

    if not forged_q:
        q_star = q
        roots_of_diff: List[int] = []
    else:
        q_star_suggestion, roots_of_diff = dishonest_q_polynomial(
            q_true=q, zx_star=zx_star, zy_star=zy_star,
            deg_bound=s_next, field=F, t=t,
        )
        if user_is_prover:
            out.print(f"\n{RED}=== START INVISIBLE TO VERIFIER ==={RESET}")
            out.print(f"\nIn fact,\n\n{GREEN}q_{i + 1}(t) = {q.as_expr()}{RESET},")
            out.print(
                f"\nbut q_{i + 1}(0) = {int(z_x_true)} and q_{i + 1}(1) = {int(z_y_true)}: the "
                f"true restriction does not match your claimed endpoints, so you must forge "
                f"q*_{i + 1} to pass check (b)."
            )
            out.print(
                f"\nAfter checks (a) and (b), V will sample \u03c4_{i + 1} uniformly at random "
                f"from {F} and carry the single claim\n\n\u03b1_{i + 1} := q*_{i + 1}(\u03c4_{i + 1}) "
                f"= W\u0303_{i + 1}(\u2113(\u03c4_{i + 1}))  (a claim about the point "
                f"\u03c1_{i + 1} := \u2113(\u03c4_{i + 1}))."
            )
            out.print(
                f"\nIf \u03c4_{i + 1} is a root of q*_{i + 1} - q_{i + 1}, the carried claim will "
                f"be TRUE, and you can play honestly for the rest of the protocol."
            )
            out.print(
                f"\nAs you don't know what \u03c4_{i + 1} will be, the best you can do is choose "
                f"q*_{i + 1} satisfying (a) and (b) such that q*_{i + 1} - q_{i + 1} has as many "
                f"roots as possible in {F} (there can be at most deg(q*_{i + 1} - q_{i + 1}) "
                f"\u2264 {s_next})."
            )
            if roots_of_diff:
                print_roots = ", ".join(f"{YELLOW}{z}{RESET}" for z in roots_of_diff)
                out.print(
                    f"\nFor example, if\n\n{RED}q*_{i + 1}(t) = {q_star_suggestion.as_expr()}{RESET},"
                    f"\n\nthen (a) and (b) hold, and the roots (in {F}) of "
                    f"q*_{i + 1} - q_{i + 1} are: {print_roots}."
                )
                out.print(
                    f"\nThe probability of V sampling one of these roots as \u03c4_{i + 1} is "
                    f"{len(roots_of_diff)}/{p} = {len(roots_of_diff)/p:.10f}."
                )
                out.print(
                    f"\nIn general, by Schwartz-Zippel, this probability cannot exceed "
                    f"s_{i + 1}/#F = {s_next}/{p} = {s_next/p:.10f}."
                )
            else:
                out.print(
                    f"\nFor example, if\n\n{RED}q*_{i + 1}(t) = {q_star_suggestion.as_expr()}{RESET},"
                    f"\n\nthen (a) and (b) hold, but q*_{i + 1} - q_{i + 1} has no roots in {F}."
                )
            q_star = _prompt_q_polynomial(field=F, suggestion=q_star_suggestion, t=t, i=i, out=out)
            out.print(f"\n{RED}=== END INVISIBLE TO VERIFIER ==={RESET}")
            if q_star is None:
                out.print(f"\n{RED}Input cancelled or invalid too many times. Aborting this run.{RESET}")
                res.status = "abort"
                return res
        else:
            q_star = q_star_suggestion
            if not secret_mode:
                print_roots = ", ".join(f"{YELLOW}{z}{RESET}" for z in roots_of_diff) if roots_of_diff else "(none)"
                out.print(
                    f"\n{RED}P forges q*_{i + 1} to match the claimed endpoints{RESET}, planting "
                    f"as many agreement points with the true q_{i + 1} as the degree bound allows; "
                    f"the roots of q*_{i + 1} - q_{i + 1} are: {print_roots}."
                )
        res.notes.append(
            f"Layer {i} folding: P forged q*_{i + 1}; roots of q*_{i + 1} - q_{i + 1}: "
            f"{roots_of_diff if roots_of_diff else 'none'}."
        )

    res.q_star = q_star

    # ------------------------------------------------------------------
    # V's checks on q*
    # ------------------------------------------------------------------
    out.print(f"\nP claims that q_{i + 1}(t) = q*_{i + 1}(t), where\n\nq*_{i + 1}(t) = {q_star.as_expr()}.")

    q_deg = q_star.degree()
    if isinstance(q_deg, int) and q_deg > s_next:
        out.print(f"\nV finds that deg(q*_{i + 1}) = {q_deg} > s_{i + 1} = {s_next}.")
        out.print(f"\nV {RED}REJECTS{RESET} (degree bound violated). The protocol terminates.")
        res.status = "reject"
        res.notes.append(f"Layer {i} folding: q* violated the degree bound.")
        return res
    out.print(f"\nV checks the degree bound: deg(q*_{i + 1}) = {q_deg} \u2264 s_{i + 1} = {s_next}.")

    q_star_0 = F.convert(q_star.eval({t: 0}))
    q_star_1 = F.convert(q_star.eval({t: 1}))
    out.print(f"\nV checks the endpoints:\n")
    display_aligned(
        f"q*_{i + 1}(0) = {int(q_star_0)}  (should be z*_x = {int(zx_star)})",
        f"q*_{i + 1}(1) = {int(q_star_1)}  (should be z*_y = {int(zy_star)})",
        out=out,
    )
    if q_star_0 != F.convert(zx_star) or q_star_1 != F.convert(zy_star):
        out.print(f"\nV {RED}REJECTS{RESET} (endpoint check failed). The protocol terminates.")
        res.status = "reject"
        res.notes.append(f"Layer {i} folding: q*'s endpoints did not match (z*_x, z*_y).")
        return res
    out.print(f"\nV sees that P's claims so far are consistent.")

    # ------------------------------------------------------------------
    # Fold: sample tau, define rho_{i+1}, carry beta*_{i+1}
    # ------------------------------------------------------------------
    verifier_prompt = (
        f"\nAs verifier, choose an element of {F} uniformly at random, independent of any "
        f"previous choice (this will be \u03c4_{i + 1}):"
    ) if user_is_verifier else None
    tau = random_field_element(field=F, user_input=user_is_verifier, custom_message=verifier_prompt, out=out)
    if tau is None:
        res.status = "abort"
        return res
    tau_F = F.convert(int(tau))
    res.tau = int(tau_F)

    rho_next = tuple(
        F.convert((1 - int(tau_F)) * int(r_x[j]) + int(tau_F) * int(r_y[j]))
        for j in range(s_next)
    )
    alpha_next = F.convert(q_star.eval({t: int(tau_F)}))

    out.print(f"\nV samples an element uniformly at random from {F}; here \u03c4_{i + 1} = {int(tau_F)}.")
    out.print(
        f"\nV sets \u03c1_{i + 1} := \u2113(\u03c4_{i + 1}) = {_point_str(rho_next)} and carries the "
        f"single claim\n\n\u03b1_{i + 1} := q*_{i + 1}(\u03c4_{i + 1}) = {int(alpha_next)}\n\n(the "
        f"claim being that \u03b1_{i + 1} = W\u0303_{i + 1}(\u03c1_{i + 1})). The protocol proceeds "
        f"to the next layer."
    )

    # Omniscient bookkeeping: did the fold launder the lie?
    w_next_true = _eval_tilde(ac.tilde_W[i + 1], rho_next, F)
    if forged_q and alpha_next == w_next_true:
        res.laundered = True
        res.notes.append(
            f"Layer {i} folding: \u03c4_{i + 1} = {int(tau_F)} hit a root of "
            f"q*_{i + 1} - q_{i + 1}; the carried claim became TRUE."
        )
        if user_is_prover:
            out.print(f"\n{RED}=== START INVISIBLE TO VERIFIER ==={RESET}")
            out.print(
                f"\n{RED}YOU HAVE SUCCESSFULLY DECEIVED THE VERIFIER: "
                f"q*_{i + 1}(\u03c4_{i + 1}) = q_{i + 1}(\u03c4_{i + 1}), i.e. the carried claim "
                f"\u03b1_{i + 1} = W\u0303_{i + 1}(\u03c1_{i + 1}) is TRUE.{RESET}"
            )
            out.print(f"\n{RED}From now on, honest play suffices.{RESET}")
            out.print(f"\n{RED}=== END INVISIBLE TO VERIFIER ==={RESET}")
        elif not secret_mode:
            out.print(
                f"\n{YELLOW}\u03c4_{i + 1} = {int(tau_F)} hit a root of q*_{i + 1} - q_{i + 1}: "
                f"the carried claim is now TRUE. The lie has been laundered, and P can proceed "
                f"honestly.{RESET}"
            )

    res.status = "continue"
    res.rho_next = rho_next
    res.alpha_next = alpha_next
    return res


"""
END: LAYER TRANSITION
"""


"""
START: THE GKR PROTOCOL (INTERACTIVE ENTRY POINT)
"""


def gkr(
    ac: Optional[ArithmeticCircuit] = None,
    *,
    secret_mode: Optional[bool] = None,
    show_steps: bool = True,
    out: TerminalOutput = default_out,
) -> Optional[bool]:
    """
    Sets up and runs the GKR protocol interactively, mirroring `sum_check`.

    This function:
    - Asks the user whether the protocol should run interactively and whether they wish
      to act as prover and/or verifier.
    - Prompts for a prime field and an arithmetic circuit (unless `ac` is provided).
    - Lets the prover claim the circuit's output(s) -- honestly or not. If the user is
      not the prover, the user chooses a scenario in which the machine prover may be
      dishonest about the claimed output(s).
    - Runs the layer-by-layer GKR protocol: at each layer, a sum-check over Thaler's
      identity, followed by the bridging check and the folding step (or, at the last
      layer, the final check against the public inputs).
    - A prover whose claimed output is false is FORCED to forge, consistently, at every
      subsequent step -- unless a random verifier challenge launders the lie.

    Returns:
        Optional[bool]:
            - True if the verifier accepts.
            - False if the verifier rejects.
            - None if the run is aborted (cancelled input, invalid circuit, ...).
    """
    if hasattr(out, "flush"):
        out.flush()

    # ---- interactivity and roles (mirrors sum_check) ----
    interactive_input = out.input("\nDo you want this to be interactive? (y/n): ")
    user_input = interactive_input.strip().lower() == 'y'
    if not user_input:
        out.print("\nAlthough you've selected non-interative mode, responses to a few prompts are still required...")

    user_is_verifier: bool = False
    user_is_prover: bool = False

    if user_input:
        user_selection_prover = out.input("Do you want to act as prover? (y/n): ")
        user_selection_verifier = out.input("Do you want to act as verifier? (y/n): ")
        user_is_prover = user_selection_prover.strip().lower() == 'y'
        user_is_verifier = user_selection_verifier.strip().lower() == 'y'

    if secret_mode is None:
        secret_mode = (user_is_verifier and not user_is_prover)

    # ---- field and circuit ----
    if ac is None:
        ac = choose_arithmetic_circuit(out=out)
        if ac is None:
            out.print(f"\n{YELLOW}Protocol aborted.{RESET}")
            return None
    else:
        # Validate a user-supplied circuit the same way.
        ok = (
            getattr(ac, "is_dag", False)
            and getattr(ac, "fan_in_two", False)
            and all(hasattr(ac, attr) for attr in ("W_dict", "tilde_W", "tilde_add", "tilde_mult"))
            and ac.depth is not None and ac.depth >= 1
            and all(_label_bitlength(ac, layer) >= 1 for layer in range(1, ac.depth + 1))
        )
        if not ok:
            out.print(f"\n{RED}The supplied circuit cannot be used for GKR (see the hints in choose_arithmetic_circuit).{RESET}")
            return None

    F: FiniteField = ac.field
    p = int(F.mod)
    d: int = ac.depth
    s_list = [_label_bitlength(ac, layer) for layer in range(d + 1)]
    S_list = [len(ac.layers[layer]) for layer in range(d + 1)]
    s0 = s_list[0]

    # ---- initialization ----
    print_header("Initialization", out=out)

    out.print(f"\nThe arithmetic circuit C is defined over {F} and has depth {d}.")
    out.print(f"\nLayer sizes: " + ", ".join(f"S_{layer} = {S_list[layer]}" for layer in range(d + 1)) + ".")
    out.print(f"\nGate-label bit-lengths: " + ", ".join(f"s_{layer} = {s_list[layer]}" for layer in range(d + 1)) + ".")
    out.print(f"\n(Layer 0 holds the output gate(s); layer {d} holds the inputs.)")

    if _in_notebook():
        _ipython_display(ac.graphviz_circuit_bitstring)
    else:
        out.print(
            f"\n(Running in a terminal: to render the circuit, call the .view() method of "
            f"your ArithmeticCircuit, e.g. ArithmeticCircuit(...).view().)"
        )

    input_items = sorted(ac.W_dict[d].items())
    inputs_str = ", ".join(f"W_{d}({stringify(lbl)}) = {int(v)}" for lbl, v in input_items)
    out.print(
        f"\nPublic information: the circuit topology -- and hence the wiring predicates "
        f"add_i, mult_i and their multilinear extensions add\u0303_i, mult\u0303_i, which V can "
        f"evaluate anywhere -- together with the inputs:\n\n{inputs_str}."
    )
    out.print(
        f"\nIn particular, V can compute W\u0303_{d} directly. What V does NOT know (and does "
        f"not want to compute) are the interior gate values and the output(s): verifying a "
        f"claim about the output(s), without re-executing C, is the whole point of the protocol."
    )

    true_outputs = {label: int(v) for label, v in ac.W_dict[0].items()}
    output_labels = sorted(true_outputs.keys())

    if not secret_mode:
        truth_str = ", ".join(f"W_0({stringify(lbl)}) = {true_outputs[lbl]}" for lbl in output_labels)
        out.print(
            f"\n{YELLOW}We display the true output(s) for the reader. In the protocol, V does "
            f"not know these:{RESET}\n\n{truth_str}."
        )

    # ---- the prover's claimed output(s) ----
    print_header("Claimed output(s)", out=out)

    claims: Dict[Tuple[int, ...], int] = {}

    if user_is_prover:
        for lbl in output_labels:
            true_v = true_outputs[lbl]
            if secret_mode is True:
                prompt = f"\nAs prover, enter your claim for output gate W_0({stringify(lbl)}): "
            else:
                prompt = (
                    f"\nAs prover, enter your claim for output gate W_0({stringify(lbl)}) "
                    f"(the true value is {true_v}): "
                )
            value: Optional[int] = None
            for attempt in range(1, 4):
                raw = out.input(prompt, hidden=bool(secret_mode)).strip()
                if raw.lower() == "cancel":
                    out.print(f"\n{YELLOW}Protocol aborted.{RESET}")
                    return None
                try:
                    value = int(F.convert(int(raw)))
                    break
                except Exception:
                    out.print(f"\nInvalid integer. Try again ({attempt}/3).")
            if value is None:
                out.print(f"\n{YELLOW}Aborting: invalid claimed output.{RESET}")
                return None
            claims[lbl] = value
    else:
        dishonesty_selection = out.input(
            f"\nChoose a, b, or c: About the claimed circuit output(s), the prover will be "
            f"(a) honest. "
            f"(b) honest with probability 1/2. "
            f"(c) dishonest.",
            hidden=secret_mode,
        ).strip().lower()
        if dishonesty_selection == "a":
            dishonest_claim = False
        elif dishonesty_selection == "b":
            dishonest_claim = bool(random.randint(0, 1))
        else:  # c or anything other than a or b
            dishonest_claim = True
        claims = _machine_claimed_outputs(ac, dishonest_claim)

    initial_claim_false = (claims != true_outputs)

    # The claimed outputs are a protocol message: V receives them.
    claims_str = ", ".join(f"W*_0({stringify(lbl)}) = {claims[lbl]}" for lbl in output_labels)
    out.print(f"\nP claims that the circuit output(s) are:\n\n{claims_str}.")

    if initial_claim_false and not (secret_mode is True):
        out.print(
            f"\n{RED}In this run, P's claimed output(s) are intentionally false, and P will "
            f"try to get away with it.{RESET}"
        )

    # ---- reduce the output claim to a single point-claim about W-tilde_0 ----
    out.print(
        f"\nV forms the multilinear extension W\u0303*_0 of the claimed outputs (defining the "
        f"claimed-output function to be 0 on the {2**s0 - len(output_labels)} unused "
        f"label(s), which is public information)."
        if 2**s0 > len(output_labels) else
        f"\nV forms the multilinear extension W\u0303*_0 of the claimed outputs."
    )
    out.print(
        f"\nIf P's claims are correct, then D\u0303 = W\u0303_0 (multilinear extensions are "
        f"unique); otherwise D\u0303 \u2260 W\u0303_0."
    )

    W0_star_tilde = _claimed_output_mle(ac, claims)

    rho_0: Tuple[ModularInteger, ...]
    if s0 == 0:
        rho_0 = ()
        out.print(
            f"\nHere s_0 = 0 (a single output gate), so \u03c1_0 := () and the point-claim is "
            f"simply the output claim itself."
        )
    else:
        out.print(f"\nV samples \u03c1_0 uniformly at random from F^{s0}.")
        coords: List[ModularInteger] = []
        for j in range(s0):
            verifier_prompt = (
                f"\nAs verifier, choose an element of {F} uniformly at random, independent of "
                f"any previous choice (coordinate {j} of \u03c1_0):"
            ) if user_is_verifier else None
            c = random_field_element(field=F, user_input=user_is_verifier, custom_message=verifier_prompt, out=out)
            if c is None:
                out.print(f"\n{YELLOW}Protocol aborted.{RESET}")
                return None
            coords.append(F.convert(int(c)))
        rho_0 = tuple(coords)
        out.print(f"\nHere \u03c1_0 = {_point_str(rho_0)}.")

    alpha = _eval_tilde(W0_star_tilde, rho_0, F) if s0 > 0 else F.convert(claims[()])
    out.print(
        f"\nV computes \u03b1_0 := W\u0303*_0(\u03c1_0) = {int(alpha)}. The claim to be verified "
        f"is now a single point-claim:\n\nW\u0303_0(\u03c1_0) = \u03b1_0 = {int(alpha)}."
    )

    w_0_true = _eval_tilde(ac.tilde_W[0], rho_0, F)
    if initial_claim_false and not secret_mode:
        if s0 == 0:
            out.print(
                f"\n{YELLOW}Since the claimed output is false and s_0 = 0, the point-claim is "
                f"false with certainty: \u03b1_0 \u2260 W\u0303_0(\u03c1_0).{RESET}"
            )
        else:
            out.print(
                f"\n{YELLOW}Since the claimed outputs are false, W\u0303*_0 \u2260 W\u0303_0, and (by "
                f"Schwartz-Zippel) the event \u03b1_0 = W\u0303_0(\u03c1_0) -- which would launder "
                f"the lie immediately -- has probability at most s_0/#F = {s0}/{p} = "
                f"{s0/p:.10f}.{RESET}"
            )
            if alpha == w_0_true:
                out.print(
                    f"\n{YELLOW}Remarkably, that is exactly what happened: \u03c1_0 landed where "
                    f"D\u0303 and W\u0303_0 agree. The lie has been laundered before the protocol "
                    f"even started, and P can play honestly throughout.{RESET}"
                )

    # ---- the layer-by-layer protocol ----
    rho = rho_0
    ledger: List[str] = []
    accepted: Optional[bool] = None

    for i in range(d):
        result = gkr_layer_transition(
            ac,
            i=i,
            rho_i=rho,
            alpha_i=alpha,
            final_layer=(i == d - 1),
            user_is_prover=user_is_prover,
            user_is_verifier=user_is_verifier,
            secret_mode=bool(secret_mode),
            show_steps=show_steps,
            initial_claim_false=initial_claim_false,
            out=out,
        )
        ledger.extend(result.notes)

        if result.status == "abort":
            out.print(f"\n{YELLOW}Protocol aborted.{RESET}")
            return None
        if result.status == "reject":
            accepted = False
            break
        if result.status == "accept":
            accepted = True
            break
        # status == "continue"
        rho, alpha = result.rho_next, result.alpha_next

    if accepted is None:
        # Should not happen (the loop always ends in accept/reject/abort), but be safe.
        accepted = False

    # ---- ground truth ----
    print_header("Ground truth", level=1, out=out)

    truth_str = ", ".join(f"W_0({stringify(lbl)}) = {true_outputs[lbl]}" for lbl in output_labels)
    claims_str = ", ".join(f"W*_0({stringify(lbl)}) = {claims[lbl]}" for lbl in output_labels)
    out.print(f"\nTrue circuit output(s):\n\n{truth_str}.")
    out.print(f"\nProver claimed:\n\n{claims_str}.")

    if ledger:
        out.print("")
        for note in ledger:
            out.print(f"{YELLOW}{note}{RESET}")

    if accepted:
        out.print(f"\nOutcome: V {GREEN}ACCEPTED{RESET}.")
        if not initial_claim_false:
            out.print(f"\n{GREEN}This was a TRUE POSITIVE{RESET}: the claimed output(s) were correct.")
        else:
            out.print(f"\n{RED}This was a FALSE POSITIVE{RESET}: V accepted false claimed output(s) (P got lucky).")
    else:
        out.print(f"\nOutcome: V {RED}REJECTED{RESET}.")
        if not initial_claim_false:
            out.print(f"{YELLOW}\nThis was a FALSE NEGATIVE{RESET}: rejection happened despite correct claimed output(s) (should be rare unless the transcript was made inconsistent).")
        else:
            out.print(f"{GREEN}\nThis was a TRUE NEGATIVE{RESET}: V rejected false claimed output(s).")

    out.print("")

    if hasattr(out, "flush"):
        out.flush()
    return accepted


"""
END: THE GKR PROTOCOL (INTERACTIVE ENTRY POINT)
"""