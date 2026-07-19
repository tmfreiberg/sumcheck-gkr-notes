---
title: Arithmetic circuits
kernelspec:
  name: python3
  display_name: Python 3
---

```{code-cell} python
:tags: [remove-cell]
import gkr
env = gkr.init(verbose=False)
from gkr.ac import ArithmeticCircuit
```

(sec-introduction)=
## Introduction

Through our [sum-check protocol](./01-sum-check-protocol.md) and [multilinear extensions](./02-multilinear-extensions.md) notebooks, we have started to replicate Thaler's elegant presentation [@tha2015] of the GKR interactive proof for circuit evaluation, as introduced by Goldwasser, Kalai, and Rothblum [@gkr2008; @gkr2015]. We are nearly ready to present the GKR protocol in full, but before we do, there's one final topic to address: arithmetic circuits.

(sec-definition)=
## Modeling computations

An arithmetic circuit is defined as a special kind of directed graph, which is assumed to be familiar to the reader.

```{prf:definition} arithmetic circuit
:label: def-arithmetic-circuit
An _arithmetic circuit_ $C$ over a field $\mathbb{F}$ in the variables $X = \{x_0, \ldots, x_{n-1}\}$ is a labeled directed acyclic multigraph (DAG). The nodes of this graph are called _gates_, and the edges are called _wires_.

- _Input gates_ are gates with _fan-in_ (in-degree) zero, labeled by variables from $X$ or constants from $\mathbb{F}$.
  
- _Output gates_ are gates with _fan-out_ (out-degree) zero, where the output of the circuit is computed.

- _Non-input gates_ are either _addition gates_, labeled with the addition operation ($+$), or _multiplication gates_, labeled with the multiplication operation ($\times$). These gates compute the sum or product of the polynomials computed on the tails of the incoming wires. Subtraction can be represented by multiplication with the constant $-1$ (i.e., using $(x - y) = x + (-1) \cdot y$).

* The _output_ of $C$ is the polynomial (or set of polynomials) computed at the output gate(s).

* The _size_ $S$ of $C$ is the total number of gates in the graph, and the _depth_ $d$ of $C$ is the length of the longest path from an input gate to an output gate.

* Layer $i$ of $C$ is a set of all gates $v$ such that the shortest path from $v$ to any output gate has length $i$. We index layers starting from the output layer (Layer $0$), increasing as we move toward the inputs. This convention is convenient for top-down verification in the GKR protocol.

We say that $C$ is a _constant-input_ circuit if:

* Every input gate is labeled with a constant from $\mathbb{F}$ (as opposed to a variable from $X$).

We say that $C$ is a _binary_ arithmetic circuit if:

* Every non-input gate has a fan-in of $2$, representing a _binary_ operation on two inputs.

We say that $C$ is a _strictly layered_ arithmetic circuit if:

* All inputs are in Layer $d$, and every wire is a wire from a gate in Layer $i + 1$ to a gate in Layer $i$, for some $i \in \{0,1,\ldots,d - 1\}$, where $d$ is the depth of the circuit.

```

```{prf:assumption}
:label: asm-assumption
Throughout, we will assume that all of our arithmetic circuits are **constant-input**, **binary** and **strictly layered**. 

Under the **constant-input** restriction, the circuit computes a constant polynomial. We adopt this model because, in the GKR protocol, verification concerns the correctness of gate evaluations rather than symbolic polynomial computation. Allowing variable-labeled inputs would require only notational changes and does not affect the protocol. 

The **binary** fan-in assumption ensures that wiring predicates depend on exactly two child gates, which will be essential when defining the verification equations in later sections. 

The **strictly layered** assumption is made primarily for conceptual and notational simplicity. In the GKR protocol, verification proceeds layer by layer, with each round reducing correctness of one layer to a polynomial identity checked via sum-check. Strict layering ensures that all dependencies are local to adjacent layers, yielding uniform wiring predicates and a clean inductive structure. This assumption is not restrictive. Any arithmetic circuit can be transformed into a strictly layered circuit by inserting identity gates, with at most polynomial overhead. The protocol and its soundness guarantees extend to general circuits after such a normalization.

```

````{prf:example}
:label: eg-evaluate
Consider evaluating the expressions $(2 + 2) \times (3 \times 3)$ and $3 \times 4 + (5 + 5)$ in the field $\mathbb{F} = \mathbb{Z}/11\mathbb{Z}$. The following circuit of size $S = 10$ and depth $d = 2$ illustrates one way to perform this computation:

