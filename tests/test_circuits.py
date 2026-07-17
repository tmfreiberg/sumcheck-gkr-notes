"""
Circuit-builder tests.

None of this was covered before: the golden transcripts exercise exactly two
circuits, both of which happen to avoid every sharp edge. These pin the
behaviour of ac.py directly.
"""
from __future__ import annotations

import pytest

from gkr.ac import (
    ArithmeticCircuit,
    CircuitError,
    DegenerateLayer,
    InputsNotAtBottom,
    pad_expression,
    parse_expression,
)
from gkr.protocol.gkr_support import validate_for_gkr


def _output(ac: ArithmeticCircuit) -> int:
    return int(list(ac.W_dict[0].values())[0])


# ----------------------------------------------------------------------------
# Shared sub-expressions
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("expr,want", [
    ("(2+2)", 4),
    ("(1+2)*(1+2)", 9),
    ("(3*2) + (3*2)", 12),
    ("(1+2)*(3+4)", 21),
])
def test_shared_subexpressions_evaluate_correctly(expr: str, want: int) -> None:
    """SymPy caches structurally identical sub-expressions, so both halves of
    '(3*2) + (3*2)' are the SAME object. build_circuit must not re-walk the
    memoised subtree: doing so re-emitted its internal edges, inflating the
    shared gate's fan-in and corrupting every value downstream ('(1+2)*(1+2)'
    evaluated to 4, '(3*2)+(3*2)' to 18).
    """
    ac = ArithmeticCircuit(expr, prime=331)
    assert _output(ac) == want
    assert ac.fan_in_two, "a shared gate feeding one consumer twice is still fan-in 2"


def test_sharing_produces_a_dag_not_a_tree() -> None:
    """'(3*2) + (3*2)' is ONE multiplication gate feeding the addition twice --
    add(z, x, y) with x == y, which the wiring-predicate formalism handles."""
    ac = ArithmeticCircuit("(3*2) + (3*2)", prime=331)
    assert [len(ac.layers[i]) for i in range(ac.depth + 1)] == [1, 1, 2]


# ----------------------------------------------------------------------------
# Refusal, with a diagnosis that matches the failure
# ----------------------------------------------------------------------------

def test_inputs_not_at_bottom_names_the_offender() -> None:
    with pytest.raises(InputsNotAtBottom) as excinfo:
        ArithmeticCircuit("3 + (4*5)", prime=331)
    assert "3" in str(excinfo.value)
    assert excinfo.value.hint, "every CircuitError must carry an actionable hint"


def test_the_constructor_never_returns_a_half_built_circuit() -> None:
    """It used to print a WARNING and carry on, leaving W_dict simply absent --
    so an AttributeError leaked into the user's transcript and callers had to
    hasattr-check five attributes to discover whether they had a circuit."""
    for expr in ["3 + (4*5)", "1 + 2 + 3"]:
        with pytest.raises(CircuitError):
            ArithmeticCircuit(expr, prime=331)
    ac = ArithmeticCircuit("(1+2)*(3+4)", prime=331)
    for attr in ("W_dict", "tilde_W", "tilde_add", "tilde_mult", "add_dict", "mult_dict"):
        assert hasattr(ac, attr), f"a circuit that built must have {attr}"


def test_gkr_refuses_a_degenerate_interior_layer() -> None:
    """A perfectly valid circuit that GKR still cannot use: a single-gate layer
    has a 0-bit label, making that layer's sum-check degenerate."""
    ac = ArithmeticCircuit("(2+2)", prime=331)   # builds fine
    with pytest.raises(DegenerateLayer):
        validate_for_gkr(ac)


# ----------------------------------------------------------------------------
# Padding
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("expr,want", [
    ("3 + (4*5)", 23),
    ("1 + 2 + 3", 6),
    ("(3*2) + (4 + 1 + 3)", 14),
])
def test_padding_fixes_the_circuit_and_preserves_the_value(expr: str, want: int) -> None:
    with pytest.raises(CircuitError):
        ArithmeticCircuit(expr, prime=331)
    ac = ArithmeticCircuit(expr, prime=331, pad=True)
    assert _output(ac) == want
    assert ac.padding_notes, "padding must report what it inserted, for the caller to narrate"


