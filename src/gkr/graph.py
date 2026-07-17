"""
Graph surgery: DOT -> networkx -> layers.

Takes the Graphviz circuit built by gkr.expressions and turns it into a
strictly layered DAG with bitstring gate labels, refusing (see gkr.errors) if
the expression does not describe one. Gate values and wiring predicates are
gkr.wiring's job.
"""
from __future__ import annotations

import re
from collections import defaultdict

import networkx as nx
import pydot
from graphviz import Digraph
from networkx.drawing.nx_pydot import from_pydot

from .errors import NotStrictlyLayered


def parse_dot_source(dot_source: str):
    """
    Parse a DOT source string to extract nodes, edges, and their attributes.

    Args:
        dot_source (str): The DOT source code as a string.

    Returns:
        dict: A dictionary with 'nodes' and 'edges'.
            - 'nodes': A dictionary mapping node IDs to their attributes (label, shape).
            - 'edges': A list of tuples representing edges (tail_node, head_node).
    """
    # Patterns for extracting nodes and edges
    node_pattern = re.compile(r'^\s*(\w+)\s*\[label="([^"]+)"\s+shape=([^]]+)\];?$', re.MULTILINE)
    edge_pattern = re.compile(r'^\s*(\w+)\s*->\s*(\w+)\s*;?$', re.MULTILINE)

    # Extract nodes with attributes
    nodes = {}
    for match in node_pattern.findall(dot_source):
        node_id, label, shape = match
        nodes[node_id] = {'label': label, 'shape': shape}

    # Extract edges
    edges = edge_pattern.findall(dot_source)

    return {'nodes': nodes, 'edges': edges}

def dot_source_to_networkx(dot_source: str) -> nx.DiGraph:
    """
    Converts a DOT source string to a NetworkX directed graph.

    Args:
        dot_source (str): The DOT source code as a string.

    Returns:
        nx.DiGraph: The corresponding NetworkX directed graph.
    """
    # Parse the DOT source into a Pydot graph. pydot returns None on a
    # parse failure; fail with the reason rather than a cryptic TypeError.
    parsed = pydot.graph_from_dot_data(dot_source)
    if not parsed:
        raise ValueError("pydot could not parse the DOT source for this circuit")
    pydot_graph = parsed[0]

    # Convert the Pydot graph to a NetworkX graph
    nx_graph = from_pydot(pydot_graph)
    return nx_graph

def check_fan_in_two(nx_graph: nx.DiGraph) -> bool:
    """
    Checks the in-degree of each node in the graph. If any non-input node
    has an in-degree other than 2, returns False. Otherwise, returns True

    Args:
        nx_graph (nx.DiGraph): A directed graph representing the arithmetic circuit.

    Returns:
        True or False
    """
    for node in nx_graph.nodes:
        indegree = nx_graph.in_degree(node)
        if indegree == 0:
            # Input nodes are expected to have in-degree 0
            continue
        elif indegree != 2:
            # Non-input nodes must have in-degree 2
            return False
    return True

def find_graph_depth_dag(nx_graph: nx.DiGraph) -> int:
    """
    Finds the depth of a directed acyclic graph (DAG).

    Args:
        nx_graph (nx.DiGraph): A directed acyclic graph.

    Returns:
        int: The depth (longest path length) of the graph.
    """
    # Ensure the graph is a DAG
    if not nx.is_directed_acyclic_graph(nx_graph):
        raise ValueError("The graph is not a directed acyclic graph (DAG).")

    # Perform a topological sort
    topo_order = list(nx.topological_sort(nx_graph))

    # Compute the longest path
    longest_path_length = {node: 0 for node in topo_order}
    for node in topo_order:
        for successor in nx_graph.successors(node):
            longest_path_length[successor] = max(
                longest_path_length[successor],
                longest_path_length[node] + 1
            )

    return max(longest_path_length.values())

