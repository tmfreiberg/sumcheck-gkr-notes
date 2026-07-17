"""
Circuit errors.

Their own module because both gkr.ac and gkr.graph raise them, and gkr.ac
imports gkr.graph: a shared vocabulary cannot live in one of its own consumers.
(Same reason gkr.notation sits at the package root.)

The circuit builder computes and refuses; it does not narrate. Callers catch
CircuitError and render `str(e)` plus `e.hint` however suits them -- the
interactive prompt re-asks, the CLI prints to stderr.
"""
from __future__ import annotations


class CircuitError(ValueError):
    """The expression does not describe a circuit usable for GKR."""

    hint: str = ""

    def __init__(self, message: str, *, hint: str = ""):
        super().__init__(message)
        if hint:
            self.hint = hint

class NotADag(CircuitError):
    hint = "A circuit must be acyclic; this one models no well-defined computation."

class FanInNotTwo(CircuitError):
    hint = (
        "Every gate must take exactly two inputs. Write nested binary operations, "
        "e.g. '(1 + 2) + 3' rather than '1 + 2 + 3'."
    )

class InputsNotAtBottom(CircuitError):
    hint = (
        "Every input must sit at the bottom layer, so that all paths from the "
        "output have the same length. Pad the shallow inputs with '(x*1)' or "
        "'(x + 0)' -- or pass pad=True (CLI: --pad) to have it done for you."
    )

class NotStrictlyLayered(CircuitError):
    hint = (
        "A GKR circuit must be strictly layered: every edge goes from layer i+1 "
        "to layer i, so all paths from an output to an input have the same "
        "length. Pad the shallow branches with '(x*1)' -- or pass pad=True "
        "(CLI: --pad)."
    )

class DegenerateLayer(CircuitError):
    hint = (
        "Every interior layer needs at least two gates: a single-gate layer has a "
        "0-bit label, which makes that layer's sum-check degenerate."
    )

class SymbolicInputs(CircuitError):
    hint = (
        "Gate values are only defined when every input is a concrete field "
        "element. The circuit's STRUCTURE -- layers, wiring, topological order, "
        "both drawings -- does not depend on the values and is available with "
        "strict=False."
    )


class CircuitConstructionFailed(CircuitError):
    hint = "The circuit is structurally unusual; simplify the expression and try again."