def test_padding_leaves_no_leaf_stranded() -> None:
    """The obvious chain ((x*1)*1) would leave its outer 1 one layer above the
    bottom, so the transform recurses on both sides: pad(x, 2) = (x*1)*(1*1)."""
    expr, _ = pad_expression(parse_expression("3 + (4*(5*6))"))
    ac = ArithmeticCircuit(str(expr), prime=331)   # must not raise
    assert _output(ac) == 3 + 4 * 5 * 6


def test_a_padded_circuit_is_usable_for_gkr() -> None:
    ac = ArithmeticCircuit("3 + (4*5)", prime=331, pad=True)
    validate_for_gkr(ac)   # must not raise


# ----------------------------------------------------------------------------
# Non-power-of-two layers
# ----------------------------------------------------------------------------

def test_interior_layer_with_a_non_power_of_two_gate_count() -> None:
    """Unused gate labels are 0: W_i must be a function on ALL of {0,1}^{s_i}
    for its multilinear extension to exist, and nothing wires to an unused
    label, so Thaler's identity reads 0 = 0 there. This zero-fill used to apply
    to the input layer only, so any such interior layer raised a bare KeyError
    -- which is what the old advice 'layer sizes that are powers of two are
    safest' was really hiding.
    """
    ac = ArithmeticCircuit("(3*2) + (4 + 1 + 3)", prime=331, pad=True)
    sizes = [len(ac.layers[i]) for i in range(ac.depth + 1)]
    assert 3 in sizes, "this circuit is only interesting if some layer has 3 gates"
    for layer, size in enumerate(sizes):
        bits = max(0, (size - 1).bit_length())
        assert len(ac.W_dict[layer]) == 2 ** bits, f"layer {layer} must define W on every label"


# ----------------------------------------------------------------------------
# strict=False: circuits built for exposition rather than for GKR
# ----------------------------------------------------------------------------

def test_strict_false_records_problems_instead_of_raising() -> None:
    """The notes deliberately build '5*4 + 3' to show a reader WHY it is not
    strictly layered, and want the picture and the depth to discuss. Raising
    serves the protocol; recording serves the exposition."""
    from gkr.ac import ArithmeticCircuit
    ac = ArithmeticCircuit("5*4 + 3", prime=7, strict=False)
    assert ac.depth == 2 and ac.field.mod == 7
    assert ac.graphviz_circuit is not None
    assert any(isinstance(e, InputsNotAtBottom) for e in ac.problems)
    assert "bottom layer" in ac.describe_problems()


def test_a_non_strict_circuit_cannot_reach_gkr() -> None:
    """strict=False must not become a way to smuggle a broken circuit into the
    protocol -- that was the old silent-failure bug wearing a new hat."""
    from gkr.ac import ArithmeticCircuit
    ac = ArithmeticCircuit("5*4 + 3", prime=7, strict=False)
    with pytest.raises(CircuitError):
        validate_for_gkr(ac)


def test_symbolic_inputs_are_diagnosed_as_such() -> None:
    """'5*x + (3*4)' has a perfectly good structure and no gate values. Saying
    'the circuit is structurally unusual, simplify the expression' would be
    false and useless advice."""
    from gkr.ac import ArithmeticCircuit, SymbolicInputs
    with pytest.raises(SymbolicInputs):
        ArithmeticCircuit("5*x + (3*4)", prime=7)

    ac = ArithmeticCircuit("5*x + (3*4)", prime=7, strict=False)
    assert ac.depth == 2
    assert ac.topological_ordering, "the structure does not depend on the values"
    assert len(ac.layers) == 3
    assert not hasattr(ac, "W_dict"), "gate values must not be invented"


def test_strict_is_the_default() -> None:
    from gkr.ac import ArithmeticCircuit
    with pytest.raises(InputsNotAtBottom):
        ArithmeticCircuit("5*4 + 3", prime=7)
    ac = ArithmeticCircuit("(1+2)*(3+4)", prime=331)
    assert ac.problems == [], "a strict circuit that returns has nothing wrong with it"