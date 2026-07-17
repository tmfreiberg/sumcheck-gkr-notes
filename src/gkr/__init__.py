"""
Sum-check and GKR interactive proofs, for the notes.

The public API. Everything below can also be imported from its own module; this
is the front door, so a notebook needs one import line rather than five:

    from gkr import sum_check, gkr, ArithmeticCircuit

Layout:

    gkr.protocol    the protocols: engine, parties, events, renderers
    gkr.ac          arithmetic circuits (built on expressions/graph/wiring)
    gkr.mle         multilinear extensions (pure mathematics)
    gkr.notation    the symbol vocabulary every renderer routes through
    gkr.examples    the worked examples from the notebooks
    gkr.utils       display, polynomials, trees, decorators

Resolution is lazy (PEP 562): `import gkr` costs nothing, and each name pulls
in its module on first use. Eager imports here would be paid by every consumer
of the package -- including the CLI, which is careful to defer its own imports
so that `gkr --help` stays instant, and which loads this module before its own
code runs. Importing sympy, networkx and graphviz to print a usage message took
1.6s; this takes 0.03s.

"""
from importlib import import_module
from typing import Any

# name -> module that defines it (relative to this package)
_EXPORTS = {
    "init": "._env",
    # protocols
    "sum_check": ".protocol.sumcheck_session",
    "gkr": ".protocol.gkr_session",
    "choose_arithmetic_circuit": ".protocol.gkr_support",
    # objects
    "ArithmeticCircuit": ".ac",
    "multilinear_extension": ".mle",
    "multilinear_extension_using_lagrange_basis": ".mle",
    "evaluation_array": ".mle",
    "print_mle": ".mle_render",
    "print_evaluation_array": ".mle_render",
    "Notation": ".notation",
    "NOTEBOOK_NOTATION": ".notation",
    # errors
    "CircuitError": ".errors",
    "NotADag": ".errors",
    "FanInNotTwo": ".errors",
    "InputsNotAtBottom": ".errors",
    "NotStrictlyLayered": ".errors",
    "DegenerateLayer": ".errors",
    "CircuitConstructionFailed": ".errors",
    # worked examples
    "sum_check_example": ".examples",
    "gkr_example": ".examples",
    "roots_example": ".examples",
    "total_degree_example": ".examples",
    "multilinear_extension_example": ".examples",
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Import a public name on first use, then cache it in the module dict."""
    try:
        module = _EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    value = getattr(import_module(module, __name__), name)
    globals()[name] = value      # subsequent lookups skip __getattr__
    return value


def __dir__() -> list:
    return sorted(__all__)