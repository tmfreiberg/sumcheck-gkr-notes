"""
Gate values and wiring predicates, and their multilinear extensions.

Given a layered graph from gkr.graph, build W_i (what each gate computes),
add_i and mult_i (which triples of gate labels are wired together), and the
multilinear extension of each -- the objects GKR actually runs on.
"""
from __future__ import annotations

from collections import defaultdict
from itertools import product
from typing import Any, Callable, DefaultDict, Dict, List, Optional, Set, Tuple, Union

import networkx as nx
from sympy import Poly, symbols
from sympy.polys.domains.finitefield import FiniteField


def format_wiring_key(key, s_i, s_ip1):
    """
    Format a flattened wiring key as ((c),(a),(b)).
    """
    c = key[:s_i]
    a = key[s_i : s_i + s_ip1]
    b = key[s_i + s_ip1 :]
    return f"({tuple(c)}, {tuple(a)}, {tuple(b)})"

def construct_W_and_wiring_dicts(
    machine_id_graph: nx.DiGraph,
    id_mapping: Dict[str, str],
    layer_partition: Dict[int, Set[str]],
    p: Optional[int] = None,
) -> Tuple[
    Dict[int, Dict[Tuple[Any, ...], int]],
    Dict[int, Dict[Tuple[Any, ...], int]],
    Dict[int, Dict[Tuple[Any, ...], int]],
]:
    """
    Constructs the nested dictionary W_dict along with add_dict and mult_dict.

    Handles the empty bitstring case by including it explicitly in the keys.
    """
    W_dict: Dict[int, Dict[Tuple[int, ...], Any]] = {}
    add_dict: DefaultDict[int, Dict[Tuple[Any, ...], int]] = defaultdict(dict)
    mult_dict: DefaultDict[int, Dict[Tuple[Any, ...], int]] = defaultdict(dict)

    # Reverse the id_mapping to map bitstring IDs to machine IDs
    reverse_mapping = {v: k for k, v in id_mapping.items()}

    # Process layers in reverse order (from outputs to inputs)
    for layer in sorted(layer_partition.keys(), reverse=True):
        W_dict[layer] = {}  # Initialize dictionary for this layer

        for node in layer_partition[layer]:
            # Handle the bitstring
            raw_bitstring = node.split('.')[1]
            bitstring = tuple() if raw_bitstring == '_' else tuple(map(int, raw_bitstring))

            # Get the corresponding machine ID
            machine_id = reverse_mapping[node]

            # Normalize the label by stripping quotes
            operation = machine_id_graph.nodes[machine_id]['label'].strip('"')

            # Special case for input layer
            if layer == max(layer_partition.keys()):  # Input layer
                value = int(operation)  # Use the label directly as an integer
                W_dict[layer][bitstring] = value % p if p else value

            else:  # Non-input layer
                # Get incoming edges
                incoming_edges = list(machine_id_graph.in_edges(machine_id))
                if len(incoming_edges) < 2:
                    raise ValueError(f"Node {node} in layer {layer} does not have at least 2 incoming edges.")

                # Map parents to bitstring-based IDs and retrieve their values
                parent_bitstrings = []
                parent_values = []
                for parent, _ in incoming_edges:
                    raw_parent_bitstring = id_mapping[parent].split('.')[1]
                    parent_bitstring = tuple() if raw_parent_bitstring == '_' else tuple(map(int, raw_parent_bitstring))
                    parent_bitstrings.append(parent_bitstring)

                    if parent_bitstring not in W_dict[layer + 1]:
                        raise KeyError(
                            f"Parent node {parent} with bitstring {id_mapping[parent]} (layer {layer + 1}) "
                            f"is missing in W_dict[layer + 1]: {list(W_dict[layer + 1].keys())}"
                        )
                    parent_values.append(W_dict[layer + 1][parent_bitstring])

                # Normalize parent order so that parent_bitstrings[0] <= parent_bitstrings[1]
                if parent_bitstrings[0] > parent_bitstrings[1]:
                    parent_bitstrings[0], parent_bitstrings[1] = parent_bitstrings[1], parent_bitstrings[0]
                    parent_values[0], parent_values[1] = parent_values[1], parent_values[0]

                # Compute the value for the current node
                if operation == '+':
                    value = parent_values[0] + parent_values[1]
                    key = (bitstring,) + parent_bitstrings[0] + parent_bitstrings[1]
                    add_dict[layer][key] = 1
                elif operation == '×':
                    value = parent_values[0] * parent_values[1]
                    key = (bitstring,) + parent_bitstrings[0] + parent_bitstrings[1]
                    mult_dict[layer][key] = 1
                else:
                    raise ValueError(f"Unsupported operation {operation} for node {node}.")

                # Apply modulo if p is provided
                W_dict[layer][bitstring] = value % p if p else value

        # A layer whose gate count is not a power of two has unused labels.
        # Define those gates to be 0: W_i must be a function on ALL of
        # {0,1}^{s_i} for its multilinear extension to exist, and 0 is the
        # consistent choice -- nothing wires to an unused label, so
        # add_i(z, ., .) = mult_i(z, ., .) = 0 there and Thaler's identity
        # reads 0 = 0. (This fill used to apply to the input layer only, so
        # any interior layer with a non-power-of-two gate count raised a bare
        # KeyError from the MLE construction. That is what the old advice
        # "layer sizes that are powers of two are safest" was really about.)
        bitstring_length = len(next(iter(W_dict[layer]))) if W_dict[layer] else 0
        for label in product(range(2), repeat=bitstring_length):
            W_dict[layer].setdefault(tuple(label), 0)

    # Ensure all layers are included when filling missing keys
    all_layers = list(layer_partition.keys())
    for layer in all_layers:
        if layer == max(layer_partition.keys()):  # Skip input layer
            continue
        # Ensure the layer exists in add_dict and mult_dict
        if layer not in add_dict:
            add_dict[layer] = {}
        if layer not in mult_dict:
            mult_dict[layer] = {}

        # Determine bitstring lengths
        bitstring_length = len(next(iter(W_dict[layer]))) if W_dict[layer] else 0
        parent_bitstring_length = len(next(iter(W_dict[layer + 1]))) if layer + 1 in W_dict else 0

        # Generate all possible combinations for keys
        all_possible_keys: Set[Tuple[Any, ...]]
        if bitstring_length == 0:
            # Include the empty bitstring explicitly in the key
            all_parent_bitstrings = [tuple(bits) for bits in product(range(2), repeat=parent_bitstring_length)]
            all_possible_keys = {
                ((),) + parent_bits1 + parent_bits2
                for parent_bits1 in all_parent_bitstrings
                for parent_bits2 in all_parent_bitstrings
            }
        else:
            all_bitstrings = [tuple(bits) for bits in product(range(2), repeat=bitstring_length)]
            all_parent_bitstrings = [tuple(bits) for bits in product(range(2), repeat=parent_bitstring_length)]
            all_possible_keys = {
                (bitstring,) + parent_bits1 + parent_bits2
                for bitstring in all_bitstrings
                for parent_bits1 in all_parent_bitstrings
                for parent_bits2 in all_parent_bitstrings
            }

        for key in all_possible_keys:
            if key not in add_dict[layer]:
                add_dict[layer][key] = 0
            if key not in mult_dict[layer]:
                mult_dict[layer][key] = 0

    return W_dict, add_dict, mult_dict