- **Layer 0 (output layer)**: The top layer contains the two gates labeled $\times$ and $+$.
- **Layer 1 (intermediate layer)**: The middle layer contains four gates labeled $+$, $\times$, $\times$, and $+$.
- **Layer 2 (input layer)**: The bottom layer contains four gates labeled $2$, $3$, $4$, and $5$. (Although the number $3$ appears only once as an input gate, it has fan-out three: its value is used as an input to two multiplication operations via three outgoing wires.)

In this structure:
- Every input gate is labeled with a constant from $\mathbb{F}$. This is a constant-input circuit.
- Every gate in layers 0 and 1 has a fan-in of $2$ (representing a binary operation, either addition or multiplication). This is a binary circuit.
- All inputs are in Layer 2: no inputs are in Layer 0 or Layer 1. Also, wires only connect consecutive layers: from Layer 2 to Layer 1, and from Layer 1 to Layer 0. No wires connect gates within the same layer, non-consecutive layers, or consecutive layers in the 'low to high' (e.g. 1 to 2) direction. This is a strictly layered circuit.

For example:
- The two wires from the gate labeled $2$ enter the leftmost gate in Layer 1 labeled $+$, representing the subexpression $2 + 2$.
- Similarly, the gates in Layer 1 compute the subexpressions $3 \times 3$, $3 \times 4$, and $5 + 5$ in parallel. 

Next, in Layer 1, we evaluate:
- $2 + 2 \equiv 4 \bmod 11$,
- $3 \times 3 \equiv 9 \bmod 11$,
- $3 \times 4 \equiv 1 \bmod 11$,
- $5 + 5 \equiv 10 \bmod 11$.

Finally, the output layer computes:
- $4 \times 9 \equiv 3 \bmod 11$,
- $1 + 10 \equiv 0 \bmod 11$.

Thus, the circuit computes two expressions through six binary operations performed in two stages, holding four field elements in memory at each stage.

```{code-cell} python
expression_01a = '(2 + 2)*(3*3)'
expression_01b = '3*4 + (5 + 5)'

ac_01 = ArithmeticCircuit(expression_01a, expression_01b, prime=11)
print(f"{expression_01a} mod {ac_01.field.mod}, {expression_01b} mod {ac_01.field.mod}")
display(ac_01.graphviz_circuit)

print(f"This circuit has size S = {ac_01.size} and depth d = {ac_01.depth}.")
```
````

(sec-topological-ordering)=
## Topological ordering

An arithmetic circuit cannot have cycles because it represents a well-defined, finite computation. They are designed to compute polynomials in a finite number of steps. If a cycle existed, it would be unclear where to start, and the computation would never terminate. For example, the cycle below results in the expression $2 + (3 \times (2 + ( 3 \times \cdots )))$ (or $3 \times (2 + (3 \times ( 2 + \cdots )))$), which is ambiguous and infinite, making it meaningless. Arithmetic circuits are acyclic to ensure that each operation is performed in a clear, finite sequence.

```{code-cell} python
from graphviz import Digraph

# Non-DAG example
dot = Digraph()
dot.node('2', '2', shape='circle')
dot.node('+', '+', shape='circle')
dot.node('3', '3', shape='circle')
dot.node('×', '×', shape='circle') 
dot.edge('2', '+')
dot.edge('+', '3')
dot.edge('3', '×') 
dot.edge('×', '2')
dot.attr(rankdir='LR')
display(dot)
```

A _topological ordering_ (or _topological sort_) of a directed graph is a linear ordering of its vertices such that, for every directed edge from vertex $u$ to vertex $v$, vertex $u$ appears before vertex $v$ in the ordering. In other words, the ordering respects the direction of the edges.

More formally:

```{prf:definition} topological ordering
:label: def-topological-ordering
Given a directed acyclic graph (DAG) $ G = (V, E) $, a _topological ordering_ of the vertices $V$ is a linear sequence $v_0, v_1, \ldots, v_{n-1}$ such that for every directed edge $(v_i, v_j) \in E$, it holds that $i < j$, meaning that vertex $v_i$ appears before vertex $v_j$ in the ordering. 
```

