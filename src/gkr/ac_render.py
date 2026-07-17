"""
The circuit renderer: every line ac.py prints, in one place.

Same treatment as the protocols' renderers (gkr.protocol.sumcheck_render,
gkr.protocol.gkr_render): the computing module builds circuits and raises when
it cannot, and all didactic text lives here, with every symbol routed through
the shared Notation (gkr.notation) rather than hard-coded. Supplying a
different Notation retargets this renderer too.

These functions back the ArithmeticCircuit.print_* methods, which are thin
delegates. Note that `out` is now an explicit parameter everywhere: the
extracted code printed some lines through the module-level default `out` and
others through `self.out`, so a circuit built with a custom output object had
half its lines go elsewhere. An explicit parameter makes that unrepresentable.
"""
from __future__ import annotations

import random
from itertools import product
from typing import Any, Dict, Iterable, List, Optional, Tuple

import networkx as nx
from sympy import Poly

from .notation import NOTEBOOK_NOTATION, Notation
from .utils.display import (
    GREEN,
    PINK,
    RED,
    RESET,
    YELLOW,
    TerminalOutput,
    out,
    print_header,
)
from .utils.display import (
    out as default_out,
)
from .wiring import flatten_inner_tuples, replace_symbols_in_polynomial


def print_topological_ordering(nx_graph: nx.DiGraph):
    """
    Prints the topological ordering of nodes in a directed acyclic graph (DAG).

    Args:
        nx_graph (nx.DiGraph): A directed acyclic graph.

    Raises:
        ValueError: If the graph is not a DAG.
    """
    # Check if the graph is a DAG
    if not nx.is_directed_acyclic_graph(nx_graph):
        raise ValueError(f"{RED}\nThe provided graph is not a directed acyclic graph (DAG).{RESET}\n")

    # Get the topological ordering
    topo_order = list(nx.topological_sort(nx_graph))

    # Print the ordering
    print_header(f"{PINK}Topological ordering{RESET}\n", level=2, out=out)
    out.print(f" {YELLOW}->{RESET} ".join(topo_order))


def print_W_dict(W_dict: Dict[int, Dict[tuple, int]], *, out: TerminalOutput = out,) -> None:
    """
    Prints the W_dict in a structured format, layer by layer.

    Args:
        W_dict (Dict[int, Dict[tuple, int]]): The dictionary representing the layer-wise weights.
    """
    print_header("Gate values\n", level=2, out=out)
    # Iterate through layers in sorted order
    for layer in sorted(W_dict.keys(), reverse=True):  # Start from the highest layer
        out.print(f"Layer {layer}\n".upper())

        # Sort the tuples (keys of the inner dictionary) in lexicographical order
        sorted_keys = sorted(W_dict[layer].keys())

        # Print each weight in the layer
        for key in sorted_keys:
            formatted_key = ','.join(map(str, key))  # Convert tuple to comma-separated string
            out.print(f"W_{layer}({formatted_key}) = {W_dict[layer][key]}")

        out.print("")  # Add spacing between layers


def print_add_mult_dicts(add_dict: Dict[int, Dict[tuple, int]],
                         mult_dict: Dict[int, Dict[tuple, int]],
                         *,
                         W_dict: Optional[Dict[int, Dict[tuple, Any]]] = None,
                         out: TerminalOutput = out,) -> None:
    """
    Prints the add_dict and mult_dict in a structured format, layer by layer.
    Only entries where the value is 1 are printed.

    Args:
        add_dict (Dict[int, Dict[tuple, int]]): The dictionary representing the addition wiring predicates.
        mult_dict (Dict[int, Dict[tuple, int]]): The dictionary representing the multiplication wiring predicates.
    """
    def filter_and_sort_dict(input_dict: Dict[int, Dict[tuple, int]]) -> Dict[int, List[tuple]]:
        """
        Filters and sorts keys with value 1 in the input_dict.

        Args:
            input_dict (Dict[int, Dict[tuple, int]]): Dictionary to process.

        Returns:
            Dict[int, List[tuple]]: Processed dictionary with sorted keys for each layer.
        """
        result = {}
        for layer in sorted(input_dict.keys(), reverse=True):
            filtered_keys = [key for key in input_dict[layer] if input_dict[layer][key] == 1]
            flattened_keys = flatten_inner_tuples(filtered_keys)
            result[layer] = sorted(flattened_keys)
        return result

    def _vw_for_layer(layer: int) -> Tuple[int, int]:
        if W_dict is None:
            raise ValueError("W_dict is required to format keys as (z),(x),(y) with correct dimensions.")
        v = len(next(iter(W_dict[layer].keys())))
        w = len(next(iter(W_dict[layer + 1].keys())))
        return v, w

    # Filter and sort both dictionaries
    add_dict_sorted = filter_and_sort_dict(add_dict)
    mult_dict_sorted = filter_and_sort_dict(mult_dict)

    # Print add_dict
    print_header("Addition Wiring Predicates (nonzero values)\n", level=2, out=out)

    for layer, keys in add_dict_sorted.items():
        out.print(f"\nLayer {layer}\n".upper())
        v, w = _vw_for_layer(layer)
        for key in keys:
            if len(key) != v + 2 * w:
                raise ValueError(f"Expected key length {v + 2*w} for layer {layer}, got {len(key)}: {key}")
            z = key[:v]
            x = key[v : v + w]
            y = key[v + w : v + 2 * w]
            formatted_key = f"({','.join(map(str, z))}),({','.join(map(str, x))}),({','.join(map(str, y))})"
            out.print(f"add_{layer}({formatted_key}) = 1")

        out.print("")  # Add spacing between layers

    # Print mult_dict
    print_header("Multiplication Wiring Predicates (nonzero values)\n", level=2, out=out)

    for layer, keys in mult_dict_sorted.items():
        out.print(f"\nLayer {layer}\n".upper())
        v, w = _vw_for_layer(layer)
        for key in keys:
            if len(key) != v + 2 * w:
                raise ValueError(f"Expected key length {v + 2*w} for layer {layer}, got {len(key)}: {key}")
            z = key[:v]
            x = key[v : v + w]
            y = key[v + w : v + 2 * w]
            formatted_key = f"({','.join(map(str, z))}),({','.join(map(str, x))}),({','.join(map(str, y))})"
            out.print(f"mult_{layer}({formatted_key}) = 1")

    out.print("")  # Add spacing between layers