def flatten_inner_tuples(lst):
    return [tuple(item if not isinstance(item, tuple) else item for sub in t for item in (sub if isinstance(sub, tuple) else [sub])) for t in lst]

def generate_layer_functions_and_extensions(
    W_dict: Dict[int, Dict[Tuple[int, ...], int]],
    field: FiniteField,
    multilinear_extension: Callable[[FiniteField, int, Callable[[Tuple[int, ...]], int]], Poly]
) -> Tuple[Dict[int, Callable[[Tuple[int, ...]], int]], Dict[int, Poly]]:
    """
    Generate layer functions W_i and their multilinear extensions tilde_W_i.

    Args:
        W_dict (Dict[int, Dict[Tuple[int, ...], int]]): The dictionary representing the layer-wise weights.
        field (FiniteField): The finite field over which the extensions are defined.
        multilinear_extension (Callable): A function to compute the multilinear extension.

    Returns:
        Tuple[Dict[int, Callable[[Tuple[int, ...]], int]], Dict[int, Poly]]: Dictionaries for W and tilde_W.
    """
    # Create the layer functions W_i
    def create_W(i: int) -> Callable[[Tuple[int, ...]], int]:
        def Wi(b: Tuple[int, ...]) -> int:
            return W_dict[i][b]
        return Wi

    # Initialize dictionaries for W and tilde_W
    W = {i: create_W(i) for i in W_dict.keys()}
    tilde_W = {}

    # Create the multilinear extensions for each layer
    for i in W.keys():
        # Handle the degenerate case where the keys are empty tuples
        if not W_dict[i]:  # If W_dict[i] is empty
            raise ValueError(f"W_dict for layer {i} is empty, cannot compute extensions.")

        first_key = next(iter(W_dict[i].keys()))
        v = len(first_key)  # Length of any key in layer i
        if v == 0:
            # Degenerate case: no variables in the layer
            constant_value = list(W_dict[i].values())[0]
            # Introduce a dummy variable x_0
            X = symbols(f"x_:{v + 1}")
            # Create a constant polynomial in the dummy variable
            tilde_W[i] = Poly(constant_value, X, domain=field)
        else:
            # Compute the multilinear extension
            tilde_W[i] = multilinear_extension(field, v, W[i])

    return W, tilde_W