Since an arithmetic circuit is acyclic, a _topological order_ of its nodes allows us to evaluate the circuit in a sequence where each node (operation) depends only on previously evaluated nodes. This ensures that each computation is performed in a clear, finite order, starting from the input nodes and progressing through intermediate gates to the output nodes. Without a valid topological order, cycles would create circular dependencies, preventing the circuit from being evaluated at all. Therefore, topological ordering guarantees that the computation proceeds in a finite, unambiguous manner.

````{prf:example}
:label: eg-topological

```{code-cell} python
display(ac_01.layers)
print("")
display(ac_01.graphviz_circuit_bitstring)
print("")
ac_01.print_topological_order()
```
````

(sec-gate-values)=
## Gate-value functions

A gate-value function is a function that records the values computed by all gates in a given layer of an arithmetic circuit, where gates are indexed by their binary identifiers. We formalize this notion below.

```{prf:definition} layer size, bit length, and bit labeling
:label: def-layer-size-bit-length-and-bit-labeling
Let $C$ be an arithmetic circuit of depth $d$. For $0 \le i \le d$, let $S_i$ denote the number of gates in Layer $i$, and let $s_i$ be the smallest integer such that $S_i \leq 2^{s_i}$. We refer to $S_i$ as the _size_ of Layer $i$, and $s_i$ as the _bit length_ of Layer $i$. A _bit labeling_ of the gates in Layer $i$ assigns each gate a unique bitstring of length $s_i$, corresponding to the binary representation of its index in the layer. If $\mathbf{b} \in \{0,1\}^{s_i}$, we refer to the gate in Layer $i$ labeled by $\mathbf{b}$ as _gate $\mathbf{b}$_.

```

```{prf:remark}
:label: rem-degenerate-labeling
In the degenerate case where $S_i = 1$ and $s_i = 0$, a bit labeling assigns the only gate, which has index $0$, to the empty string $()$. This will be the case in Layer $0$ of a circuit with a single output. More formally, a bit labeling is a map $\ell : \{0, \ldots, S_i - 1\} \to \{0,1\}^{s_i}$. When $S_i = 1$ and $s_i = 0$, we interpret $\{0,1\}^{s_i}$ as the singleton set whose only element is the empty set. In this case, $\ell : \{0\} \to \{\emptyset\}$ maps $0$ to $\ell(0) = \emptyset$, which we represent as $()$.
```

```{prf:definition} gate-value function
:label: def-gate-value-function
Let $C$ be a constant-input, binary, strictly layered arithmetic circuit of depth $d$ over a field $\mathbb{F}$. For $0 \leq i \leq d$, let Layer $i$ have size $S_i$ and bit length $s_i$, and fix a bit labeling of each layer. The **gate-value function** $W_i : \{0,1\}^{s_i} \to \mathbb{F}$ is defined as follows:

1. **Non-gate labels:** If $\mathbf{b} \in \{0,1\}^{s_i}$ does not correspond to a valid gate label in Layer $i$ (i.e., if $S_i$ is not a power of 2 and $\mathbf{b}$ represents an integer exceeding $S_i - 1$), then:  
\begin{equation*}
W_i(\mathbf{b}) := 0.
\end{equation*}

3. **Valid gate labels:**  

   - **Layer $d$ (input layer):** For all $\mathbf{b} \in \{0,1\}^{s_d}$, define:  
     \begin{equation*}
     W_d(\mathbf{b}) := \text{the input at gate $\mathbf{b}$ in Layer $d$}.
     \end{equation*}

   - **Intermediate layers, $d-1 \geq i \geq 0$:** For $\mathbf{c} \in \{0,1\}^{s_i}$, let $\mathbf{a}, \mathbf{b} \in \{0,1\}^{s_{i+1}}$ (possibly $\mathbf{a} = \mathbf{b}$) be the gates in Layer $i+1$ connected by wires to gate $\mathbf{c}$. Define:  
     \begin{equation*}
     W_i(\mathbf{c}) := W_{i+1}(\mathbf{a}) \odot W_{i+1}(\mathbf{b}),
     \end{equation*}
     where $\odot$ represents:  
     - Addition, if gate $\mathbf{c}$ is an addition gate;  
     - Multiplication, if gate $\mathbf{c}$ is a multiplication gate.

4. **Multilinear extension:** For each layer $i$, the **multilinear extension** $\widetilde{W}_i : \mathbb{F}^{s_i} \to \mathbb{F}$ is defined to extend $W_i$ to inputs in $\mathbb{F}^{s_i}$.

```

````{prf:example}
:label: eg-gate-values

```{code-cell} python
display(ac_01.graphviz_circuit_bitstring)
```