def render_print_wiring_predicate_mles(ac, *, out=default_out, notation=NOTEBOOK_NOTATION):
    n = notation
    print_header("Multilinear extensions of wiring predicates: ADD\n", level=2, out=ac.out)

    tilde_add = ac.tilde_add
    tilde_mult = ac.tilde_mult
    W_dict = ac.W_dict

    for i in reversed(sorted(tilde_add.keys())):
        out.print(f"Layer {i}\n".upper())
        v = len(next(iter(W_dict[i].keys())))
        w = len(next(iter(W_dict[i + 1].keys())))
        formatted_input = ','.join(
            [f"z_{j}" for j in range(v)] + [f"x_{j}" for j in range(w)] + [f"y_{j}" for j in range(w)])
        LHS = f"{n.add(i)}({formatted_input})"
        RHS = replace_symbols_in_polynomial(tilde_add[i], v, w).as_expr()
        out.print(f"{LHS} = {RHS}")
        out.print("")

    print_header("Multilinear extensions of wiring predicates: MULT\n", level=2, out=ac.out)

    for i in reversed(sorted(tilde_mult.keys())):
        ac.out.print(f"Layer {i}\n".upper())
        v = len(next(iter(W_dict[i].keys())))
        w = len(next(iter(W_dict[i + 1].keys())))
        formatted_input = ','.join(
            [f"z_{j}" for j in range(v)] + [f"x_{j}" for j in range(w)] + [f"y_{j}" for j in range(w)])
        LHS = f"{n.mult(i)}({formatted_input})"
        RHS = replace_symbols_in_polynomial(tilde_mult[i], v, w).as_expr()
        out.print(f"{LHS} = {RHS}")
        out.print("")


