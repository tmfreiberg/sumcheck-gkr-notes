"""A toy polynomial commitment: hash the coefficients and check them later."""
from __future__ import annotations

import hashlib
from typing import Tuple

from sympy import Poly


def poly_commitment_sha256(g: Poly) -> str:
    """
    Toy commitment: SHA-256 hash of a canonical serialization of a SymPy Poly.

    Binding here is only "demo binding":
    - if someone later changes g, the hash will (almost surely) change.
    - not hiding (hash is not a commitment scheme).
    """
    F = g.domain
    p = int(getattr(F, "mod", 0) or 0)
    gens = tuple(str(x) for x in g.gens)

    # Canonical term list: (monom tuple, coeff int) sorted lexicographically
    # Poly.terms() gives [((e0,...,ev-1), coeff), ...]
    terms: list[Tuple[Tuple[int, ...], int]] = []
    for monom, coeff in g.terms():
        try:
            c = int(coeff)
        except Exception:
            c = int(F.convert(coeff))
        terms.append((tuple(int(e) for e in monom), c))

    terms.sort()

    # Degree bounds per variable (what V "knows")
    degs = tuple(int(g.degree(gen)) for gen in g.gens)

    payload = repr((p, gens, degs, terms)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()