```{code-cell} python
ac_01.print_gate_values()
```

```{code-cell} python
ac_01.print_tilde_W()
```
````

(sec-wiring-predicates)=
## Wiring predicates

For the purposes of the next definition, we order bitstrings of a given length lexicographically with the most significant bit first (equivalently, by the numeric value of their binary representation). That is, if $\mathbf{a} = (a_0,\ldots,a_{m - 1}) \in \{0,1\}^m$ and $\mathbf{b} = (b_0,\ldots,b_{m - 1}) \in \{0,1\}^m$, we write 

\begin{equation*}
\mathbf{a} \, \le \, \mathbf{b} \quad \Leftrightarrow \quad 2^{m - 1}a_{0} + 2^{m - 2}a_{1} + \cdots + 2^0a_{m - 1} \, \le \, 2^{m - 1}b_{0} + 2^{m - 2}b_1 + \cdots + 2^0b_{m - 1}.
\end{equation*}

This ordering is fixed once and for all and serves only as a convenient convention.

```{prf:definition} wiring predicates
:label: def-wiring-predicates
Let $C$ be a binary, strictly layered arithmetic circuit of depth $d$ over a field $\mathbb{F}$. For $0 \leq i \leq d$, let Layer $i$ have size $S_i$ and bit length $s_i$, and fix a bit labeling of each layer. For $0 \le i \le d - 1$, the _wiring predicates_ 
\begin{equation*}
\begin{align}
\mathrm{add}_i & : \{0,1\}^{s_i} \times \{0,1\}^{s_{i + 1}} \times \{0,1\}^{s_{i + 1}} \to \mathbb{F} \\
\mathrm{mult}_i & : \{0,1\}^{s_i} \times \{0,1\}^{s_{i + 1}} \times \{0,1\}^{s_{i + 1}} \to \mathbb{F}
\end{align}
\end{equation*}
with respect to this bit labeling is defined as follows. Let $\mathbf{c} \in \{0,1\}^{s_i}$, and let $\mathbf{a}, \mathbf{b} \in \{0,1\}^{s_{i + 1}}$ be gates in layer $i + 1$ (with the possibility that $\mathbf{a} = \mathbf{b}$).

* If gate $\mathbf{c}$ is:
  - an addition gate, _and_ 
  - the (multi)set of its two children is $\{\mathbf{a}, \mathbf{b}\}$, _and_ 
  - $\mathbf{a} \le \mathbf{b}$,
  
then we set $\mathrm{add}_i(\mathbf{c}, \mathbf{a}, \mathbf{b}) = 1$; otherwise, we set $\mathrm{add}_i(\mathbf{c}, \mathbf{a}, \mathbf{b}) = 0$.

</p>

* If gate $\mathbf{c}$ is:
  - a multiplication gate, _and_ 
  - the (multi)set of its two children is $\{\mathbf{a}, \mathbf{b}\}$, _and_ 
  - $\mathbf{a} \le \mathbf{b}$,

then we set $\mathrm{mult}_i(\mathbf{c}, \mathbf{a}, \mathbf{b}) = 1$; otherwise, we set $\mathrm{mult}_i(\mathbf{c}, \mathbf{a}, \mathbf{b}) = 0$.

* If $\mathbf{c}$ is the label of a nonexistent gate, i.e., $S_i$ is not a power of $2$ and $\mathbf{c}$ is the binary representation of an integer exceeding $S_i - 1$, $\mathrm{add}_i(\mathbf{c}, \mathbf{a}, \mathbf{b}) = \mathrm{mult}_i(\mathbf{c}, \mathbf{a}, \mathbf{b}) = 0$.

We may then define the multilinear extensions
\begin{equation*}
\begin{align}
\widetilde{\mathrm{add}}_i & : \mathbb{F}^{s_i} \times \mathbb{F}^{s_{i + 1}} \times \mathbb{F}^{s_{i + 1}} \to \mathbb{F} \\
\widetilde{\mathrm{mult}}_i & : \mathbb{F}^{s_i} \times \mathbb{F}^{s_{i + 1}} \times \mathbb{F}^{s_{i + 1}} \to \mathbb{F}
\end{align}
\end{equation*}

```