def render_print_verification_propagation_equation(
    ac,
    mle: Optional[bool] = None,
    random_selection: Optional[int] = None,
    *,
    max_full_check: int = 1000,   # if total z's > this, sample instead of full enumeration
    sample_limit: int = 1000,     # how many z's to sample in large cases
    display_limit: int = 100,     # how many equations to print
    seed: Optional[int] = None,   # set for reproducibility if desired
    out: TerminalOutput = default_out,
    notation: Notation = NOTEBOOK_NOTATION,
) -> None:
    n = notation
    if mle is None:
        mle = False

    if seed is not None:
        random.seed(seed)

    if mle:
        W, W_dict, add, mult, F = ac.tilde_W, ac.W_dict, ac.tilde_add, ac.tilde_mult, ac.field
        print_header("Verification of Thaler's identity\n", level=2, out=ac.out)
    else:
        W, W_dict, add, mult, F = ac.W, ac.W_dict, ac.add, ac.mult, ac.field
        print_header("Verification of layer-wise gate-value propagation equation\n", level=2, out=ac.out)

    # Field size p (GF(p))
    p = int(ac.field.mod)

    # Iterate over layers in descending order
    for i in sorted(add.keys(), reverse=True):
        out.print(f"Layer {i}\n".upper())

        # Bit-lengths of gate labels in layers i and i+1
        v = len(next(iter(W_dict[i].keys())))
        w = len(next(iter(W_dict[i + 1].keys())))

        # Total number of z-values to verify for this layer
        total_z = (p ** v) if mle else (2 ** v)

        # Decide how many to check
        if random_selection is not None:
            # User override
            num_to_check = min(int(random_selection), total_z)
            sampling_reason = f"(Random selection of {num_to_check} z-values.)\n"
            use_sampling = True
        else:
            if total_z > max_full_check:
                num_to_check = min(sample_limit, total_z)
                sampling_reason = (
                    f"(There are {total_z} z-values in the domain; "
                    f"checking all would be slow.\n"
                    f" We will select {num_to_check} z-values uniformly at random, "
                    f"and display at most {display_limit} of them.)\n"
                )
                use_sampling = True
            else:
                num_to_check = total_z
                sampling_reason = ""
                use_sampling = False

        if sampling_reason:
            out.print(sampling_reason)

        # Helper: sample a random z in the correct domain without building product(...)
        def _random_z():
            if mle:
                # z in F^v, represented as tuple of ints in [0, p-1]
                return tuple(random.randrange(p) for _ in range(v))
            else:
                # z in {0,1}^v
                return tuple(random.randrange(2) for _ in range(v))

        # Build z iterator
        z_iter: Iterable[Tuple[int, ...]]
        if use_sampling:
            z_iter = (_random_z() for _ in range(num_to_check))
        else:
            # Full enumeration is safe (<= max_full_check)
            if mle:
                z_iter = product(range(p), repeat=v)
            else:
                z_iter = product([0, 1], repeat=v)

        # Precompute xy_range once per layer (small: 2^w by 2^w)
        xy_range = list(product(product([0, 1], repeat=w), repeat=2))

        # Track and print only the first display_limit checks
        printed = 0

        for z in z_iter:
            # LHS
            if mle:
                LHS = int(F(W[i].eval(z)))
            else:
                LHS = int(F(W[i](z)))

            # RHS
            if mle:
                RHS = sum(
                    add[i].eval(z + x + y) * (W[i + 1].eval(x) + W[i + 1].eval(y)) +
                    mult[i].eval(z + x + y) * W[i + 1].eval(x) * W[i + 1].eval(y)
                    for x, y in xy_range
                )
            else:
                RHS = sum(
                    add[i](z + x + y) * (W[i + 1](x) + W[i + 1](y)) +
                    mult[i](z + x + y) * W[i + 1](x) * W[i + 1](y)
                    for x, y in xy_range
                )

            RHS = int(F(RHS))

            correct = f"{GREEN}\u2713{RESET}" if LHS == RHS else f"{RED}\u2717{RESET}"

            # Format z as a tuple with parentheses always (including v=0 -> "()")
            z_display = "(" + ",".join(str(z_j) for z_j in z) + ")"

            if printed < display_limit:
                if mle:
                    formatted_LHS = f"{n.W(i)}{z_display}"
                    formatted_RHS = (
                        f"sum {{ {n.add(i)}({z_display},x,y) [ {n.W(i + 1)}(x) + {n.W(i + 1)}(y) ] + "
                        f"{n.mult(i)}({z_display},x,y) [ {n.W(i + 1)}(x) {n.W(i + 1)}(y)] }} over (x,y) in "
                        f"{{0,1}}^{w} × {{0,1}}^{w}"
                    )
                else:
                    formatted_LHS = f"{n.W(i, tilde=False)}{z_display}"
                    formatted_RHS = (
                        f"sum {{ {n.add(i, tilde=False)}({z_display},x,y) [ {n.W(i + 1, tilde=False)}(x) + {n.W(i + 1, tilde=False)}(y) ] + "
                        f"{n.mult(i, tilde=False)}({z_display},x,y) [ {n.W(i + 1, tilde=False)}(x) {n.W(i + 1, tilde=False)}(y)] }} over (x,y) in "
                        f"{{0,1}}^{w} × {{0,1}}^{w}"
                    )

                out.print(f"{formatted_LHS} = {LHS}, {formatted_RHS} = {RHS} {correct}")
                printed += 1

        if num_to_check > display_limit:
            out.print(f"\n(Displayed {display_limit} of {num_to_check} checked equations.)")

        out.print("")


def print_multilinear_extensions(
    W_dict: Dict[int, Dict[Tuple[int], int]],
    tilde_W: Dict[int, Poly], *, out: TerminalOutput = out,
    notation: Notation = NOTEBOOK_NOTATION,
) -> None:
    """
    Prints the multilinear extensions for each layer in a structured format.

    Args:
        W_dict (Dict[int, Dict[Tuple[int], int]]): The dictionary of layer-wise weights.
        tilde_W (Dict[int, Callable]): The dictionary of multilinear extensions for each layer.
    """
    n = notation
    print_header("Multilinear extensions of gate-value functions\n", level=2, out=out)
    for i in sorted(W_dict.keys(), reverse=True):  # Iterate over layers in descending order
        out.print(f"Layer {i}\n".upper())
        # Determine the length of the bitstring keys for the current layer
        v = len(next(iter(W_dict[i].keys())))
        # Generate symbolic variable names x_0, x_1, ..., x_{v-1}
        formatted_tuple = ', '.join([f"x_{j}" for j in range(v)])
        # Print the formatted output
        out.print(f"{n.W(i)}({formatted_tuple}) = {tilde_W[i].as_expr()}\n")