def partition_layers(nx_graph: nx.DiGraph) -> dict[int, set[str]]:
    """
    Partitions the nodes of a graph into layers based on their distance from all sink nodes.
    The layers are indexed by distance, and each layer contains the union of nodes at that distance
    from any sink.

    Args:
        nx_graph (nx.DiGraph): A directed graph.

    Returns:
        dict[int, set[str]]: A dictionary where the keys are distances (layer indices)
                             and the values are sets of nodes in each layer.
    """
    # Find all sink nodes
    sinks = [node for node in nx_graph.nodes if nx_graph.out_degree(node) == 0]

    # Initialize a dictionary to store the union of layers across all sinks
    combined_layers = defaultdict(set)

    # Process each sink node
    for sink in sinks:
        # Reverse the graph to measure distances toward the sink
        reversed_graph = nx.reverse(nx_graph)

        # Compute shortest path lengths from the sink
        distances = nx.single_source_shortest_path_length(reversed_graph, source=sink)

        # Add nodes to the appropriate layer
        for node, distance in distances.items():
            combined_layers[distance].add(node)

    # Convert defaultdict to a regular dict and return
    return dict(combined_layers)

def check_layer_structure(nx_graph: nx.DiGraph, layers: dict[int, set[str]]) -> None:
    """
    Verify that the graph is strictly layered, raising NotStrictlyLayered if not.

    Checks that:

    For every node in layer i:
    - Layer 0 (output layer) has incoming edges only from layer 1.
    - Layer i (for 1 <= i < d-1) has incoming edges only from layer i+1.
    - Layer d-1 (input layer) has no incoming edges.

    Args:
        nx_graph (nx.DiGraph): A directed graph.
        layers (dict[int, set[str]]): A dictionary of layers, where keys are the layer indices and the values are sets
                                      of nodes in each layer.

    Raises:
        NotStrictlyLayered: on the first violation found.
    """
    # Find the maximum layer index (the input layer)
    max_layer = max(layers.keys())

    # (1) Check that the output layer (layer 0) has incoming edges only from layer 1
    for u in layers[0]:  # The output layer is layer 0
        for pred in nx_graph.predecessors(u):
            if pred not in layers[1]:
                raise NotStrictlyLayered(
                    f"node {u} in layer 0 has an incoming edge from {pred}, which is not in layer 1"
                )

    # (2) Check that layers i (for 1 <= i < max_layer-1) have incoming edges only from layer i+1
    for i in range(1, max_layer):  # Skip the first and last layers
        for u in layers[i]:  # For each node u in layer i
            for pred in nx_graph.predecessors(u):
                if pred not in layers[i + 1]:
                    raise NotStrictlyLayered(
                        f"node {u} in layer {i} has an incoming edge from {pred}, "
                        f"which is not in layer {i + 1}"
                    )

    # (3) Check that the input layer (max_layer) has no incoming edges
    for u in layers[max_layer]:  # The input layer is layer max_layer
        if nx_graph.in_degree(u) > 0:
            raise NotStrictlyLayered(
                f"node {u} in the input layer ({max_layer}) has incoming edges"
            )

def check_unique_layer_assignment(nx_graph: nx.DiGraph, layers: dict[int, set[str]]) -> None:
    """
    Verify that every node appears in exactly one layer, raising
    NotStrictlyLayered if not.

    Args:
        nx_graph (nx.DiGraph): A directed graph.
        layers (dict[int, set[str]]): A dictionary of layers, where keys are the layer indices and the values are sets
                                      of nodes in each layer.

    Returns:
        None. Raises NotStrictlyLayered on the first violation found.
    """
    # Set to track nodes we have seen across layers
    seen_nodes = set()

    # Iterate over each layer and its nodes
    for layer, nodes in layers.items():
        for node in nodes:
            # If the node has already been seen, it appears in more than one layer
            if node in seen_nodes:
                raise NotStrictlyLayered(f"node {node} appears in more than one layer")
            seen_nodes.add(node)

    # Ensure that all nodes in the graph are accounted for in the layers
    all_nodes_in_layers = set(node for nodes in layers.values() for node in nodes)
    graph_nodes = set(nx_graph.nodes)

    if all_nodes_in_layers != graph_nodes:
        missing_nodes = graph_nodes - all_nodes_in_layers
        extra_nodes = all_nodes_in_layers - graph_nodes
        if missing_nodes:
            raise NotStrictlyLayered(f"nodes missing from every layer: {sorted(missing_nodes)}")
        if extra_nodes:
            raise NotStrictlyLayered(f"nodes assigned to a layer but absent from the graph: {sorted(extra_nodes)}")