```{prf:remark}
:label: rem-wiring-convention
(i) The reason we define $\mathrm{add}_i(\mathbf{c}, \mathbf{a}, \mathbf{b})$ to be $0$ unless $\mathbf{a} \le \mathbf{b}$ is precisely so that, if $\mathbf{a} \ne \mathbf{b}$, then at most one of $\mathrm{add}_i(\mathbf{c}, \mathbf{a}, \mathbf{b})$ and $\mathrm{add}_i(\mathbf{c}, \mathbf{b}, \mathbf{a})$ can be $1$. Similarly for $\mathrm{mult}_i$. This avoids double counting in the layer-wise gate-value propagation equation and Thaler's identity [below](#sec-thaler-identity).

(ii) For $A \subseteq \mathbb{F}$, we may of course identify the domain $A^{s_i} \times A^{s_{i + 1}} \times A^{s_{i + 1}}$ with $A^{s_i + 2s_{i + 1}}$, and write $(c_0,\ldots,c_{s_i - 1},a_0,\ldots,a_{s_{i + 1} - 1},b_0,\ldots,b_{s_{i + 1} - 1})$ instead of $((c_0,\ldots,c_{s_i - 1}),(a_0,\ldots,a_{s_{i + 1} - 1}),(b_0,\ldots,b_{s_{i + 1} - 1}))$ for the input of $\mathrm{add}_i$ and $\mathrm{mult}_i$.
```

````{prf:example}
:label: eg-wiring

```{code-cell} python
ac_01.print_wiring_predicates()
```

```{code-cell} python
ac_01.print_wiring_predicate_mles()
```
````

(sec-thaler-identity)=
## Thaler's identity

The structure of an arithmetic circuit is fully described by the wiring predicates $\mathrm{add}_i$ and $\mathrm{mult}_i$, which encode its topology but not the values assigned to the gates by the gate-value functions $W_i$. The circuit's computation can be expressed in terms of the gate-value functions and wiring predicates, as shown in part (a) of the following proposition. Part (b) enables us to apply the sum-check protocol to verify the output of a circuit, as we will explore in the [next notebook](./04-gkr-protocol.md). We refer to this as Thaler's identity, a simplification by Thaler [@tha2015] of an identity of Cormode, Mitzenmacher, and Thaler [@cmt2012].

```{prf:proposition}
:label: prop-thaler-identity
Let $C$ be a constant-input, binary, strictly layered arithmetic circuit of depth $d$ over a field $\mathbb{F}$. For $0 \leq i \leq d$, let Layer $i$ have size $S_i$ and bit length $s_i$, and fix a bit labeling of each layer. For $0 \le i \le d$, let $W_i$ be the gate-value function corresponding to this bit labeling, and for $0 \le i \le d - 1$, let $\mathrm{add}_i$ and $\mathrm{mult}_i$ be the wiring predicates corresponding to this bit labeling.

(a) **[Layer-wise gate-value propagation equation]** Let $i \in \{0,\ldots,d - 1\}$. For all $\mathbf{z} \in \{0,1\}^{s_i}$,

\begin{equation}
\label{eq-propagation}
W_i(\mathbf{z}) = 
\sum_{\substack{\mathbf{x} \, \in \{0,1\}^{s_{i + 1}} \\ \mathbf{y} \, \in \{0,1\}^{s_{i + 1}}}} \Big\{ \mathrm{add}_i(\mathbf{z},\mathbf{x},\mathbf{y}) \big[ W_{i+1}(\mathbf{x}) + W_{i+1}(\mathbf{y})\big]
 + \mathrm{mult}_i(\mathbf{z},\mathbf{x},\mathbf{y}) \big[ W_{i+1}(\mathbf{x})W_{i+1}(\mathbf{y})\big]\Big\}.
\end{equation}

(b) **[Thaler's identity]** Let $i \in \{0,\ldots,d - 1\}$. For all $\mathbf{z} \in \mathbb{F}^{s_i}$,

\begin{equation}
\label{eq-thaler-identity}
\widetilde{W}_i(\mathbf{z}) = \sum_{\substack{\mathbf{x} \, \in \{0,1\}^{s_{i + 1}} \\ \mathbf{y} \, \in \{0,1\}^{s_{i + 1}}}} \Big\{\widetilde{\mathrm{add}}_i(\mathbf{z},\mathbf{x},\mathbf{y}) \big[ \widetilde{W}_{i + 1}(\mathbf{x}) + \widetilde{W}_{i + 1}(\mathbf{y})\big]
 + \widetilde{\mathrm{mult}}_i(\mathbf{z},\mathbf{x},\mathbf{y}) \big[ \widetilde{W}_{i + 1}(\mathbf{x})\widetilde{W}_{i + 1}(\mathbf{y})\big]\Big\}.
\end{equation}
```

