"""
Rendering for multilinear extensions: the mirror of ac_render.py.

mle.py is pure mathematics with no print sites, so everything that puts an MLE
on a screen lives here. Symbols are composed through gkr.notation rather than
written literally.
"""
from __future__ import annotations

import shutil
from typing import Optional, Tuple

import numpy as np
from sympy import Poly

from .mle import evaluation_array
from .notation import NOTEBOOK_NOTATION, Notation
from .utils.display import BLUE, GREEN, RED, RESET, TerminalOutput, print_header
from .utils.display import out as default_out


def is_multilinear(poly: Poly) -> bool:
    """True if no variable appears to a power above 1."""
    for var in poly.gens:
        if poly.degree(var) > 1:
            return False
    return True


def print_mle(
    poly: Poly,
    *,
    name: Optional[str] = None,
    out: TerminalOutput = default_out,
    notation: Notation = NOTEBOOK_NOTATION,
) -> None:
    """Print an MLE as a polynomial, with its field and multilinearity noted."""
    label = name if name is not None else "f-tilde"
    p = int(poly.domain.mod)
    v = len(poly.gens)
    out.print(f"\n{label}({', '.join(str(g) for g in poly.gens)}) = {poly.as_expr()}")
    out.print(f"\nover GF({p}), in {v} variable{'s' if v != 1 else ''}.")
    if not is_multilinear(poly):
        out.print(f"\n{RED}This polynomial is NOT multilinear.{RESET}")


def print_evaluation_array(
    poly: Poly,
    *,
    out: TerminalOutput = default_out,
    max_side: int = 25,
) -> None:
    """Print the polynomial's values at every point of GF(p)^v.

    The array has p^v entries, so this is only readable for small p and v; above
    max_side per side we say so rather than flooding the terminal.
    """
    p = int(poly.domain.mod)
    v = len(poly.gens)
    if p > max_side:
        out.print(
            f"\nThe evaluation array over GF({p})^{v} has {p ** v} entries; "
            f"too many to display (the limit is {max_side} per side). "
            f"Try a smaller prime."
        )
        return None

    arr = evaluation_array(poly)
    print_header(f"Evaluations over GF({p})^{v}", level=2, out=out)
    if v == 1:
        out.print("")
        for a, value in enumerate(np.atleast_1d(arr)):
            out.print(f"  f({a}) = {value}")
    elif v == 2:
        out.print("\nRows are x_0, columns are x_1:\n")
        width = max(len(str(int(x))) for x in arr.flatten())
        header = "     " + " ".join(f"{c:>{width}}" for c in range(p))
        out.print(header)
        out.print("     " + "-" * (len(header) - 5))
        for r in range(p):
            row = " ".join(f"{int(arr[r][c]):>{width}}" for c in range(p))
            out.print(f"{r:>3} | {row}")
    else:
        out.print(f"\n{arr}")
    return None


def print_compared_grids(
    first: "np.ndarray",
    second: "np.ndarray",
    labels: Tuple[str, str],
    *,
    out: TerminalOutput,
    gutter: int = 4,
) -> None:
    """Print two evaluation grids, each cell green where they agree and red
    where they differ.

    Side by side if the terminal is wide enough, stacked otherwise.

    Two things worth knowing:

    * Padding is computed on the PLAIN number and the colour wrapped around it
      afterwards. ANSI escapes are invisible but not zero-length, so padding an
      already-coloured string right-aligns the escape sequence and leaves the
      digits ragged -- which is exactly how the old overlay drifted out of
      alignment as soon as one row held a two-digit value.
    * A one-variable example gives a 1-D array; atleast_2d turns it into a
      single row rather than an IndexError.
    """
    a = np.atleast_2d(first)
    b = np.atleast_2d(second)
    rows, cols = a.shape
    width = max(len(str(int(x))) for g in (a, b) for x in g.flat)

    def render_row(g: "np.ndarray", other: "np.ndarray", i: int) -> str:
        cells = []
        for j in range(cols):
            x, y = int(g[i, j]), int(other[i, j])
            colour = GREEN if x == y else RED
            cells.append(f"{colour}{x:>{width}}{RESET}")
        return " ".join(cells)

    grid_width = cols * width + (cols - 1)
    try:
        term_width = shutil.get_terminal_size((100, 24)).columns
    except Exception:
        term_width = 100

    if 2 * grid_width + gutter <= term_width:
        pad = " " * gutter
        out.print(f"{BLUE}{labels[0]:^{grid_width}}{RESET}{pad}"
                  f"{BLUE}{labels[1]:^{grid_width}}{RESET}")
        for i in range(rows):
            out.print(render_row(a, b, i) + pad + render_row(b, a, i))
    else:
        for g, other, label in ((a, b, labels[0]), (b, a, labels[1])):
            out.print(f"\n{BLUE}{label:^{grid_width}}{RESET}")
            for i in range(rows):
                out.print(render_row(g, other, i))