def relabel_nodes_with_layers_and_get_map(nx_graph: nx.DiGraph) -> tuple[nx.DiGraph, dict]:
    """
    Relabel the nodes of a graph using the scheme:
    'i.bbbb...b', where 'i' is the layer index and 'bbbb...b' is the
    zero-padded binary representation of the node's position within the layer.

    In the degenerate case where the layer contains only one node, the bitstring is '_'.

    Args:
        nx_graph (nx.DiGraph): A directed graph.

    Returns:
        tuple[nx.DiGraph, dict]: A new graph with nodes relabeled and the mapping of old IDs to new IDs.
    """
    layers = partition_layers(nx_graph)  # Get layers
    relabel_map = {}  # Initialize relabeling map

    for i, nodes in layers.items():
        sorted_nodes = sorted(nodes)  # Sort the nodes
        if len(sorted_nodes) == 1:  # Degenerate case: single node in the layer
            bitstring = "_"
            node = next(iter(sorted_nodes))  # Only one node exists
            new_id = f"{i}.{bitstring}"  # Create new ID
            relabel_map[node] = new_id  # Map old to new ID
        else:  # General case: multiple nodes in the layer
            bitstring_length = len(bin(len(sorted_nodes) - 1)[2:])  # Max bitstring length
            for idx, node in enumerate(sorted_nodes):
                bitstring = bin(idx)[2:].zfill(bitstring_length)  # Convert to binary and pad
                new_id = f"{i}.{bitstring}"  # Create new ID
                relabel_map[node] = new_id  # Map old to new ID

    # Relabel the graph nodes
    relabeled_graph = nx.relabel_nodes(nx_graph, relabel_map)
    return relabeled_graph, relabel_map

def relabel_dot_source(dot_source: str, relabel_map: dict) -> str:
    """
    Relabels the nodes in a DOT source string according to the provided mapping.

    Args:
        dot_source (str): The original DOT source string.
        relabel_map (dict): A dictionary mapping old node IDs to new node IDs.

    Returns:
        str: The relabeled DOT source string.
    """
    # Replace old node IDs with new IDs in the DOT source
    for old_id, new_id in relabel_map.items():
        dot_source = dot_source.replace(str(old_id), str(new_id))
    return dot_source

def deep_copy_and_add_labels(dot_obj: Digraph, new_labels: dict, font_size: int = 10) -> Digraph:
    """
    Deep copies a Graphviz Digraph object and adds new labels to its nodes.

    Args:
        dot_obj (Digraph): The original Graphviz Digraph.
        new_labels (dict): A dictionary mapping old node IDs to new labels.
        font_size (int): Font size for the node labels.

    Returns:
        Digraph: A new Graphviz Digraph with updated node labels.
    """
    # Step 1: Create a deep copy of the original graph
    copied_dot = Digraph(name=dot_obj.name, comment=dot_obj.comment, format=dot_obj.format)

    # Set the graph orientation to Bottom-to-Top (BT)
    copied_dot.attr(rankdir="BT")

    # Step 2: Extract old labels from the original dot source
    old_labels = {}
    label_pattern = r'label="([^"]*)"|label=([^ ]*)'
    for line in dot_obj.source.splitlines():
        if '[' in line and 'label=' in line:  # Node definition line with a label
            node_id = line.split()[0]
            label_match = re.search(label_pattern, line)
            if label_match:
                # Extract the label from the match
                old_label = label_match.group(1) if label_match.group(1) else label_match.group(2)
                old_labels[node_id] = old_label

    # Step 3: Add updated nodes with new labels
    for node_id, new_label in new_labels.items():
        if node_id in old_labels:
            old_label = old_labels[node_id]
            new_label_part = str(new_label).split('.')[-1]  # Ensure new_label is a string and take the part after the `.`

            # Combine old_label and new_label
            # combined_label = f"{old_label}\n{new_label_part}"
            combined_label = f"""<<FONT COLOR="black">{old_label}</FONT><BR/><FONT COLOR="blue">{new_label_part}</FONT>>"""

            # Determine shape based on new_label length
            shape = "ellipse" if len(new_label_part) > 3 else "circle"

            # Add the updated node to the copied graph
            copied_dot.node(node_id, label=combined_label, shape=shape, fontsize=str(font_size))

    # Step 4: Preserve edges
    for line in dot_obj.source.splitlines():
        if '->' in line:  # Edge definition
            copied_dot.body.append(line)  # Preserve edges

    return copied_dot