```{admonition} Proof
:class: proof
(a) Let $\mathbf{z} \in \{0,1\}^{s_i}$. When the (multi)set of $\mathbf{z}$'s two children is $\{\mathbf{a}, \mathbf{b}\}$ with $\mathbf{a} \le \mathbf{b}$, the only potentially nonzero summand on the right-hand side of [](#eq-propagation) corresponds to $\mathbf{x} = \mathbf{a}$ and $\mathbf{y} = \mathbf{b}$. Furthermore:

- If $\mathbf{z}$ is an addition gate, then $\mathrm{mult}_i(\mathbf{z},\mathbf{a},\mathbf{b}) = 0$, reducing the right-hand side to

\begin{equation*}
\mathrm{add}_i(\mathbf{z},\mathbf{a},\mathbf{b})\big[ W_{i+1}(\mathbf{a}) + W_{i+1}(\mathbf{b})\big] = W_{i+1}(\mathbf{a}) + W_{i+1}(\mathbf{b}) = W_i(\mathbf{z}).
\end{equation*}

- Similarly, if $\mathbf{z}$ is a multiplication gate, then $\mathrm{add}_i(\mathbf{z},\mathbf{a},\mathbf{b}) = 0$, reducing the right-hand side to

\begin{equation*}
\mathrm{mult}_i(\mathbf{z},\mathbf{a},\mathbf{b})\big[ W_{i+1}(\mathbf{a}) W_{i+1}(\mathbf{b})\big] = W_{i+1}(\mathbf{a}) W_{i+1}(\mathbf{b}) = W_i(\mathbf{z}).
\end{equation*}

(b) Still assuming $\mathbf{z} \in \{0,1\}^{s_i}$, since $\mathbf{z}$, $\mathbf{x}$, and $\mathbf{y}$ lie in a Boolean hypercube, each function in the expression [](#eq-propagation) can be replaced by its multilinear extension. Specifically, for $\mathbf{z} \in \{0,1\}^{s_i}$,

\begin{equation*}
W_i(\mathbf{z}) = \widetilde{W}_i(\mathbf{z});
\end{equation*}

for $\mathbf{x}, \mathbf{y} \in \{0,1\}^{s_{i + 1}}$,

\begin{equation*}
W_{i + 1}(\mathbf{x}) = \widetilde{W}_{i + 1}(\mathbf{x}) \quad \text{and} \quad W_{i + 1}(\mathbf{y}) = \widetilde{W}_{i + 1}(\mathbf{y});
\end{equation*}

and for $(\mathbf{z},\mathbf{x}, \mathbf{y}) \in \{0,1\}^{s_i} \times \{0,1\}^{s_{i + 1}} \times \{0,1\}^{s_{i + 1}}$,

\begin{equation*}
\mathrm{add}_i(\mathbf{z},\mathbf{x},\mathbf{y}) = \widetilde{\mathrm{add}}_i(\mathbf{z},\mathbf{x},\mathbf{y}) \quad \text{and} \quad
\mathrm{mult}_i(\mathbf{z},\mathbf{x},\mathbf{y}) = \widetilde{\mathrm{mult}}_i(\mathbf{z},\mathbf{x},\mathbf{y}).
\end{equation*}

Therefore,

\begin{equation*}
\begin{align}
\begin{split} 
& \sum_{\substack{\mathbf{x} \, \in \{0,1\}^{s_{i + 1}} \\ \mathbf{y} \, \in \{0,1\}^{s_{i + 1}}}} \Big\{ \mathrm{add}_i(\mathbf{z},\mathbf{x},\mathbf{y}) \big[ W_{i+1}(\mathbf{x}) + W_{i+1}(\mathbf{y})\big]
 + \mathrm{mult}_i(\mathbf{z},\mathbf{x},\mathbf{y}) \big[ W_{i+1}(\mathbf{x})W_{i+1}(\mathbf{y})\big]\Big\}
  \\ & =
\sum_{\substack{\mathbf{x} \, \in \{0,1\}^{s_{i + 1}} \\ \mathbf{y} \, \in \{0,1\}^{s_{i + 1}}}} \Big\{\widetilde{\mathrm{add}}_i(\mathbf{z},\mathbf{x},\mathbf{y}) \big[ \widetilde{W}_{i + 1}(\mathbf{x}) + \widetilde{W}_{i + 1}(\mathbf{y})\big]
 + \widetilde{\mathrm{mult}}_i(\mathbf{z},\mathbf{x},\mathbf{y}) \big[ \widetilde{W}_{i + 1}(\mathbf{x})\widetilde{W}_{i + 1}(\mathbf{y})\big]\Big\}.
 \end{split}
\end{align}
\end{equation*}

The functions on both sides of [](#eq-thaler-identity) are defined for all $\mathbf{z} \in \mathbb{F}^{s_i}$, and we've just shown they agree for all $\mathbf{z}$ in the Boolean hypercube $\{0,1\}^{s_i}$. We claim that equality in fact holds for all $\mathbf{z}$ in $\mathbb{F}^{s_i}$. Since the left-hand side is a multilinear extension of $W_i$ and the right hand side is an extension of $W_i$, it suffices to show that the right-hand side is _multilinear_ in $\mathbf{z}$. By uniqueness of multilinear extensions, it then follows that both sides of [](#eq-thaler-identity) are the same function on $\mathbb{F}^{s_i}$, viz. the multilinear extension of $W_i$. 

Indeed, given $\mathbf{x}, \mathbf{y} \in \{0,1\}^{s_{i + 1}}$, $\widetilde{\mathrm{add}}_i(\mathbf{z},\mathbf{x},\mathbf{y})$ and $\widetilde{\mathrm{mult}}_i(\mathbf{z},\mathbf{x},\mathbf{y})$ are multilinear functions in $\mathbf{z}$, because they are multilinear extensions of $\mathrm{add}_i$ and $\mathrm{mult}_i$ respectively. Recall the [proposition](./02-multilinear-extensions.md#prop-mle-linear) of our [multilinear extensions notebook](./02-multilinear-extensions.md), which states that the multilinear extension process is linear on function spaces, i.e. $\widetilde{cf + dg} = c\tilde{f} + d\tilde{g}$. This implies that the summand on the right-hand side of [](#eq-thaler-identity) is a multilinear function in $\mathbf{z}$, and therefore, in turn, that the entire sum is a multilinear function in $\mathbf{z}$.
```

