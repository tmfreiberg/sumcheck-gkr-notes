"""
Notation and colour configuration for renderers.

This is the project's symbol vocabulary, shared by every renderer -- the
protocols' and the circuit's. It deliberately sits above gkr.protocol: the
protocol package imports gkr.ac, so a circuit renderer reaching back into
gkr.protocol.notation would close an import cycle.

Every symbol the protocols print is defined here, once. The defaults reproduce
the notebooks' conventions; supply a different `Notation` to change them
everywhere, including in the golden transcripts.

Design note -- composers, not holes. It is tempting to expose only atoms and
let renderers interpolate them, but `f"{n.gate}{n.tilde}{n.star}_{i}"` is
unreadable and invites transcription slips across hundreds of dense strings.
So the atoms below are private-ish defaults and the *methods* are the API:
`n.W(0, star=True)` -> "W̃*_0", `n.rho(0)` -> "ρ_0", `n.g(j, star=True)` ->
"g*_j". Renderers then read like mathematics, and a LaTeX or ASCII notation is
a subclass overriding `sub`/`tilded`/`starred` rather than a rewrite:

    class LatexNotation(Notation):
        def sub(self, base, i):     return f"{base}_{{{i}}}"
        def starred(self, base):    return f"{base}^{{*}}"
        def tilded(self, base):     return f"\\\\tilde{{{base}}}"

Subscripts accept `None` (bare symbol), an int, or a string, so callers can
pass "j", "i+1", or "k" as freely as 0.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from .utils.display import GREEN, RED, RESET, YELLOW

Index = Optional[Union[int, str]]


@dataclass(frozen=True)
class Notation:
    # ---- atoms: sum-check ---------------------------------------------------
    true_sum_symbol: str = "H"
    message_symbol: str = "g"
    challenge_symbol: str = "r"
    hypercube_symbol: str = "b"
    degree_label: str = "deg"
    star: str = "*"

    # ---- atoms: GKR ---------------------------------------------------------
    gate_symbol: str = "W"
    point_symbol: str = "\u03c1"          # rho
    carried_symbol: str = "\u03b1"        # alpha
    fold_symbol: str = "\u03c4"           # tau
    terminal_symbol: str = "\u03b3"       # gamma
    line_symbol: str = "\u2113"           # ell
    restriction_symbol: str = "q"
    add_symbol: str = "add"
    mult_symbol: str = "mult"
    layer_size_symbol: str = "S"
    label_bits_symbol: str = "s"
    endpoint_symbol: str = "z"
    endpoint_x_sub: str = "x"
    endpoint_y_sub: str = "y"
    add_value_symbol: str = "A"
    mult_value_symbol: str = "M"
    line_var: str = "t"
    tilde: str = "\u0303"                 # combining tilde: W + U+0303 = W̃

    # ---- primitives: override these to retarget a whole notation -------------
    def sub(self, base: str, i: Index = None) -> str:
        return base if i is None else f"{base}_{i}"

    def starred(self, base: str) -> str:
        return f"{base}{self.star}"

    def tilded(self, base: str) -> str:
        return f"{base}{self.tilde}"

    def _decorate(self, base: str, i: Index, tilde: bool, star: bool) -> str:
        if tilde:
            base = self.tilded(base)
        if star:
            base = self.starred(base)
        return self.sub(base, i)

    # ---- composers: sum-check ------------------------------------------------
    def H(self, *, star: bool = False) -> str:
        """H, or the claimed sum H*."""
        return self._decorate(self.true_sum_symbol, None, False, star)

    def g(self, j: Index = None, *, star: bool = False) -> str:
        """g, g_j, or the claimed g*_j."""
        return self._decorate(self.message_symbol, j, False, star)

    def r(self, j: Index = None) -> str:
        """The sum-check challenge r_j."""
        return self.sub(self.challenge_symbol, j)

    def b(self, k: Index = None) -> str:
        """A Boolean-hypercube variable b_k."""
        return self.sub(self.hypercube_symbol, k)

    def deg(self, of: str, *, wrt: Index = None) -> str:
        """deg(g*_j), or the per-variable bound deg_j(g)."""
        return f"{self.sub(self.degree_label, wrt)}({of})"

    # ---- composers: GKR -------------------------------------------------------
    def W(self, i: Index = None, *, tilde: bool = True, star: bool = False) -> str:
        """A gate-value function: W̃_i, W̃*_0, or plain W_i."""
        return self._decorate(self.gate_symbol, i, tilde, star)

    def rho(self, i: Index = None) -> str:
        return self.sub(self.point_symbol, i)

    def alpha(self, i: Index = None) -> str:
        return self.sub(self.carried_symbol, i)

    def tau(self, i: Index = None) -> str:
        return self.sub(self.fold_symbol, i)

    def gamma(self) -> str:
        return self.terminal_symbol

    def ell(self) -> str:
        return self.line_symbol

    def q(self, i: Index = None, *, star: bool = False) -> str:
        """The restriction q_{i+1}, or the claimed q*_{i+1}."""
        return self._decorate(self.restriction_symbol, i, False, star)

    def add(self, i: Index = None, *, tilde: bool = True) -> str:
        return self._decorate(self.add_symbol, i, tilde, False)

    def mult(self, i: Index = None, *, tilde: bool = True) -> str:
        return self._decorate(self.mult_symbol, i, tilde, False)

    def layer_size(self, i: Index = None) -> str:
        return self.sub(self.layer_size_symbol, i)

    def label_bits(self, i: Index = None) -> str:
        return self.sub(self.label_bits_symbol, i)

    def z_x(self, *, star: bool = False) -> str:
        """An endpoint claim: z_x, or the claimed z*_x (the star binds to the
        symbol, before the subscript, as in W̃*_0 and g*_j)."""
        return self._decorate(self.endpoint_symbol, self.endpoint_x_sub, False, star)

    def z_y(self, *, star: bool = False) -> str:
        return self._decorate(self.endpoint_symbol, self.endpoint_y_sub, False, star)

    def A(self) -> str:
        return self.add_value_symbol

    def M(self) -> str:
        return self.mult_value_symbol

    def t(self) -> str:
        return self.line_var


@dataclass(frozen=True)
class Palette:
    """Colours by meaning, not by name: truths green, lies red, asides yellow."""
    TRUTH: str = GREEN
    LIE: str = RED
    ASIDE: str = YELLOW
    RESET: str = RESET


NOTEBOOK_NOTATION = Notation()
DEFAULT_PALETTE = Palette()