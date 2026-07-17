"""
Arithmetic circuits for GKR.

This module is now just the ArithmeticCircuit class, which orchestrates:

    gkr.expressions   text -> SymPy -> a Graphviz circuit (parsing, padding)
    gkr.graph         DOT -> networkx -> strictly layered DAG, structural checks
    gkr.wiring        gate values, wiring predicates, their multilinear extensions
    gkr.errors        the CircuitError hierarchy every stage raises
    gkr.ac_render     every line any of this prints

The constructor raises rather than warning: there is no such thing as a
half-built circuit. Names the notebooks import are re-exported at the bottom.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

import networkx as nx
from sympy import isprime
from sympy.polys.domains import GF

from .errors import (
    CircuitConstructionFailed,
    CircuitError,
    DegenerateLayer,
    FanInNotTwo,
    InputsNotAtBottom,
    NotADag,
    NotStrictlyLayered,
    SymbolicInputs,
)
from .expressions import (
    _expression_depth,
    create_arithmetic_circuit,
    pad_expression,
    parse_expression,
)
from .graph import (
    check_fan_in_two,
    check_layer_structure,
    check_unique_layer_assignment,
    deep_copy_and_add_labels,
    dot_source_to_networkx,
    find_graph_depth_dag,
    partition_layers,
    relabel_dot_source,
    relabel_nodes_with_layers_and_get_map,
)
from .mle import multilinear_extension
from .utils import PINK, RED, RESET, YELLOW, TerminalOutput, out, print_header
from .wiring import (
    construct_W_and_wiring_dicts,
    flatten_inner_tuples,
    generate_add_mult_functions_and_extensions,
    generate_layer_functions_and_extensions,
    replace_symbols_in_polynomial,
)


def _is_field_literal(label: str) -> bool:
    """Whether a gate label is a concrete integer, as opposed to a symbol."""
    try:
        int(label)
    except (TypeError, ValueError):
        return False
    return True


class ArithmeticCircuit:
    """
    Represents an arithmetic circuit constructed from mathematical expressions.

    This class enables the creation, analysis, and manipulation of arithmetic circuits represented as directed acyclic graphs (DAGs).
    It integrates functionality for visualization, gate evaluation, and wiring predicate computation using Graphviz and NetworkX libraries.

    Attributes:
        graphviz_circuit (Digraph): A Graphviz Digraph representation of the circuit, created from input expressions.
        networkx_circuit_machine_ID (nx.DiGraph): A NetworkX DiGraph representation of the circuit with machine-generated node IDs.
        is_dag (bool): Indicates whether the circuit is a Directed Acyclic Graph (DAG). If False, the circuit is invalid.
        fan_in_two (bool): Indicates whether all non-source nodes in the circuit have an in-degree of 2. If False, mathematical results may not apply.
        size (int): Total number of nodes in the circuit graph.
        depth (int): Depth of the circuit graph, measured as the longest path from sinks to sources.
        networkx_circuit (nx.DiGraph): A relabeled NetworkX representation of the circuit with human-readable node IDs.
        node_dict (dict): A mapping from original machine-generated node IDs to human-readable bitstring-based IDs.
        graphviz_circuit_bitstring (Digraph): A Graphviz Digraph representation with node labels replaced by bitstrings.
        layers (dict): A dictionary mapping each layer index to the set of nodes in that layer.
        topological_ordering (list): A topological ordering of nodes in the NetworkX circuit, useful for evaluating the circuit layer by layer.
        W_dict (dict): A dictionary storing the values of each gate in the circuit, layer by layer.
        add_dict (dict): A dictionary representing the addition wiring predicates for each layer.
        mult_dict (dict): A dictionary representing the multiplication wiring predicates for each layer.
        W (dict): A dictionary of functions computing the values of each gate in the circuit for given inputs.
        tilde_W (dict): A dictionary of multilinear extensions of the gate-value functions (W).
        add (dict): A dictionary of functions representing the addition wiring predicates.
        tilde_add (dict): A dictionary of multilinear extensions of the addition wiring predicates.
        mult (dict): A dictionary of functions representing the multiplication wiring predicates.
        tilde_mult (dict): A dictionary of multilinear extensions of the multiplication wiring predicates.

    Methods:
        print_topological_order(): Prints the topological ordering of the nodes in the circuit.
        print_gate_values(): Prints the values assigned to each gate (e.g., W_2(0,0) = 4).
        print_wiring_predicates(): Prints the nonzero wiring predicates for addition and multiplication.
        print_tilde_W(): Prints the multilinear extensions of the gate-value functions (W).
        print_wiring_predicate_mles(): Prints the multilinear extensions of the addition and multiplication wiring predicates.
        print_verification_propagation_equation(mle: Optional[bool]): Prints the layer-wise gate value propagation equation or its multilinear extension version.
        view(which: str = "bitstring", *, format: str = "svg", ...):
            Renders the circuit as a Graphviz diagram (bitstring-labeled or machine-labeled)
            and opens it in the system's default viewer. Intended for use in terminal-based
            workflows where inline display (e.g., Jupyter) is unavailable.

    Usage:
        - Input a list of mathematical expressions to construct the circuit.
        - Visualize the circuit using Graphviz:
              * In Jupyter: display(circuit.graphviz_circuit_bitstring)
              * In a terminal: circuit.view("bitstring")
        - Compute and analyze gate values and wiring predicates.
        - Verify Thaler's identity or the propagation equation.
    """

    def __init__(self, *expr_strings: str, prime: int, pad: bool = False,
                 strict: bool = True, out: TerminalOutput = out):
        """Build a layered arithmetic circuit from one or more expressions.

        By default (strict=True) this raises a CircuitError subclass if the
        expressions do not describe a circuit usable for GKR, and the object is
        never left half-built: anything that returns is complete.

        With strict=False, the GKR-usability failures are RECORDED in
        `self.problems` instead of raised, and construction continues as far as
        it can. This is for exposition -- a notebook showing why '5*4 + 3' is
        not strictly layered wants to display the picture and discuss it, not
        catch an exception -- and for circuits over symbolic inputs, whose gate
        values do not exist but whose structure is perfectly good.

        A circuit with problems is still not usable for GKR: validate_for_gkr()
        refuses it, so a non-strict circuit cannot leak into the protocol. What
        is gone is the old silent failure, where a warning was printed and the
        caller had to hasattr-check five attributes to find out.

        Not affected by strict: an expression that is not a DAG, or has a gate
        with fan-in other than 2, is refused either way. There would be no
        layers to show and nothing to discuss.

        With pad=True, shallow inputs are first padded with multiplications by
        1 so that every input sits at the bottom layer. `self.padding_notes`
        records what was inserted, for the caller to narrate.
        """
        self.out = out
        self.strict = strict
        self.problems: List[CircuitError] = []
        # 0. Underlying field, which must be a prime field
        if not isprime(prime):
            raise ValueError("We can only work with prime fields. Enter a prime number for the order of the field.\n")
        else:
            self.field = GF(prime, symmetric=False)
        # 1. Create the Graphviz circuit
        self.padding_notes: List[str] = []

        if pad:
            # The circuit's depth is set by its DEEPEST output, so every output
            # must be padded to that, not to its own depth. Padding each
            # expression against itself would leave a shallow output's inputs
            # sitting above the bottom layer -- which is exactly what GKR
            # refuses.
            parsed = [parse_expression(e) for e in expr_strings]
            target = max(_expression_depth(e) for e in parsed)
            padded: List[str] = []
            for expr in parsed:
                padded_expr, notes = pad_expression(expr, target)
                self.padding_notes.extend(notes)
                padded.append(str(padded_expr))
            self.graphviz_circuit = create_arithmetic_circuit(*padded)
        else:
            self.graphviz_circuit = create_arithmetic_circuit(*expr_strings)

        # 2. Convert Graphviz circuit to NetworkX graph
        self.networkx_circuit_machine_ID = dot_source_to_networkx(self.graphviz_circuit.source)

        # 3. Check if the graph is a DAG
        self.is_dag = nx.is_directed_acyclic_graph(self.networkx_circuit_machine_ID)
        if not self.is_dag:
            raise NotADag("the purported circuit is not a directed acyclic graph")

        # 4. Check if all non-source nodes have fan-in of 2
        self.fan_in_two = check_fan_in_two(self.networkx_circuit_machine_ID)
        if not self.fan_in_two:
            g = self.networkx_circuit_machine_ID
            bad = sorted(
                f"{n} (fan-in {g.in_degree(n)})"
                for n in g.nodes if g.in_degree(n) not in (0, 2)
            )
            raise FanInNotTwo("some gates do not have exactly two inputs: " + ", ".join(bad))

        # 5. Size of the graph (number of nodes)
        self.size = self.networkx_circuit_machine_ID.number_of_nodes()

        # 6. Depth of the graph
        self.depth = find_graph_depth_dag(self.networkx_circuit_machine_ID) if self.is_dag else None

        # 7. Relabel nodes and get the mapping
        self.networkx_circuit, self.node_dict = relabel_nodes_with_layers_and_get_map(self.networkx_circuit_machine_ID)

        # 8. Create new graphviz_circuit that is a copy of the original but with bitstring node labels.
        self.graphviz_circuit_bitstring = deep_copy_and_add_labels(self.graphviz_circuit,self.node_dict)

        # 9. Partition nodes into layers
        self.layers = partition_layers(self.networkx_circuit)

        # Check structure of circuit
        try:
            check_unique_layer_assignment(self.networkx_circuit, self.layers)
            check_layer_structure(self.networkx_circuit, self.layers)
        except CircuitError as e:
            self._refuse(e)

        # 10. Compute the topological ordering as an attribute
        self.topological_ordering = list(nx.topological_sort(self.networkx_circuit)) if self.is_dag else None

        # 11. Create wiring predicates. First step, create W_dict
        # Every source (an input) must sit at the bottom layer, or the circuit is
        # not strictly layered and Thaler's identity does not apply layer by layer.
        # (self.layers indexes the RELABELLED graph, so query that one.)
        bottom = max(self.layers)
        strays = sorted(
            str(self.networkx_circuit.nodes[n].get("label", n)).strip('"')
            for layer, nodes in self.layers.items() if layer != bottom
            for n in nodes
            if self.networkx_circuit.in_degree(n) == 0
        )
        if strays:
            self._refuse(InputsNotAtBottom(
                f"input(s) {', '.join(strays)} do not sit at the bottom layer "
                f"(layer {bottom}), so not every path from an output to an input "
                f"has the same length"
            ))

        # Gate values need concrete inputs. '5*x + (3*4)' describes a perfectly
        # good circuit whose values simply do not exist; say so precisely rather
        # than letting int('x') surface as "structurally unusual".
        symbolic = sorted({
            lbl for nodes in self.layers.values() for n in nodes
            if self.networkx_circuit.in_degree(n) == 0
            for lbl in [str(self.networkx_circuit.nodes[n].get("label", n)).strip('"')]
            if not _is_field_literal(lbl)
        })
        if symbolic:
            self._refuse(SymbolicInputs(
                f"input(s) {', '.join(symbolic)} are symbolic, so the gate values "
                f"are not defined"
            ))
            return

        try:
            self.W_dict, self.add_dict, self.mult_dict = construct_W_and_wiring_dicts(self.networkx_circuit_machine_ID, self.node_dict, self.layers,self.field.mod)
            self.W, self.tilde_W = generate_layer_functions_and_extensions(self.W_dict, self.field,multilinear_extension)
            self.add, self.tilde_add, self.mult, self.tilde_mult = generate_add_mult_functions_and_extensions(self.add_dict, self.mult_dict, self.field, multilinear_extension)
        except CircuitError as e:
            self._refuse(e)
        except Exception as e:
            self._refuse(CircuitConstructionFailed(
                f"unable to construct gate values or wiring predicates: {e}"
            ), cause=e)

    def _refuse(self, error: CircuitError, cause: Optional[Exception] = None) -> None:
        """Raise (strict) or record (not strict). See __init__."""
        if self.strict:
            raise error from cause
        self.problems.append(error)

    def describe_problems(self) -> str:
        """One line per problem, each with its hint. Empty if there are none."""
        return "\n".join(
            f"{type(e).__name__}: {e}" + (f"\n    {e.hint}" if e.hint else "")
            for e in self.problems
        )

    def view(
        self,
        which: str = "bitstring",
        *,
        format: str = "svg",
        filename: Optional[str] = None,
        directory: Optional[os.PathLike] = None,
        open_file: bool = True,
        cleanup: bool = False,
    ) -> Path:
        """
        Render the circuit graph to disk and (optionally) open it in the OS default viewer.

        Args:
            which: "bitstring" (default) or "machine".
                - "bitstring" uses self.graphviz_circuit_bitstring
                - "machine" uses self.graphviz_circuit
            format: "svg" (default), "png", "pdf", etc. Must be supported by graphviz.
            filename: base filename without extension. If None, an auto name is used.
            directory: output directory. If None, uses a temp directory.
            open_file: if True, open the rendered file in the default viewer.
            cleanup: if True, delete intermediate files created by graphviz (keeps the final).

        Returns:
            Path to the rendered file.
        """
        if shutil.which("dot") is None:
            raise RuntimeError(
            "Graphviz system executable 'dot' not found on PATH. "
            "Install Graphviz (system package) and ensure 'dot' is available."
            )
        # Pick which graphviz object to render
        if which.lower() in {"bitstring", "bits", "bit"}:
            dot = self.graphviz_circuit_bitstring
            default_stem = "arithmetic_circuit_bitstring"
        elif which.lower() in {"machine", "raw", "original"}:
            dot = self.graphviz_circuit
            default_stem = "arithmetic_circuit"
        else:
            raise ValueError("which must be 'bitstring' or 'machine'")

        # Configure output location
        out_dir = Path(directory) if directory is not None else Path(tempfile.gettempdir())
        out_dir.mkdir(parents=True, exist_ok=True)

        stem = filename or default_stem
        # graphviz wants a path WITHOUT extension; it appends ".{format}"
        out_path_no_ext = out_dir / stem

        # Make sure the Digraph knows the intended output format
        dot.format = format

        # Render (graphviz will create out_path_no_ext + ".{format}")
        rendered_path_str = dot.render(
            filename=str(out_path_no_ext),
            cleanup=cleanup,
            quiet=True,
        )
        rendered_path = Path(rendered_path_str)

        # Open in default viewer
        if open_file:
            self._open_path(rendered_path)

        return rendered_path

    def _open_path(self, path: Path) -> None:
        """
        Open a file path in the OS default application.
        """
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
        except Exception as e:
            out.print(f"Could not open file automatically: {e}")
            out.print(f"Rendered file is at: {path}")

    def print_topological_order(self) -> None:
        """
        Prints the topological ordering of the nodes in the circuit.
        """
        if not self.is_dag:
            raise ValueError(f"{RED}\nThe provided graph is not a directed acyclic graph (DAG).{RESET}\n")

        assert self.topological_ordering is not None  # guaranteed by the is_dag guard above
        print_header(f"{PINK}Topological ordering{RESET}\n", level=2, out=self.out)
        self.out.print(f" {YELLOW}->{RESET} ".join(self.topological_ordering))

    def print_gate_values(self) -> None:
        """
        Prints the value assigned to each gate, e.g. W_2(0,0) = 4 and so on
        """
        print_W_dict(self.W_dict)

    def print_wiring_predicates(self) -> None:
        """
        Prints nonzero wiring predicates
        """
        print_add_mult_dicts(self.add_dict, self.mult_dict, W_dict=self.W_dict, out=self.out)

    def print_tilde_W(self):
        """
        Prints multilinear extensions of gate-value functions W
        """
        print_multilinear_extensions(self.W_dict, self.tilde_W)

    def print_wiring_predicate_mles(self) -> None:
        """Print the multilinear extensions of the wiring predicates."""
        from .ac_render import render_print_wiring_predicate_mles
        render_print_wiring_predicate_mles(self, out=self.out)

    def print_verification_propagation_equation(
        self,
        mle: Optional[bool] = None,
        random_selection: Optional[int] = None,
        *,
        max_full_check: int = 1000,
        sample_limit: int = 1000,
        display_limit: int = 100,
        seed: Optional[int] = None,
    ) -> None:
        """Verify (and print) the gate-value propagation equation, or Thaler's
        identity if mle=True."""
        from .ac_render import render_print_verification_propagation_equation
        render_print_verification_propagation_equation(
            self, mle=mle, random_selection=random_selection,
            max_full_check=max_full_check, sample_limit=sample_limit,
            display_limit=display_limit, seed=seed, out=self.out,
        )


# Example usage
if __name__ == "__main__":
    # Create the arithmetic circuit with multiple expressions
    dot = create_arithmetic_circuit(
        '(2 + 2)*(3*3)',
        '(3*4) + (5 + 5)'
    )
    # Render the graph to a file and display it
    dot.render('arithmetic_circuit', view=True)


# Helper function for print_add_mult_dicts below


# ---------------------------------------------------------------------------
# Re-exports: gkr.ac stays the front door for circuits, so the notebooks and
# gkr.protocol keep importing from here while the implementation lives in the
# modules above.
# ---------------------------------------------------------------------------

from .ac_render import (  # noqa: E402,F401
    print_add_mult_dicts,
    print_multilinear_extensions,
    print_topological_ordering,
    print_W_dict,
)

__all__ = [
    "ArithmeticCircuit",
    # errors
    "CircuitError", "NotADag", "FanInNotTwo", "InputsNotAtBottom",
    "NotStrictlyLayered", "DegenerateLayer", "SymbolicInputs",
    "CircuitConstructionFailed",
    # expressions
    "parse_expression", "pad_expression", "create_arithmetic_circuit",
    # graph
    "dot_source_to_networkx", "partition_layers", "check_fan_in_two",
    "find_graph_depth_dag", "relabel_nodes_with_layers_and_get_map",
    "relabel_dot_source", "deep_copy_and_add_labels",
    "check_layer_structure", "check_unique_layer_assignment",
    # wiring
    "construct_W_and_wiring_dicts", "flatten_inner_tuples",
    "generate_layer_functions_and_extensions",
    "generate_add_mult_functions_and_extensions",
    "replace_symbols_in_polynomial",
    # display
    "print_W_dict", "print_add_mult_dicts", "print_multilinear_extensions",
    "print_topological_ordering",
]