```{prf:remark}
:label: rem-thaler-relaxed
(i) We call a function multilinear if it is the evaluation map of some multilinear polynomial. For example, over $\mathbb{Z}/3\mathbb{Z}$, the function $(z_0,z_1,x_0,x_1,y_0,y_1) \mapsto x_0^2y_1z_0^3 + x_1y_0^2z_1^3$ is multilinear in $(z_0,z_1)$, because it is equivalent to the function $(z_0,z_1,x_0,x_1,y_0,y_1) \mapsto x_0^2y_1z_0 + x_1y_0^2z_1$, which is the evaluation map of the polynomial $X_0^2Y_1Z_0 + X_1Y_0^2Z_1$, which is multilinear in $(Z_0,Z_1)$. 

(ii) We did not use the fact that $\widetilde{\mathrm{add}}_i(\mathbf{z},\mathbf{x},\mathbf{y})$ and $\widetilde{\mathrm{mult}}_i(\mathbf{z},\mathbf{x},\mathbf{y})$ are multilinear functions with respect to $\mathbf{x}$ and $\mathbf{y}$ in the above proof. The hypotheses for Thaler's identity can be relaxed: $\widetilde{\mathrm{add}}_i(\mathbf{z},\mathbf{x},\mathbf{y})$ and $\widetilde{\mathrm{mult}}_i(\mathbf{z},\mathbf{x},\mathbf{y})$ can be extensions of $\mathrm{add}_i(\mathbf{z},\mathbf{x},\mathbf{y})$ and $\mathrm{mult}_i(\mathbf{z},\mathbf{x},\mathbf{y})$ that are multilinear in $\mathbf{z}$.
```

```{code-cell} python
ac_01.print_verification_propagation_equation()
```

```{code-cell} python
ac_01.print_verification_propagation_equation(mle=True)
```

(sec-conclusion)=
## Conclusion

Fix $\mathbf{z} \in \mathbb{F}^{s_i}$. We may view the summand on the right-hand side of Thaler's identity [](#eq-thaler-identity) as a function of $\mathbf{x}$ and $\mathbf{y}$, rather than of $\mathbf{z}$. Specifically, for fixed $\mathbf{z}$ it defines a polynomial function