def generate_add_mult_functions_and_extensions(
    add_dict: Dict[int, Dict[Tuple[Any, ...], int]],
    mult_dict: Dict[int, Dict[Tuple[Any, ...], int]],
    field: FiniteField,
    multilinear_extension: Callable[[FiniteField, int, Callable[[Tuple[int, ...]], int]], Poly]
) -> Tuple[
    Dict[int, Callable[[Tuple[int, ...]], int]],
    Dict[int, Poly],
    Dict[int, Callable[[Tuple[int, ...]], int]],
    Dict[int, Poly]
]:
    """
    Generate layer functions add_i, mult_i, and their multilinear extensions tilde_add_i, tilde_mult_i.

    Args:
        add_dict (Dict[int, Dict[Tuple[Any, ...], int]]): The dictionary representing addition predicates.
        mult_dict (Dict[int, Dict[Tuple[Any, ...], int]]): The dictionary representing multiplication predicates.
        field (FiniteField): The finite field over which the extensions are defined.
        multilinear_extension (Callable): A function to compute the multilinear extension.

    Returns:
        Tuple[
            Dict[int, Callable[[Tuple[int, ...]], int]],
            Dict[int, Poly],
            Dict[int, Callable[[Tuple[int, ...]], int]],
            Dict[int, Poly]
        ]:
            Dictionaries for add, tilde_add, mult, and tilde_mult.
    """
    # Create the layer functions for addition
    def create_add(i: int) -> Callable[[Tuple[int, ...]], int]:
        sample_key = next(iter(add_dict[i].keys()))
        def add_func(b: Tuple[int, ...]) -> int:
            # Reconstruct the key based on the structure of keys in add_dict[i]
            key_elements: List[Union[Tuple[int, ...], int]] = []
            idx = 0  # Index in b
            for element in sample_key:
                if isinstance(element, tuple):
                    # For tuples (which could be empty), extract len(element) bits
                    length = len(element)
                    key_elements.append(tuple(b[idx:idx+length]))
                    idx += length
                else:
                    # For single bits
                    key_elements.append(b[idx])
                    idx += 1
            key = tuple(key_elements)
            return add_dict[i][key]
        return add_func

    # Create the layer functions for multiplication
    def create_mult(i: int) -> Callable[[Tuple[int, ...]], int]:
        sample_key = next(iter(mult_dict[i].keys()))
        def mult_func(b: Tuple[int, ...]) -> int:
            # Reconstruct the key based on the structure of keys in mult_dict[i]
            key_elements: List[Union[Tuple[int, ...], int]] = []
            idx = 0
            for element in sample_key:
                if isinstance(element, tuple):
                    length = len(element)
                    key_elements.append(tuple(b[idx:idx+length]))
                    idx += length
                else:
                    key_elements.append(b[idx])
                    idx += 1
            key = tuple(key_elements)
            return mult_dict[i][key]
        return mult_func

    # Initialize dictionaries for add, tilde_add, mult, tilde_mult
    add = {i: create_add(i) for i in add_dict.keys()}
    tilde_add = {}
    mult = {i: create_mult(i) for i in mult_dict.keys()}
    tilde_mult = {}

    # Create the multilinear extensions for each layer
    for i in add.keys():
        if not add_dict[i]:
            continue
        sample_key = next(iter(add_dict[i].keys()))
        # Compute total number of bits v
        v = sum(len(element) if isinstance(element, tuple) else 1 for element in sample_key)
        tilde_add[i] = multilinear_extension(field, v, add[i])

    for i in mult.keys():
        if not mult_dict[i]:
            continue
        sample_key = next(iter(mult_dict[i].keys()))
        v = sum(len(element) if isinstance(element, tuple) else 1 for element in sample_key)
        tilde_mult[i] = multilinear_extension(field, v, mult[i])

    return add, tilde_add, mult, tilde_mult

def replace_symbols_in_polynomial(poly: Poly, v: int, w: int) -> Poly:
    """
    Replace the symbols in a SymPy polynomial.

    Assumes poly.gens are ordered as:
      first v gens  -> z_0..z_{v-1}
      next w gens   -> x_0..x_{w-1}
      next w gens   -> y_0..y_{w-1}
    """
    original_symbols = list(poly.gens)

    z_symbols = list(symbols(f"z_:{v}"))
    x_symbols = list(symbols(f"x_:{w}"))
    y_symbols = list(symbols(f"y_:{w}"))
    new_gens = z_symbols + x_symbols + y_symbols

    expected = v + 2 * w
    if len(original_symbols) != expected:
        raise ValueError(
            f"Expected {expected} generators (v + 2w), got {len(original_symbols)}: {original_symbols}"
        )

    replacement_map = {
        **dict(zip(original_symbols[:v], z_symbols)),
        **dict(zip(original_symbols[v : v + w], x_symbols)),
        **dict(zip(original_symbols[v + w : v + 2 * w], y_symbols)),
    }

    replaced_expr = poly.as_expr().subs(replacement_map)
    return Poly(replaced_expr, *new_gens, domain=poly.domain)