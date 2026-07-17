"""
GKR-level cheat constructions: endpoint pairs consistent with a surviving lie,
and forged restrictions q* with planted agreement points.
"""
from __future__ import annotations

import random
from typing import List, Optional, Tuple, Union

from sympy import Poly, Symbol
from sympy.polys.domains.finitefield import FiniteField
from sympy.polys.domains.modularinteger import ModularInteger


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