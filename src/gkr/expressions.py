"""
Expressions: text -> SymPy -> a Graphviz circuit.

Everything upstream of the graph lives here -- parsing, the padding transform,
and the walk that turns an expression tree into a DOT circuit. Downstream (DOT
-> networkx -> layers) is gkr.graph; gate values and wiring predicates are
gkr.wiring.
"""
from __future__ import annotations

import ast
from typing import Dict, List, Optional, Tuple

from graphviz import Digraph
from sympy import Add, Expr, Integer, Mul, Pow, Symbol


def _expression_depth(expr: Expr) -> int:
    """Depth of the expression tree (an atom has depth 0)."""
    if expr.is_Atom:
        return 0
    return 1 + max(_expression_depth(a) for a in expr.args)

def _pad_to_depth(expr: Expr, depth: int) -> Expr:
    """Return an expression of exactly `depth` whose value equals `expr`.

    Multiplying by 1 pushes a leaf down one layer, but the 1 it introduces is
    itself a leaf that must reach the bottom too, so the padding recurses on
    both sides:

        pad(x, 1) = x * 1
        pad(x, 2) = (x * 1) * (1 * 1)

    A chain like ((x*1)*1) would NOT do: its outer 1 would be left stranded one
    layer above the bottom.
    """
    if depth <= 0:
        return expr
    return Mul(_pad_to_depth(expr, depth - 1), _pad_to_depth(Integer(1), depth - 1),
               evaluate=False)

def pad_expression(expr: Expr, target: Optional[int] = None) -> Tuple[Expr, List[str]]:
    """Pad every shallow leaf so that all inputs sit at the bottom layer.

    `target` is the depth to pad to. It defaults to this expression's own depth,
    which is right for a single-output circuit. A multi-output circuit is only
    as shallow as its DEEPEST output, so the caller must pass the maximum depth
    across all the outputs -- otherwise each output is balanced against itself
    and the circuit as a whole still has inputs above the bottom layer.

    Returns the padded expression and a list of human-readable notes describing
    what was inserted (the caller narrates them: this module does not print).
    """
    if target is None:
        target = _expression_depth(expr)
    notes: List[str] = []

    def walk(e: Expr, depth: int) -> Expr:
        if e.is_Atom:
            shortfall = target - depth
            if shortfall > 0:
                notes.append(
                    f"padded input {e} (at depth {depth}, needs {target}) with "
                    f"{shortfall} multiplication{'s' if shortfall > 1 else ''} by 1"
                )
                return _pad_to_depth(e, shortfall)
            return e
        return e.func(*[walk(a, depth + 1) for a in e.args], evaluate=False)

    return walk(expr, 0), notes

def parse_expression(expr_str: str) -> Expr:
    """
    Parse a string expression into a SymPy expression with integers replaced by symbols.

    Args:
        expr_str (str): The arithmetic expression as a string (e.g., '(2 + 2)*(3*3)').

    Returns:
        Expr: The SymPy expression with integers replaced by symbols.
    """
    # Parse the string into an Abstract Syntax Tree (AST)
    expr_ast = ast.parse(expr_str, mode='eval')
    # Recursively convert the AST into a SymPy expression
    expr_sympy = ast_to_sympy(expr_ast.body)
    return expr_sympy

def ast_to_sympy(node: ast.AST) -> Expr:
    """
    Recursively convert an AST node into a SymPy expression, replacing integers with symbols.

    Args:
        node (ast.AST): The AST node to convert.

    Returns:
        Expr: The corresponding SymPy expression.

    Raises:
        ValueError: If an unsupported AST node or operator is encountered.
    """
    if isinstance(node, ast.Constant):  # For Python 3.8 and above
        # Handle numeric constants
        if isinstance(node.value, int):
            # Replace integer constants with symbols named after the integers
            return Symbol(str(node.value), commutative=False)
        elif isinstance(node.value, float):
            # Replace float constants with symbols named after the floats
            return Symbol(str(node.value), commutative=False)
        else:
            raise ValueError(f"Unsupported constant type: {type(node.value)}")

    elif isinstance(node, ast.BinOp):
        # Handle binary operations (e.g., addition, subtraction, multiplication)
        left = ast_to_sympy(node.left)   # Convert the left operand
        right = ast_to_sympy(node.right) # Convert the right operand
        op = node.op                     # Get the operator

        if isinstance(op, ast.Add):
            # Addition operation
            return Add(left, right, evaluate=False)
        elif isinstance(op, ast.Sub):
            # Subtraction operation: a - b => a + (-1)*b
            return Add(left, Mul(-1, right, evaluate=False), evaluate=False)
        elif isinstance(op, ast.Mult):
            # Multiplication operation
            return Mul(left, right, evaluate=False)
        elif isinstance(op, ast.Div):
            # Division operation: a / b => a * b^(-1)
            return Mul(left, Pow(right, -1, evaluate=False), evaluate=False)
        elif isinstance(op, ast.Pow):
            # Exponentiation operation
            return Pow(left, right, evaluate=False)
        else:
            # Unsupported binary operator
            raise ValueError(f"Unsupported binary operator: {op}")

    elif isinstance(node, ast.UnaryOp):
        # Handle unary operations (e.g., negation)
        operand = ast_to_sympy(node.operand)  # Convert the operand
        uop = node.op                         # Get the operator

        if isinstance(uop, ast.UAdd):
            # Unary plus (e.g., +a)
            return operand
        elif isinstance(uop, ast.USub):
            # Unary minus (e.g., -a)
            return Mul(-1, operand, evaluate=False)
        else:
            # Unsupported unary operator
            raise ValueError(f"Unsupported unary operator: {uop}")

    elif isinstance(node, ast.Name):
        # Handle variable names
        return Symbol(node.id, commutative=False)

    elif isinstance(node, ast.Expr):
        # Handle expression nodes
        return ast_to_sympy(node.value)

    else:
        # Unsupported AST node type
        raise ValueError(f"Unsupported AST node type: {type(node)}")