\begin{equation*}
F_{\mathbf{z}} : \mathbb{F}^{s_{i + 1}} \times \mathbb{F}^{s_{i + 1}} \to \mathbb{F},
\end{equation*}

which we may identify with a polynomial function on $\mathbb{F}^{2s_{i+1}}$. 

Moreover, this polynomial function may be represented by a polynomial that is multilinear (and hence of low total degree) in the variables $(\mathbf{x},\mathbf{y})$. Thaler's identity asserts that $\widetilde{W}_i(\mathbf{z})$ is equal to the sum of $F_{\mathbf{z}}$ over the Boolean hypercube $\{0,1\}^{2s_{i + 1}}$. Consequently, for any fixed $\mathbf{z}$, verification of ($2$) is amenable to the sum-check protocol.

(sec-appendix-a)=
## Appendix A: further examples

````{prf:example}
:label: eg-appendix-2

```{code-cell} python
expression_02 = '(2 + 2)*(3*3)'
ac_02 = ArithmeticCircuit(expression_02, prime=7)

print(f"{expression_02} mod {ac_02.field.mod}")
display(ac_02.graphviz_circuit)
print(f"This circuit has size S = {ac_02.size} and depth d = {ac_02.depth}.")
ac_02.print_topological_order()
display(ac_02.graphviz_circuit_bitstring)
ac_02.print_gate_values()
ac_02.print_tilde_W()
ac_02.print_wiring_predicates()
ac_02.print_wiring_predicate_mles()
ac_02.print_verification_propagation_equation()
ac_02.print_verification_propagation_equation(mle=True)
```
````

````{prf:example}
:label: eg-appendix-3

```{code-cell} python
expression_03a = '5*4 + 3'
expression_03b = '5*4 + (3 + 0)'
ac_03a = ArithmeticCircuit(expression_03a, prime=7, strict=False)
ac_03b = ArithmeticCircuit(expression_03b, prime=7)

print(f"{expression_03a} mod {ac_03a.field.mod}")
display(ac_03a.graphviz_circuit)

print(f"- The above is not a strictly layered circuit because the input 3 is not in Layer {ac_03a.depth} (the depth of the circuit).")
print(f"- If an arithmetic circuit can't model such a simple computation, it is rather otiose.")
print(f"- There is a simple workaround: note that {expression_03a} = {expression_03b}.\n")
print(f"{expression_03b} mod {ac_03b.field.mod}")
display(ac_03b.graphviz_circuit)

ac_03b.print_topological_order()
display(ac_03b.graphviz_circuit_bitstring)
ac_03b.print_gate_values()
ac_03b.print_tilde_W()
ac_03b.print_wiring_predicates()
ac_03b.print_wiring_predicate_mles()
ac_03b.print_verification_propagation_equation()
ac_03b.print_verification_propagation_equation(mle=True)
```
````

````{prf:example}
:label: eg-appendix-4

```{code-cell} python
expression_04 = '5*x + (3*4)'
ac_04 = ArithmeticCircuit(expression_04, prime=7, strict=False)

print(f"{expression_04} mod {ac_04.field.mod}")
display(ac_04.graphviz_circuit)

print(f"- The above is not a constant-input circuit because the input x a variable.")
print(f"- Nevertheless, we can still explore the arithmetic circuit.")
ac_04.print_topological_order()
display(ac_04.graphviz_circuit_bitstring)
print(ac_04.layers)
```
````

````{prf:example}
:label: eg-appendix-5

```{code-cell} python
expression_05a = '1*5 + 2*6'
expression_05b = '3*5 + 4*6'
ac_05 = ArithmeticCircuit(expression_05a, expression_05b, prime=43)

print(f"Here is an example of matrix multiplication: [ [1 2] [3 4] ] * [ [5] [6] ] ")

print(f"{expression_05a} mod {ac_05.field.mod}, {expression_05b} mod {ac_05.field.mod}")
display(ac_05.graphviz_circuit)
display(ac_05.graphviz_circuit_bitstring)
ac_05.print_topological_order()
display(ac_05.graphviz_circuit_bitstring)
ac_05.print_gate_values()
ac_05.print_tilde_W()
ac_05.print_wiring_predicates()
ac_05.print_wiring_predicate_mles()
# With prime field of size p = 43, there will be a large number of equations to print, so we just verify for a random selection
ac_05.print_verification_propagation_equation(random_selection=10)
ac_05.print_verification_propagation_equation(mle=True, random_selection=10)
```
````