def build_circuit(
    expr: Expr,
    graph: Digraph,
    parent: Optional[str] = None,
    _node_names: Optional[Dict[int, str]] = None,
) -> str:
    """
    Recursively builds a graph representation of a SymPy expression.

    Args:
        expr (Expr): The SymPy expression to be converted into a graph.
        graph (Digraph): The graph object to which nodes and edges will be added.
        parent (str, optional): The parent node ID in the graph (used for recursive calls).
        _node_names (dict, optional): Memo mapping id(sub-expression) -> node name.
            Node names are assigned in first-visit order ("n0", "n1", ...), so the
            resulting graph -- and hence the bitstring labels assigned to gates
            downstream -- is DETERMINISTIC across runs and processes. (Previously,
            node names were str(id(expr)), i.e. memory addresses, which permuted the
            gate labelling from run to run.) Keying the memo on object identity
            preserves the previous topology exactly: sub-expressions cached/shared
            by SymPy still map to a single node.

    Returns:
        str: The node ID of the current expression in the graph.
    """
    if _node_names is None:
        _node_names = {}

    def _name(e: Expr) -> Tuple[str, bool]:
        """Return (node name, is_first_visit)."""
        key = id(e)
        if key not in _node_names:
            _node_names[key] = f"n{len(_node_names)}"
            return _node_names[key], True
        return _node_names[key], False

    if expr.is_Atom:  # Base case: variable or constant
        node_id, first_visit = _name(expr)
        if first_visit:
            graph.node(node_id, label=str(expr), shape="circle")
        if parent:
            graph.edge(node_id, parent)
        return node_id

    # For compound expressions
    op_name = type(expr).__name__

    # Map operation names to desired labels
    if op_name == 'Add':
        label = '+'
    elif op_name == 'Mul':
        label = '×'  # Using the multiplication symbol
    else:
        label = op_name

    node_id, first_visit = _name(expr)
    if first_visit:
        graph.node(node_id, label=label, shape="circle")  # Use circle shape for operators

    if parent:
        graph.edge(node_id, parent)

    # Recurse ONLY on a first visit. SymPy caches structurally identical
    # sub-expressions, so both halves of e.g. "(3*2) + (3*2)" are the SAME
    # object: on a repeat visit the node already exists and its subtree has
    # already been emitted, and all that is needed is the new edge to `parent`.
    # Recursing again would re-emit the subtree's internal edges, inflating the
    # shared gate's fan-in (the "+" in "(1+2)*(1+2)" reached in-degree 4) and
    # corrupting the gate values computed downstream.
    #
    # Note the result is a genuine DAG with sharing: "(3*2) + (3*2)" is one
    # multiplication gate feeding the addition gate twice, i.e. add(z, x, y)
    # with x == y, which the wiring-predicate formalism handles fine.
    if first_visit:
        for arg in expr.args:
            build_circuit(arg, graph, node_id, _node_names)
    return node_id

def create_arithmetic_circuit(*expr_strings: str) -> Digraph:
    """
    Creates an arithmetic circuit graph from multiple string expressions.

    Args:
        *expr_strings (str): Arbitrary number of string expressions to be included in the circuit.

    Returns:
        Digraph: The graph object representing the arithmetic circuits.
    """
    # Initialize the graph
    graph = Digraph(comment="Arithmetic Circuit", format="svg")
    graph.attr(rankdir="BT")  # Set the graph direction from bottom to top

    # One shared memo across all output expressions, so that (a) node names are
    # deterministic across the whole circuit and (b) sub-expressions cached by
    # SymPy across expressions keep mapping to a single node (previous behavior).
    node_names: Dict[int, str] = {}

    # Loop over each expression string
    for expr_str in expr_strings:
        # Parse the expression
        expr = parse_expression(expr_str)
        # Build the circuit graph for this expression
        build_circuit(expr, graph, None, node_names)
        # Optionally, add a separator node or visual separation if needed

    return graph