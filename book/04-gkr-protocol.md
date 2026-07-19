---
title: GKR protocol
kernelspec:
  name: python3
  display_name: Python 3
---

```{code-cell} python
:tags: [remove-cell]
import gkr
env = gkr.init(verbose=False)
```

(sec-introduction)=
## Introduction

Building on our exploration of the [sum-check protocol](./01-sum-check-protocol.md), [multilinear extensions](./02-multilinear-extensions.md), and [arithmetic circuits](./03-arithmetic-circuits.md), we are now ready to present the GKR protocol in full. Originally introduced by Goldwasser, Kalai, and Rothblum [@gkr2008; @gkr2015], and refined by many authors since, GKR is a cornerstone of modern interactive proofs for verifying circuit computations. This notebook assembles the objects and identities from the previous notebooks and shows how they combine into the protocol itself. We follow Thaler's presentation [@tha2022, §4.6].

(sec-worked-example)=
## Worked Example

We proceed via a complete worked example. It serves two purposes: (i) to summarize the key objects (multilinear extensions, wiring predicates, Thaler's identity), and (ii) to illustrate the recurring GKR pattern: **run sum-check on Thaler's identity**, then apply a **folding** step that converts a claim about two values into a single claim at a fresh random point.

No example small enough to compute fully by hand can showcase GKR's asymptotic savings: our toy computation is trivial, while the protocol machinery is comparatively elaborate. The value of the example is conceptual. Later we will discuss complexity and explain why, for large circuits, the verifier's work in GKR is asymptotically far smaller than re-evaluating the circuit.

**Example 1 [setup and arithmetic circuit].** Work over the field $\mathbb{F} = \mathbb{Z}/p\mathbb{Z}$, where $p = 2^{31} - 1$ is the eighth Mersenne prime. Consider the $4$-variate polynomial
\begin{equation*}
P \in \mathbb{F}[X_0,X_1,X_2,X_3], \quad P(X_0,X_1,X_2,X_3) := X_0X_1 + X_2 + X_3.
\end{equation*}
For instance,
\begin{equation*}
P(3,2,4,1) \equiv (3\cdot 2) + (4 + 1) \equiv 11 \bmod p.
\end{equation*}

We represent this computation by a **constant-input, binary, strictly layered** arithmetic circuit $C$ of size $7$ and depth $d = 2$:

- Layer 2 (inputs): the four inputs $3,2,4,1$;
- Layer 1: one multiplication gate and one addition gate, computing $3\cdot 2 \equiv 6$ and $4 + 1 \equiv 5$;
- Layer 0 (output): one addition gate computing $6 + 5 \equiv 11$.

In this example, Layer i has size $S_i = 2^i$, hence bit-length $s_i = \lceil \log_2 S_i\rceil = i$ for $i \in \{0,1,2\}$. (For general circuits, $s_i$ need not equal $i$.)

We label the gates in Layer i using bitstrings of length $s_i$ as follows:

- Layer 2 (inputs): $3 \mapsto (0,0), \; 2 \mapsto (0,1), \; 4 \mapsto (1,0), \; 1 \mapsto (1,1)$.
- Layer 1: $\times \mapsto 0, \; + \mapsto 1$.
- Layer 0 (output): $+ \mapsto \emptyset$ (the empty bitstring, also written $()$).

```{code-cell} python
from gkr.ac import ArithmeticCircuit

expression_01 = '(3*2) + (4 + 1)'
gkr_01 = ArithmeticCircuit(expression_01, prime=2**31 - 1)
display(gkr_01.graphviz_circuit_bitstring)
```

**Gate-value functions.** For each layer $i \in \{0,\ldots,d\}$, the **gate-value function**
\begin{equation*}
W_i : \{0,1\}^{s_i} \to \mathbb{F}
\end{equation*}
records the value at each gate. By multilinear interpolation on the Boolean hypercube, each $W_i$ has a unique **multilinear extension**
\begin{equation*}
\widetilde{W}_i : \mathbb{F}^{s_i} \to \mathbb{F}.
\end{equation*}

**Example 1 [gate-value functions].** In our example,
\begin{equation*}
\begin{align}
W_2(0,0) &= 3, & W_2(0,1) &= 2, & W_2(1,0) &= 4, & W_2(1,1) &= 1,\\
W_1(0) &= 6, & W_1(1) &= 5,\\
W_0(\emptyset) &= 11.
\end{align}
\end{equation*}
These admit the multilinear extensions (computed explicitly below)
\begin{equation*}
\widetilde{W}_2(v_0,v_1) = -2v_0v_1 + v_0 - v_1 + 3,\qquad
\widetilde{W}_1(v) = 6 - v,\qquad
\widetilde{W}_0(\emptyset) = 11.
\end{equation*}
For instance,
\begin{equation*}
\widetilde{W}_2(1,1) = -2(1\cdot 1) + 1 - 1 + 3 \equiv 1 \bmod p,
\end{equation*}
matching $W_2(1,1)$.

**Wiring predicates.** For $i \in \{0,\ldots,d-1\}$, define wiring predicates
\begin{equation*}
\mathrm{add}_i,\,\mathrm{mult}_i : \{0,1\}^{s_i} \times \{0,1\}^{s_{i+1}} \times \{0,1\}^{s_{i+1}} \to \{0,1\},
\end{equation*}
encoding the circuit topology. Concretely, $\mathrm{add}_i(\mathbf{c},\mathbf{a},\mathbf{b}) = 1$ iff $\mathbf{c}$ is an addition gate whose two children are $\mathbf{a}$ and $\mathbf{b}$, and $\mathbf{a} \le \mathbf{b}$ (lexicographic order). Similarly for $\mathrm{mult}_i$. Each wiring predicate has a unique multilinear extension
\begin{equation*}
\widetilde{\mathrm{add}}_i,\,\widetilde{\mathrm{mult}}_i : \mathbb{F}^{s_i} \times \mathbb{F}^{s_{i+1}} \times \mathbb{F}^{s_{i+1}} \to \mathbb{F}.
\end{equation*}

**Example 1 [wiring predicates].** In our circuit,
\begin{equation*}
\mathrm{add}_0(\emptyset,0,1) = 1,\quad
\mathrm{mult}_1(0,(0,0),(0,1)) = 1,\quad
\mathrm{add}_1(1,(1,0),(1,1)) = 1,
\end{equation*}
and all other values are zero. The multilinear extensions are:
\begin{equation*}
\begin{align}
\widetilde{\mathrm{add}}_0(\emptyset,x,y) &= (1-x)y,\\
\widetilde{\mathrm{mult}}_0(\emptyset,x,y) &= 0,\\
\widetilde{\mathrm{add}}_1(z,(x_0,x_1),(y_0,y_1)) &= zx_0(1-x_1)y_0y_1,\\
\widetilde{\mathrm{mult}}_1(z,(x_0,x_1),(y_0,y_1)) &= (1-z)(1-x_0)(1-x_1)(1-y_0)y_1.
\end{align}
\end{equation*}

**Gate propagation and Thaler's identity.** The circuit semantics are captured by the **layer-wise gate propagation equation**: for $i \in \{0,\ldots,d-1\}$ and $\mathbf{z}\in\{0,1\}^{s_i}$,
\begin{equation}
\label{eq-gkr-01}
W_i(\mathbf{z}) =
\sum_{\substack{\mathbf{x}\in\{0,1\}^{s_{i+1}}\\ \mathbf{y}\in\{0,1\}^{s_{i+1}}}}
\Big\{
\mathrm{add}_i(\mathbf{z},\mathbf{x},\mathbf{y})\big[W_{i+1}(\mathbf{x})+W_{i+1}(\mathbf{y})\big]
+
\mathrm{mult}_i(\mathbf{z},\mathbf{x},\mathbf{y})\big[W_{i+1}(\mathbf{x})W_{i+1}(\mathbf{y})\big]
\Big\}.
\end{equation}
Thaler's identity is the multilinear-extension analogue: for $i \in \{0,\ldots,d-1\}$ and $\mathbf{z}\in\mathbb{F}^{s_i}$,
\begin{equation}
\label{eq-gkr-02}
\widetilde{W}_i(\mathbf{z}) =
\sum_{\substack{\mathbf{x}\in\{0,1\}^{s_{i+1}}\\ \mathbf{y}\in\{0,1\}^{s_{i+1}}}}
\Big\{
\widetilde{\mathrm{add}}_i(\mathbf{z},\mathbf{x},\mathbf{y})\big[\widetilde{W}_{i+1}(\mathbf{x})+\widetilde{W}_{i+1}(\mathbf{y})\big]
+
\widetilde{\mathrm{mult}}_i(\mathbf{z},\mathbf{x},\mathbf{y})\big[\widetilde{W}_{i+1}(\mathbf{x})\widetilde{W}_{i+1}(\mathbf{y})\big]
\Big\}.
\end{equation}

**Example 1 [layer-wise gate propagation and Thaler's identity].** In our example, [](#eq-gkr-02) expands to
\begin{equation}
\label{eq-gkr-03}
11 = \sum_{x\in\{0,1\}} \sum_{y\in\{0,1\}} (1-x)y\big[(6-x)+(6-y)\big].
\end{equation}
and
\begin{align}
\label{eq-gkr-04}
6 - z
&= \sum_{x_0\in\{0,1\}}\sum_{x_1\in\{0,1\}}\sum_{y_0\in\{0,1\}}\sum_{y_1\in\{0,1\}}
\Big\{
zx_0(1-x_1)y_0y_1\big[(-2x_0x_1+x_0-x_1+3)+(-2y_0y_1+y_0-y_1+3)\big] \notag \\
&\qquad\qquad\qquad\qquad\qquad\qquad\qquad\qquad
+ \; (1-z)(1-x_0)(1-x_1)(1-y_0)y_1\big[(-2x_0x_1+x_0-x_1+3)(-2y_0y_1+y_0-y_1+3)\big]
\Big\}.
\end{align}

**What is being verified?** The circuit $C$ (including its wiring predicates) is public. The prover's private information is the collection of intermediate gate values, equivalently the functions $W_i$. In the single-output setting, the prover's top-level claim is simply that the output gate evaluates to a particular field element (here, $11$).

More generally, Layer 0 may contain **multiple output gates**. We label the $S_0$ outputs by $\{0,1\}^{s_0}$, and the function
\begin{equation*}
W_0 : \{0,1\}^{s_0}\to\mathbb{F}
\end{equation*}
encodes all outputs at once. The prover's claim is that the true output function $W_0$ equals a purported function $W_0^*$ (equivalently, $\widetilde{W}_0=\widetilde{W}_0^*$ as polynomial functions).

The verifier does not check equality at all points. Instead, they sample a uniformly random $\rho_0\in\mathbb{F}^{s_0}$ and check equality at that point:
\begin{equation*}
\widetilde{W}_0(\rho_0) = \widetilde{W}_0^*(\rho_0).
\end{equation*}
If $\widetilde{W}_0\neq \widetilde{W}_0^*$, then $\widetilde{W}_0-\widetilde{W}_0^*$ is a nonzero multilinear polynomial function (degree $\le s_0$), so by Schwartz-Zippel,
\begin{equation*}
\Pr\big[\widetilde{W}_0(\rho_0)=\widetilde{W}_0^*(\rho_0)\big]
= \Pr\big[(\widetilde{W}_0-\widetilde{W}_0^*)(\rho_0)=0\big]
\le \frac{s_0}{\#\mathbb{F}}.
\end{equation*}
Thus, a match at a random point gives strong evidence that all output gates are correct.

**From Thaler's identity to GKR.** Fix a layer $i$. The verifier does not try to check [](#eq-gkr-02) for all $\mathbf{z}\in\mathbb{F}^{s_i}$. Instead, they sample a random point $\rho_i\in\mathbb{F}^{s_i}$ and ask the prover to justify [](#eq-gkr-02) at $\mathbf{z}=\rho_i$.

Once $\rho_i$ is fixed, the right-hand side of [](#eq-gkr-02) becomes a polynomial function in the $2s_{i+1}$ Boolean variables $(\mathbf{x},\mathbf{y})$. The prover and verifier then run sum-check over these variables. At the end of sum-check, the verifier is left with a small number of claimed values of $\widetilde{W}_{i+1}$; the folding step compresses these into a **single** new claim about $\widetilde{W}_{i+1}$ at a fresh random point $\rho_{i+1}$.

As in the sum-check notebook, we distinguish circuit-determined objects from prover-asserted objects. We use $(\cdot)^*$ (e.g. $\widetilde{W}_i^*$) for prover claims, which may be false. For clarity, we sometimes use the notation $\;\overset{?}{=}\;$ for an equality that may not hold if P is dishonest. Unadorned symbols refer to the true objects induced by the circuit. For readability, we reuse symbols like the verifier challenges $r_j$ and the prover's round polynomials $g_j$ across different sum-check invocations; they are "reset" each time a new sum-check begins.

**GKR Layer 0.** The parties are the **verifier** V and the **prover** P. V samples $\rho_0 \leftarrow \mathbb{F}^{s_0}$. Define
\begin{equation}
\label{eq-gkr-05}
g(\mathbf{x},\mathbf{y}) :=
\widetilde{\mathrm{add}}_0(\rho_0,\mathbf{x},\mathbf{y})\big[\widetilde{W}_{1}(\mathbf{x})+\widetilde{W}_{1}(\mathbf{y})\big]
+
\widetilde{\mathrm{mult}}_0(\rho_0,\mathbf{x},\mathbf{y})\big[\widetilde{W}_{1}(\mathbf{x})\widetilde{W}_{1}(\mathbf{y})\big],
\end{equation}
the summand in [](#eq-gkr-02) when $i=0$ and $\mathbf{z}=\rho_0$. Thus,
\begin{equation}
\label{eq-gkr-06}
\widetilde{W}_0(\rho_0)
=
\sum_{(\mathbf{x},\mathbf{y})\in \{0,1\}^{s_1}\times \{0,1\}^{s_1}}
g(\mathbf{x},\mathbf{y}).
\end{equation}
Moreover $\deg g \le 4s_1$: the wiring polynomials have degree $\le 2s_1$, the multilinear extensions $\widetilde{W}_1(\mathbf{x})$ and $\widetilde{W}_1(\mathbf{y})$ have degree $\le s_1$, and the worst case comes from the product term. (In general Layer $i$, the same reasoning gives $\deg g \le 4s_{i+1}$.)

The protocol runs sum-check on [](#eq-gkr-06) (with the prover's possibly false claim for $\widetilde{W}_0(\rho_0)$ on the left-hand side), with one crucial twist at the final step: instead of having V evaluate $g(r_x,r_y)$ directly, GKR uses claimed values of $\widetilde{W}_1$ and then folds them into a single new claim.

**Example 1 [GKR Layer 0].** Here $s_0=0$, so $\mathbb{F}^{s_0}=\{\emptyset\}$ and $\rho_0=\emptyset$. Also $s_1=1$, and from [](#eq-gkr-03) we set
\begin{equation*}
g(x,y) := (1-x)y\big[(6-x)+(6-y)\big].
\end{equation*}

To see how cheating is forced to "thread the needle", suppose P falsely claims that $\widetilde{W}_0(\rho_0)$ equals $10$ (the truth is $11$). The sum-check claim is
\begin{equation*}
\widetilde{W}_0^*(\rho_0) \overset{?}{=} \sum_{x,y\in\{0,1\}} g(x,y),
\end{equation*}
which is true iff the left-hand side equals $11$. Since P insists on $\widetilde{W}_0^*(\rho_0) = 10$, they must lie consistently, and later they will still need luck to avoid detection.

**Sum-check Round 0.0.** Define
\begin{equation*}
g_0(u_0) := \sum_{y\in\{0,1\}} g(u_0,y) = g(u_0,0)+g(u_0,1),
\end{equation*}
so that, as $\widetilde{W}_0$ and $g_0$ are ground-truth polynomial functions, $\widetilde{W}_0(\rho_0)=g_0(0)+g_0(1)$. P sends $g_0^*$, and V checks:
1. $\deg g_0^* \le 4s_1 = 4$,
2. $\widetilde{W}_0^*(\rho_0)=g_0^*(0)+g_0^*(1)$.

If both pass, V samples $r_0\leftarrow\mathbb{F}$ and sends it to P.

In truth, $g_0(u_0)=(1-u_0)(11-u_0)$, but V does not know this. To satisfy the checks while forcing $g_0^*(0)+g_0^*(1)=10$, P can pick (for example)
\begin{equation*}
g_0^*(u_0) := 2u_0(u_0-7)+11,
\end{equation*}
since
\begin{equation*}
g_0^*(0)+g_0^*(1) = 11 + \big(2(-6)+11\big)=10=\widetilde{W}_0^*(\emptyset).
\end{equation*}
Suppose V chooses $r_0=17$.

**Sum-check Round 0.1.** Define $g_1(u_1):=g(r_0,u_1)$, so $g_0(r_0)=g_1(0)+g_1(1)$. P sends $g_1^*$, and V checks:
1. $\deg g_1^* \le 4$,
2. $g_0^*(r_0)=g_1^*(0)+g_1^*(1)$.

If both pass, V samples $r_1\leftarrow\mathbb{F}$ and sends it to P.

Since $r_0=17$, the truth is
\begin{equation*}
g_1(u_1)=g(17,u_1)=(1-17)u_1\big[6-17+6-u_1\big]=16u_1(5+u_1),
\end{equation*}
but P can instead claim
\begin{equation*}
g_1^*(u_1):=u_1(17u_1+334),
\end{equation*}
which satisfies
\begin{equation*}
g_1^*(0)+g_1^*(1)=351=2\cdot 17(17-7)+11=g_0^*(17).
\end{equation*}
Suppose V chooses $r_1=42$.

**Sum-check final check (where GKR diverges).** In standalone sum-check, V would check $g_1^*(r_1)\overset{?}{=}g(r_0,r_1)$, but in GKR V does not directly evaluate $g(r_0,r_1)$.

Instead, define
\begin{equation*}
z_0 := \widetilde{W}_1(r_0),\qquad z_1 := \widetilde{W}_1(r_1),
\end{equation*}
and P supplies claimed values $z_0^*,z_1^*$ asserted to equal $z_0,z_1$.

In our example, the ground truth is
\begin{equation*}
z_0 = \widetilde{W}_1(17)=6-17=-11,\qquad
z_1 = \widetilde{W}_1(42)=6-42=-36,
\end{equation*}
and also
\begin{equation*}
g(r_0,r_1)=g(17,42)=16\cdot 42(5+42)=1974,
\end{equation*}
whereas
\begin{equation*}
g_1^*(r_1)=g_1^*(42)=42(17\cdot 42+334)=44016,
\end{equation*}
so standalone sum-check would reject. GKR postpones this evaluation and moves to folding.

At this point, V has reduced a claim about $\widetilde{W}_0$ to two claimed values of $\widetilde{W}_1$. Recursing naïvely would cause a blow-up. Folding avoids this by compressing two claims into one.

**GKR folding at Layer 0.** At the end of the Layer 0 sum-check, V is left to verify
\begin{equation}
\label{eq-gkr-07}
g_{2s_1-1}^*(r_{2s_1-1}) \overset{?}{=} g(r_x,r_y),
\end{equation}
where
\begin{equation*}
r_x=(r_0,\ldots,r_{s_1-1})\in\mathbb{F}^{s_1},\qquad
r_y=(r_{s_1},\ldots,r_{2s_1-1})\in\mathbb{F}^{s_1}
\end{equation*}
are the verifier challenge vectors from the $2s_1$ rounds. P supplies claimed values
\begin{equation}
\label{eq-gkr-08}
\widetilde{W}_1(r_x)\overset{\mathsf{P}}{\underset{\text{claim}}{=}}z_0^*,\qquad \widetilde{W}_1(r_y)\overset{\mathsf{P}}{\underset{\text{claim}}{=}}z_1^*.
\end{equation}
Together, [](#eq-gkr-05), [](#eq-gkr-07), and [](#eq-gkr-08) amount to the "bridging" equation
\begin{equation}
\label{eq-gkr-09}
g_{2s_1-1}^*(r_{2s_1-1})
\overset{?}{=}
\widetilde{\mathrm{add}}_0(\rho_0,r_x,r_y)\big[z_0^*+z_1^*\big]
+
\widetilde{\mathrm{mult}}_0(\rho_0,r_x,r_y)\big[z_0^*z_1^*\big].
\end{equation}
Since the circuit is public, V can evaluate $\widetilde{\mathrm{add}}_0$ and $\widetilde{\mathrm{mult}}_0$ at any point, so V checks [](#eq-gkr-09) and rejects if it fails.

Now fold the two claims in [](#eq-gkr-08) into a single claim. Define the affine line $\ell:\mathbb{F}\to\mathbb{F}^{s_1}$ by
\begin{equation}
\label{eq-gkr-10}
\ell(t):=(1-t)r_x + t r_y,
\end{equation}
and define the associated univariate polynomial function $q_1 : \mathbb{F} \to \mathbb{F}$ by
\begin{equation}
\label{eq-gkr-11}
q_1(t):=\widetilde{W}_1(\ell(t)).
\end{equation}
By construction, $q_1(0)=\widetilde{W}_1(r_x)$ and $q_1(1)=\widetilde{W}_1(r_y)$.

P sends a univariate polynomial function $q_1^*$, purported to equal $q_1$. V checks:
1. $\deg q_1^* \le s_1$,
2. $q_1^*(0)=z_0^*$ and $q_1^*(1)=z_1^*$.

If these checks pass, V samples $\tau_1\leftarrow\mathbb{F}$ and sets
\begin{equation}
\label{eq-gkr-12}
\rho_1 := \ell(\tau_1)\in\mathbb{F}^{s_1}.
\end{equation}
In an honest execution, $q^*_1$ is the true $q_1$, and hence $q_1^*(\tau_1)$ is equal to $\widetilde{W}_1(\rho_1)$. Thus the two claims in [](#eq-gkr-08) have been reduced to a single claim about $\widetilde{W}_1$ at the random point $\rho_1$. The protocol then proceeds to Layer $1$.

**Example 1 [GKR folding at Layer 0].** In this example, $r_x=r_0$ and $r_y=r_1$. P supplies $z_0^*,z_1^*$, and V checks
\begin{equation}
\label{eq-gkr-13}
g_1^*(r_1) \overset{?}{=} (1-r_0)r_1\big[z_0^*+z_1^*\big].
\end{equation}
Define $\ell$ as in [](#eq-gkr-10) and $q_1$ as in [](#eq-gkr-11). Here $\ell(t)=(1-t)r_0+tr_1$ and $q_1(t)=\widetilde{W}_1(\ell(t))=6-\ell(t)$. P sends $q_1^*$ and V checks the endpoint constraints (and $\deg q_1^*\le 1$). Then V samples $\tau_1\leftarrow\mathbb{F}$ and defines $\rho_1=\ell(\tau_1)$ as in [](#eq-gkr-12). In an honest execution, $q_1^*(\tau_1)$ equals $\widetilde{W}_1(\rho_1)$, and by Thaler's identity this equals
\begin{align}
\label{eq-gkr-14}
q_1^*(\tau_1)
&\overset{?}{=}
\sum_{x_0\in\{0,1\}}\sum_{x_1\in\{0,1\}}\sum_{y_0\in\{0,1\}}\sum_{y_1\in\{0,1\}}
\Big\{
\rho_1 x_0(1-x_1)y_0y_1\big[(-2x_0x_1+x_0-x_1+3)+(-2y_0y_1+y_0-y_1+3)\big] \notag \\
&\qquad\qquad\qquad\qquad\qquad\qquad\qquad\qquad
+ \; (1-\rho_1)(1-x_0)(1-x_1)(1-y_0)y_1\big[(-2x_0x_1+x_0-x_1+3)(-2y_0y_1+y_0-y_1+3)\big]
\Big\}.
\end{align}

With the concrete values above, $(r_0,r_1)=(17,42)$ and $g_1^*(r_1)=44016$. To satisfy [](#eq-gkr-13), P must choose $z_0^*,z_1^*$ with
\begin{equation*}
z_0^*z_1^* \equiv g_1^*(r_1)\big[(1-r_0)r_1\big]^{-1}\bmod p.
\end{equation*}
Since $\big[(1-17)\cdot 42\big]^{-1}\equiv 405848844\bmod p$, one possible choice is
\begin{equation*}
z_0^* = 255440969,\qquad z_1^* = 150407875.
\end{equation*}
Then P can define $q_1^*(t):=(1-t)z_0^*+t z_1^*$, which automatically satisfies the endpoint checks.

Suppose V chooses $\tau_1=3$. Then $\rho_1=\ell(3)=92$, and the truth is $q_1(3)=\widetilde{W}_1(92)=6-92=-86$, whereas
\begin{equation*}
q_1^*(3)=255440969-105033094\cdot 3 \equiv 2087825334 \bmod p.
\end{equation*}
Thus in the next sum-check (Layer $1$), P is forced to justify the false claim
\begin{align}
\label{eq-gkr-15}
2087825334
&\overset{?}{=}
\sum_{x_0\in\{0,1\}}\sum_{x_1\in\{0,1\}}\sum_{y_0\in\{0,1\}}\sum_{y_1\in\{0,1\}}
\Big\{
92 x_0(1-x_1)y_0y_1\big[(-2x_0x_1+x_0-x_1+3)+(-2y_0y_1+y_0-y_1+3)\big] \notag \\
&\qquad\qquad\qquad\qquad\qquad\qquad\qquad\qquad
+ \; (1-92)(1-x_0)(1-x_1)(1-y_0)y_1\big[(-2x_0x_1+x_0-x_1+3)(-2y_0y_1+y_0-y_1+3)\big]
\Big\}.
\end{align}
The true value of the right-hand side is $2147483561$. V does not know this, but after the Layer 1 sum-check the inconsistency is detected with high probability.

**GKR Layer i ($1 \le i \le d-2$).** At the start of Layer $i$, V holds a point $\rho_i\in\mathbb{F}^{s_i}$ and a claimed value $q_i^*(\tau_i)\in\mathbb{F}$, which (if P is honest) equals $\widetilde{W}_i(\rho_i)$. V and P run sum-check to justify Thaler's identity at $\mathbf{z}=\rho_i$.

Define
\begin{equation*}
g(\mathbf{x},\mathbf{y}) :=
\widetilde{\mathrm{add}}_i(\rho_i,\mathbf{x},\mathbf{y})\big[\widetilde{W}_{i+1}(\mathbf{x})+\widetilde{W}_{i+1}(\mathbf{y})\big]
+
\widetilde{\mathrm{mult}}_i(\rho_i,\mathbf{x},\mathbf{y})\big[\widetilde{W}_{i+1}(\mathbf{x})\widetilde{W}_{i+1}(\mathbf{y})\big],
\end{equation*}
a polynomial function on $\mathbb{F}^{s_{i+1}}\times\mathbb{F}^{s_{i+1}}$. Sum-check is applied to
\begin{equation*}
q_i^*(\tau_i)
\overset{?}{=}
\sum_{\substack{\mathbf{x}\in\{0,1\}^{s_{i+1}}\\ \mathbf{y}\in\{0,1\}^{s_{i+1}}}}
g(\mathbf{x},\mathbf{y}).
\end{equation*}

Let $m:=2s_{i+1}$, and identify $(\mathbf{x},\mathbf{y})$ with $v=(v_0,\ldots,v_{m-1})\in\mathbb{F}^m$, where $\mathbf{x}=(v_0,\ldots,v_{s_{i+1}-1})$ and $\mathbf{y}=(v_{s_{i+1}},\ldots,v_{m-1})$. The sum-check routine has $m$ rounds, with verifier challenges $r=(r_0,\ldots,r_{m-1})\in\mathbb{F}^m$. Write $r_x=(r_0,\ldots,r_{s_{i+1}-1})\in\mathbb{F}^{s_{i+1}}$ and $r_y=(r_{s_{i+1}},\ldots,r_{m-1})\in\mathbb{F}^{s_{i+1}}$. As usual, the prover sends round polynomials $g_j^*$, and the verifier checks the degree bound and consistency equations. After the final challenge $r_{m-1}$, sum-check reduces consistency to $g_{m-1}^*(r_{m-1}) = g(r_0,\ldots,r_{m-1}) = g(r_x,r_y)$.

Expanding $g(r_x,r_y)$ yields
\begin{equation*}
g(r_x,r_y)
=
\widetilde{\mathrm{add}}_i(\rho_i,r_x,r_y)\big[z_x+z_y\big]
+
\widetilde{\mathrm{mult}}_i(\rho_i,r_x,r_y)\big[z_x z_y\big],
\end{equation*}
where $z_x:=\widetilde{W}_{i+1}(r_x)$ and $z_y:=\widetilde{W}_{i+1}(r_y)$.

**GKR folding at Layer i.** P supplies claimed values $z_x^*,z_y^*\in\mathbb{F}$. V checks the bridging equation
\begin{equation*}
g_{m-1}^*(r_{m-1})
\overset{?}{=}
\widetilde{\mathrm{add}}_i(\rho_i,r_x,r_y)\big[z_x^*+z_y^*\big]
+
\widetilde{\mathrm{mult}}_i(\rho_i,r_x,r_y)\big[z_x^* z_y^*\big],
\end{equation*}
rejecting if it fails. To fold the two claims into one, define
\begin{equation}
\label{eq-gkr-16}
\ell(t):=(1-t)r_x + t r_y,
\end{equation}
and
\begin{equation}
\label{eq-gkr-17}
q_{i+1}(t):=\widetilde{W}_{i+1}(\ell(t)).
\end{equation}
Then $q_{i+1}(0)=\widetilde{W}_{i+1}(r_x)$ and $q_{i+1}(1)=\widetilde{W}_{i+1}(r_y)$. P sends $q_{i+1}^*$, and V checks:
1. $\deg q_{i+1}^* \le s_{i+1}$,
2. $q_{i+1}^*(0)=z_x^*$ and $q_{i+1}^*(1)=z_y^*$.

If these pass, V samples $\tau_{i+1}\leftarrow\mathbb{F}$ and defines
\begin{equation}
\label{eq-gkr-18}
\rho_{i+1}:=\ell(\tau_{i+1})\in\mathbb{F}^{s_{i+1}}.
\end{equation}
In an honest execution, $q_{i+1}^*(\tau_{i+1})$ equals $\widetilde{W}_{i+1}(\rho_{i+1})$. The protocol proceeds to the next layer until reaching $d-1$.

**GKR Layer d - 1 (final layer).** Layer $d-1$ is handled differently because its child gates lie in the **input layer** $d$. Here the recursion bottoms out: $\widetilde{W}_d$ is fully determined by the public inputs, so the verifier can evaluate $\widetilde{W}_d$ directly.

As before, at the start of Layer d - 1, V holds $\rho_{d-1}\in\mathbb{F}^{s_{d-1}}$ and a claimed value $q_{d-1}^*(\tau_{d-1})$ (honestly $\widetilde{W}_{d-1}(\rho_{d-1})$). The parties run sum-check on Thaler's identity at layer $d-1$, producing challenge vectors $r_x,r_y\in\mathbb{F}^{s_d}$ and reducing to a final check of the form $g_{2s_d-1}^*(r_{2s_d-1}) \overset{?}{=} g(r_x,r_y)$. Unlike earlier layers, V now computes $z_x=\widetilde{W}_d(r_x)$ and $z_y=\widetilde{W}_d(r_y)$ directly from the public inputs, and checks the corresponding bridging equation. If it holds, V accepts; otherwise V rejects.

This completes the description of the GKR protocol.

**Example 1 [GKR Layer d - 1].** In our example $d=2$, so the final nontrivial layer is $d-1=1$. The input layer has size $S_2=4$ and hence $s_2=2$. At the end of Layer $0$, V holds $\rho_1\in\mathbb{F}^{s_1}=\mathbb{F}$ and a claimed value $q_1^*(\tau_1)$, which (if P is honest) equals $\widetilde{W}_1(\rho_1)$. Sum-check at Layer $1$ runs for $2s_2=4$ rounds. At the end, V needs to check $g_3^*(r_3)\overset{?}{=}g(r_0,r_1,r_2,r_3)$. Crucially, since this is the input layer, V can evaluate $\widetilde{W}_2$ directly:
\begin{equation*}
\widetilde{W}_2(r_0,r_1)=-2r_0r_1+r_0-r_1+3,\qquad
\widetilde{W}_2(r_2,r_3)=-2r_2r_3+r_2-r_3+3,
\end{equation*}
and therefore V can compute the right-hand side $g(r_0,r_1,r_2,r_3)$ explicitly and reject if it disagrees with $g_3^*(r_3)$.

**Sum-check for Layer 1.** Here $s_2 = 2$, so the sum-check protocol runs for $2s_2 = 4$ rounds. Recall that the layer-1 claim being justified is the (possibly false) value $q_1^*(\tau_1)$, which in an honest execution equals $\widetilde{W}_1(\rho_1)$; see the setup in the preceding discussion (in particular, the explicit identity in [](#eq-gkr-14) above).

**Sum-check Round 1.0.** Define
\begin{equation*}
g_0(u_0)
:=
\sum_{x_1 \, \in \, \{0,1\}}
\sum_{y_0 \, \in \, \{0,1\}}
\sum_{y_1 \, \in \, \{0,1\}}
g(u_0,x_1,y_0,y_1).
\end{equation*}
For the true $g_0$ and $g$, we have $g_0(0)+g_0(1)=\sum g(\cdot)$, so the sum-check *consistency condition* for the prover's first message is
\begin{equation*}
q_1^*(\tau_1) \overset{?}{=} g_0^*(0) + g_0^*(1).
\end{equation*}

The prover P sends a polynomial $g_0^*$, claiming it is the same as $g_0$. V checks:
1. $\deg g_0^* \le 4s_2 = 8$,
2. $q_1^*(\tau_1) = g_0^*(0) + g_0^*(1)$.

If either check fails, V rejects. Otherwise, V samples
\begin{equation*}
r_0 \leftarrow \mathbb{F}
\end{equation*}
and sends it to P.

With our specific values ($\rho_1 = 92$), the true polynomial is
\begin{equation*}
g_0(u_0) = 274u_0^2 + 732u_0 + 2147483101.
\end{equation*}
However, since P is pursuing the false claim from earlier, P must send some different polynomial $g_0^*$ that still passes the two checks above. Suppose P chooses
\begin{equation*}
g^*_0(u_0) = 275u_0^2 + 2087826151u_0 + 2147483101.
\end{equation*}
Then the degree bound holds, and in $\mathbb{Z}/p\mathbb{Z}$ we have
\begin{equation*}
g^*_0(0) + g^*_0(1)
= 2147483101 + (275 + 2087826151 + 2147483101)
= 2087825334
= q_1^*(\tau_1).
\end{equation*}
So far, P's messages are consistent and V does not reject. Suppose V's random challenge is
\begin{equation*}
r_0 = 99.
\end{equation*}

**Sum-check Round 1.1.** Define
\begin{equation*}
g_1(u_1)
:=
\sum_{y_0 \, \in \, \{0,1\}}
\sum_{y_1 \, \in \, \{0,1\}}
g(r_0,u_1,y_0,y_1),
\end{equation*}
so that, as these are the true polynomials,
\begin{equation*}
g_0(r_0) = g_1(0) + g_1(1).
\end{equation*}

P sends $g_1^*$ (claiming it is the same as $g_1$). V checks:
1. $\deg g_1^* \le 8$,
2. $g_0^*(r_0) = g_1^*(0) + g_1^*(1)$.

If the checks pass, V samples
\begin{equation*}
r_1 \leftarrow \mathbb{F}
\end{equation*}
and sends it to P.

With our specific values ($r_0 = 99$), the true polynomial is
\begin{equation*}
g_1(u_1) = 5361856u_1^2 + 2139364395u_1 + 2757396.
\end{equation*}
Suppose P instead claims
\begin{equation*}
g^*_1(u_1) = 5361857u_1^2 + 528176917u_1 + 2757396.
\end{equation*}
V verifies the degree bound and the consistency equation by checking (in $\mathbb{Z}/p\mathbb{Z}$)
\begin{equation*}
\begin{align}
g^*_0(99) & = 275(99^2) + 2087826151(99) + 2147483101 = 539053566,\\
g^*_1(0) + g^*_1(1) & = 2757396 + (5361856 + 2139364395 + 2757396) = 539053566.
\end{align}
\end{equation*}
Thus the transcript remains consistent so far. Suppose V's next random challenge is
\begin{equation*}
r_1 = 7.
\end{equation*}

**Sum-check Round 1.2.** Define
\begin{equation*}
g_2(u_2)
:=
\sum_{y_1 \, \in \, \{0,1\}}
g(r_0,r_1,u_2,y_1),
\end{equation*}
so that, as these are the true polynomials,
\begin{equation*}
g_1(r_1) = g_2(0) + g_2(1).
\end{equation*}

P sends $g_2^*$ (claiming it is the same as $g_2$). V checks:
1. $\deg g_2^* \le 8$,
2. $g_1^*(r_1) = g_2^*(0) + g_2^*(1)$.

If successful, V samples
\begin{equation*}
r_2 \leftarrow \mathbb{F}
\end{equation*}
and sends it to P.

With our specific values $(r_0,r_1)=(99,7)$, the true polynomial is
\begin{equation*}
g_2(u_2) = 69133476u_2^2 + 2010688435u_2 + 138157656.
\end{equation*}
Suppose P instead claims this is
\begin{equation*}
g^*_2(u_2) = 69133477u_2^2 + 1469794372u_2 + 138157656.
\end{equation*}
V verifies the degree bound and the consistency equation by checking (in $\mathbb{Z}/p\mathbb{Z}$)
\begin{equation*}
\begin{align}
g^*_1(7) & = 5361856(7)^2 + 2139364395(7) + 2757396 = 1815243161,\\
g^*_2(0) + g^*_2(1) & = 138157656 + (69133477 + 1469794372 + 138157656) = 1815243161.
\end{align}
\end{equation*}
So V still does not reject. Suppose V's next random challenge is
\begin{equation*}
r_2 = 1001.
\end{equation*}

**Sum-check Round 1.3.** Define
\begin{equation*}
g_3(u_3) := g(r_0,r_1,r_2,u_3),
\end{equation*}
so that, as these are the true polynomials, 
\begin{equation*}
g_2(r_2) = g_3(0) + g_3(1).
\end{equation*}

P sends $g_3^*$ (claiming it is the same as $g_3$). V checks:
1. $\deg g_3^* \le 8$,
2. $g_2^*(r_2) = g_3^*(0) + g_3^*(1)$.

If the checks pass, V samples
\begin{equation*}
r_3 \leftarrow \mathbb{F}
\end{equation*}
and sends it to P.

With our specific values $(r_0,r_1,r_2)=(99,7,1001)$, the true polynomial is
\begin{equation*}
g_3(u_3) = 421362090u_3^2 + 655825959u_3.
\end{equation*}
Suppose P instead claims this is
\begin{equation*}
g^*_3(u_3) = 421362091u_3^2 + 387749940u_3.
\end{equation*}
V verifies consistency by checking (in $\mathbb{Z}/p\mathbb{Z}$)
\begin{equation*}
\begin{align}
g^*_2(1001) & = 69133477(1001)^2 + 1469794372(1001) + 138157656 = 809112031,\\
g^*_3(0) + g^*_3(1) & = 0 + (421362091 + 387749940) = 809112031.
\end{align}
\end{equation*}
Thus the transcript is still internally consistent. Suppose V's final random challenge is
\begin{equation*}
r_3 = 666.
\end{equation*}

**Sum-check final check (no folding).** At this point,
\begin{equation*}
g_3(r_3) = g(r_0,r_1,r_2,r_3).
\end{equation*}
In earlier layers, this is where folding would be used. Here, however, we are at the input layer, so V can evaluate $g(r_0,r_1,r_2,r_3)$ directly from the public data.

Expanding the right-hand side gives
\begin{equation*}
\begin{aligned}
g(r_0,r_1,r_2,r_3)
&=
\widetilde{\mathrm{add}}_1(\rho_1,(r_0,r_1),(r_2,r_3))
\big[
\widetilde{W}_{2}(r_0,r_1) + \widetilde{W}_{2}(r_2,r_3)
\big]
+
\widetilde{\mathrm{mult}}_1(\rho_1,(r_0,r_1),(r_2,r_3))
\big[
\widetilde{W}_{2}(r_0,r_1)\widetilde{W}_{2}(r_2,r_3)
\big].
\end{aligned}
\end{equation*}

Since the circuit is public, V can evaluate the wiring predicates:
\begin{equation*}
\begin{align}
\widetilde{\mathrm{add}}_1(\rho_1,(r_0,r_1),(r_2,r_3))
&= \rho_1 r_0(1-r_1)r_2r_3,\\
\widetilde{\mathrm{mult}}_1(\rho_1,(r_0,r_1),(r_2,r_3))
&= (1-\rho_1)(1-r_0)(1-r_1)(1-r_2)r_3.
\end{align}
\end{equation*}

Crucially, because this is the input layer, V can also compute $\widetilde{W}_2$ directly:
\begin{equation*}
\widetilde{W}_{2}(r_0,r_1) = -2r_0r_1 + r_0 - r_1 + 3,
\qquad
\widetilde{W}_{2}(r_2,r_3) = -2r_2r_3 + r_2 - r_3 + 3.
\end{equation*}

V therefore checks whether
\begin{equation*}
g_3^*(r_3) \overset{?}{=} g(r_0,r_1,r_2,r_3),
\end{equation*}
rejecting if the equality fails. If it holds, V accepts and the protocol terminates.

With our concrete values $(r_0,r_1,r_2,r_3)=(99,7,1001,666)$, V computes
\begin{equation*}
g^*_3(r_3) = g_3^*(666) = 421362091(666)^2 + 387749940(666) = 577775939.
\end{equation*}
If P were honest, we would instead have
\begin{equation*}
g_3(r_3) = 421362090(666)^2 + 655825959(666) = 874818336.
\end{equation*}
Although V does not know $g_3(r_3)$ directly, V does compute the right-hand side exactly:
\begin{equation*}
g(r_0,r_1,r_2,r_3) = g(99,7,1001,666) = 874818336.
\end{equation*}
Since $874818336 \ne 577775939$, V rejects P's original claim.

````{prf:example} the worked example, computed
:label: eg-worked-computed

```{code-cell} python
expression_01 = '(3*2) + (4 + 1)'
gkr_01 = ArithmeticCircuit(expression_01, prime=2**(31) - 1)

display(gkr_01.graphviz_circuit_bitstring)
gkr_01.print_gate_values()
gkr_01.print_tilde_W()
gkr_01.print_wiring_predicates()
gkr_01.print_wiring_predicate_mles()
gkr_01.print_verification_propagation_equation()
gkr_01.print_verification_propagation_equation(mle=True)
```
````

````{prf:example} honest GKR, end to end
:label: eg-gkr-honest

```{code-cell} python
from gkr import gkr_example
gkr_example();
```
````

````{prf:example} a dishonest prover
:label: eg-gkr-dishonest

```{code-cell} python
gkr_example(dishonest=True);
```
````

(sec-formal-description)=
## The GKR protocol (formal description)

**Setup.** Let $C$ be a constant-input, strictly layered arithmetic circuit of depth $d$ with fan-in two.  
For each layer $i \in \{0,\ldots,d\}$, let $s_i$ denote the bit-length of gate labels at Layer $i$, and let
\begin{equation*}
W_i : \{0,1\}^{s_i} \to \mathbb{F},
\qquad
\widetilde{W}_i : \mathbb{F}^{s_i} \to \mathbb{F}
\end{equation*}
be the gate-value function and its multilinear extension.  

For each $i \in \{0,\ldots,d-1\}$, the circuit wiring is public and encoded by multilinear extensions
\begin{equation*}
\widetilde{\mathrm{add}}_i,\;\widetilde{\mathrm{mult}}_i :
\mathbb{F}^{s_i} \times \mathbb{F}^{s_{i+1}} \times \mathbb{F}^{s_{i+1}} \to \mathbb{F}.
\end{equation*}

**Layer 0 (output layer).**

- P sends a polynomial function
  \begin{equation*}
  \widetilde{W}_0^* : \mathbb{F}^{s_0} \to \mathbb{F},
  \end{equation*}
  claimed to be the multilinear extension of the output gate-value function.

- V samples
  \begin{equation*}
  \rho_0 \leftarrow \mathbb{F}^{s_0}
  \end{equation*}
  uniformly at random, and evaluates the claimed polynomial at that point.

- Let
  \begin{equation*}
  \alpha_0 := \widetilde{W}_0^*(\rho_0) \in \mathbb{F}.
  \end{equation*}

In an honest execution, $\widetilde{W}_0^* \overset{?}{=}\widetilde{W}_0$, and hence $\alpha_0\overset{?}{=}\widetilde{W}_0(\rho_0)$. The remainder of the protocol is devoted to justifying this value. (We place a question mark over an equality symbol to remind the reader that these equalities may not hold if P is dishonest.)

**Layer i, $0 \le i \le d-1$.** At the start of Layer i, V holds:
- a point $\rho_i \in \mathbb{F}^{s_i}$,
- a scalar $\alpha_i \in \mathbb{F}$,

which, in an honest execution, satisfy $\alpha_i\overset{?}{=}\widetilde{W}_i(\rho_i)$. Define the polynomial function
\begin{equation*}
g(\mathbf{x},\mathbf{y})
:=
\widetilde{\mathrm{add}}_i(\rho_i,\mathbf{x},\mathbf{y})
\big[\widetilde{W}_{i+1}(\mathbf{x})+\widetilde{W}_{i+1}(\mathbf{y})\big]
+
\widetilde{\mathrm{mult}}_i(\rho_i,\mathbf{x},\mathbf{y})
\big[\widetilde{W}_{i+1}(\mathbf{x})\widetilde{W}_{i+1}(\mathbf{y})\big],
\end{equation*}
a polynomial on $\mathbb{F}^{s_{i+1}} \times \mathbb{F}^{s_{i+1}}$. If P is honest, then by Thaler's identity,
\begin{equation*}
\alpha_i
\overset{?}{=}
\sum_{(\mathbf{x},\mathbf{y}) \in \{0,1\}^{s_{i+1}} \times \{0,1\}^{s_{i+1}}}
g(\mathbf{x},\mathbf{y}),
\end{equation*}
and this equality must hold in order for the protocol to continue without rejection.

**Sum-check at Layer i.**

- P and V run the sum-check protocol on the above sum.
- Let $m := 2s_{i+1}$ be the number of Boolean variables.
- V introduces random challenges
  \begin{equation*}
  r_0,\ldots,r_{m-1} \in \mathbb{F},
  \end{equation*}
  grouped as
  \begin{equation*}
  r_x := (r_0,\ldots,r_{s_{i+1}-1}),
  \qquad
  r_y := (r_{s_{i+1}},\ldots,r_{m-1}).
  \end{equation*}

- P sends round polynomials $g_0^*,\ldots,g_{m-1}^*$.
- V checks degree bounds and round-to-round consistency, with the initial consistency condition
  \begin{equation*}
  \alpha_i \overset{?}{=} g_0^*(0)+g_0^*(1).
  \end{equation*}
- In particular, V checks that each round polynomial satisfies
  \begin{equation*}
  \deg g_j^* \overset{?}{\le} 2.
  \end{equation*}
  This is a valid bound on the true round polynomials: each variable occurs to degree at most $1$ in $\widetilde{\mathrm{add}}_i(\rho_i,\cdot,\cdot)$ and $\widetilde{\mathrm{mult}}_i(\rho_i,\cdot,\cdot)$, and to degree at most $1$ in $\widetilde{W}_{i+1}(\mathbf{x})$ or $\widetilde{W}_{i+1}(\mathbf{y})$, so $g$ has degree at most $2$ in each of its $2s_{i+1}$ variables. The tightness of this check is not bureaucracy: the degree bound V enforces reappears, round for round, in the soundness error below.

At the end of sum-check, correctness reduces to
\begin{equation*}
g_{m-1}^*(r_{m-1}) \overset{?}{=} g(r_x,r_y).
\end{equation*}

**Bridging and folding.** V cannot evaluate $g(r_x,r_y)$ directly, since it depends on $\widetilde{W}_{i+1}$. P therefore supplies two field elements
\begin{equation*}
z_x^*, \, z_y^* \in \mathbb{F},
\end{equation*}
intended (in an honest execution) to equal
\begin{equation*}
\widetilde{W}_{i+1}(r_x), \, \widetilde{W}_{i+1}(r_y).
\end{equation*}

Using only public data, V checks
\begin{equation*}
g_{m-1}^*(r_{m-1}) \overset{?}{=} \widetilde{\mathrm{add}}_i(\rho_i,r_x,r_y)\big[z_x^*+z_y^*\big]
+
\widetilde{\mathrm{mult}}_i(\rho_i,r_x,r_y)\big[z_x^*z_y^*\big].
\end{equation*}
(V computes both sides themself.) If this check fails, V rejects.

Assuming it passes, define the affine line
\begin{equation*}
\ell_{i+1} : \mathbb{F} \to \mathbb{F}^{s_{i + 1}}, \quad \ell_{i+1}(t) := (1-t)r_x + t r_y,
\end{equation*}
and the associated ground-truth univariate polynomial function
\begin{equation*}
q_{i + 1} : \mathbb{F} \to \mathbb{F}, \quad q_{i+1}(t) := \widetilde{W}_{i+1}(\ell_{i+1}(t)).
\end{equation*}

P sends a univariate polynomial $q_{i+1}^*$, purported to equal $q_{i+1}$. V checks:
1. $\deg q_{i+1}^* \overset{?}{\le} s_{i+1}$,
2. $q_{i+1}^*(0) \overset{?}{=} z_x^*$ and $q_{i+1}^*(1) \overset{?}{=} z_y^*$.

If these checks pass, V samples
\begin{equation*}
\tau_{i+1} \leftarrow \mathbb{F}
\end{equation*}
uniformly at random, and sets
\begin{equation*}
\rho_{i+1} := \ell_{i+1}(\tau_{i+1}),
\qquad
\alpha_{i+1} := q_{i+1}^*(\tau_{i+1}).
\end{equation*}

In an honest execution, $\alpha_{i+1}\overset{?}{=}\widetilde{W}_{i+1}(\rho_{i+1})$. The protocol then proceeds to Layer i + 1.

**Final layer.** At Layer d - 1, the same procedure is followed through the sum-check. There is no folding step: the child layer $d$ consists of input gates, so $\widetilde{W}_d$ is fully determined by the public inputs, and V computes $z_x = \widetilde{W}_d(r_x)$ and $z_y = \widetilde{W}_d(r_y)$ directly. V then checks the bridging equation with these true values. If it holds, V accepts; otherwise, V rejects.

(sec-completeness-and-soundness)=
## Completeness and soundness

**Completeness.** If P is honest and V's calculations are accurate, V accepts with probability $1$.

*Proof.* An honest P sends $\widetilde{W}_0^* = \widetilde{W}_0$, so $\alpha_0 = \widetilde{W}_0(\rho_0)$. Suppose inductively that $\alpha_i = \widetilde{W}_i(\rho_i)$ at the start of Layer $i$. By Thaler's identity, $\alpha_i$ really is the sum of $g$ over $\{0,1\}^{s_{i+1}} \times \{0,1\}^{s_{i+1}}$, so the honest round polynomials satisfy every degree bound and every consistency condition of the sum-check, and the terminal value is $g_{m-1}(r_{m-1}) = g(r_x, r_y)$. The honest endpoints $z_x^* = \widetilde{W}_{i+1}(r_x)$ and $z_y^* = \widetilde{W}_{i+1}(r_y)$ make the bridging check the *definition* of $g(r_x,r_y)$, hence an identity. The honest $q_{i+1}^* = q_{i+1} = \widetilde{W}_{i+1} \circ \ell_{i+1}$ has degree at most $s_{i+1}$ (a multilinear polynomial composed with an affine line: each monomial $\prod_{k \, \in \, T} \ell_{i+1}(t)_k$ has degree $|T| \le s_{i+1}$ in $t$) and matches both endpoints, so the folding checks pass and
\begin{equation*}
\alpha_{i+1} = q_{i+1}(\tau_{i+1}) = \widetilde{W}_{i+1}(\ell_{i+1}(\tau_{i+1})) = \widetilde{W}_{i+1}(\rho_{i+1}),
\end{equation*}
closing the induction. At the final layer, V evaluates $z_x, z_y$ itself from the public inputs, and the bridging check is again an identity. Every check is an equality between correctly computed quantities, so V accepts.

**Soundness.** A dishonest P may claim incorrect output values and still pass. We now bound the probability of this event and locate exactly where it can occur. There are only three places in the whole protocol where P is exposed to V's randomness: the choice of $\rho_0$, the challenge $r_j$ of each sum-check round, and the challenge $\tau_{i+1}$ of each fold. Everything else (the bridging equations, the endpoint claims $z_x^*, z_y^*$, the boundary conditions on $q_{i+1}^*$), P can, and a clever P will, satisfy *identically*, by lying consistently. The soundness error is the union bound over those exposures and nothing more.

```{prf:theorem} soundness of GKR
:label: thm-gkr-soundness
Suppose P's claimed outputs are not all correct, so that $\widetilde{W}_0^* \ne \widetilde{W}_0$ as multilinear polynomials. (In our implementation, V receives the claimed output *values* and forms the multilinear extension itself, so $\widetilde{W}_0^*$ is multilinear by construction; if instead P sends a polynomial, V enforces multilinearity.) Then
\begin{equation}
\label{eq-gkr-19}
\Pr[\text{V accepts}]
\;\le\;
\frac{s_0 \;+\; \displaystyle\sum_{i=0}^{d-1} 2 \cdot (2 s_{i+1}) \;+\; \sum_{i=0}^{d-2} s_{i+1}}{\#\mathbb{F}}
\;=\;
\frac{s_0 \;+\; 4\displaystyle\sum_{i=1}^{d} s_i \;+\; \sum_{i=1}^{d-1} s_i}{\#\mathbb{F}}
\;\le\;
\frac{s_0 + 5\displaystyle\sum_{i=1}^{d} s_i}{\#\mathbb{F}}.
\end{equation}
The three numerator terms are the three exposures: $\rho_0$, then $2s_{i+1}$ sum-check rounds per layer each carrying the enforced degree bound $2$, then one fold of degree at most $s_{i+1}$ per non-final layer. Writing $S_i = 2^{s_i}$ for the width of Layer $i$ and $S = \max_i S_i$,
\begin{equation}
\label{eq-gkr-20}
\Pr[\text{V accepts}] \;=\; O\!\left(\frac{d \log S}{\#\mathbb{F}}\right),
\end{equation}
the bound stated in [@tha2022] (p. 65). (More generally, if V enforces round-degree bounds $B_j \ge \deg_j g$, the middle term of [](#eq-gkr-19) becomes $\sum_i \sum_j B_j$: the check V performs is the price V pays.)
```

**Notation for the proof.** Fix a layer $i$ and drop the layer superscript. As in the [sum-check notebook](./01-sum-check-protocol.md), the *true* round polynomials of the Layer $i$ sum-check are
\begin{equation*}
\begin{align}
g_j(u) &:= \sum_{\mathbf{b} \, \in \, \{0,1\}^{m-1-j}} g(r_0,\ldots,r_{j-1},u,\mathbf{b}), \qquad 0 \le j \le m-1,
\end{align}
\end{equation*}
so that
\begin{equation*}
\begin{align}
g_0(0) + g_0(1) &= \sum_{(\mathbf{x},\mathbf{y})} g(\mathbf{x},\mathbf{y}) = \widetilde{W}_i(\rho_i) \quad \text{(Thaler's identity)}, \\
g_{j-1}(r_{j-1}) &= g_j(0) + g_j(1), \qquad 1 \le j \le m-1, \\
g_{m-1}(r_{m-1}) &= g(r_x, r_y),
\end{align}
\end{equation*}
and $\deg g_j \le \deg_j g \le 2$, as observed in the protocol description. We say the **carried claim at Layer $i$ is false** if $\alpha_i \ne \widetilde{W}_i(\rho_i)$. P is of course free to send whatever it likes; the objects above are the honest ones, well-defined whether or not anyone computes them, and V's checks are comparisons against P's actual messages $g_0^*, \ldots, g_{m-1}^*, z_x^*, z_y^*, q_{i+1}^*$.

Two families of *lucky events* will carry the whole error budget:
\begin{equation*}
\begin{align}
L_{i,j} &: \quad g_j^* \ne g_j \;\text{ and }\; g_j^*(r_j) = g_j(r_j) \qquad \text{(round $j$ of Layer $i$'s sum-check)}, \\
M_i &: \quad q_{i+1}^* \ne q_{i+1} \;\text{ and }\; q_{i+1}^*(\tau_{i+1}) = q_{i+1}(\tau_{i+1}) \qquad \text{(the fold, $0 \le i \le d-2$)}.
\end{align}
\end{equation*}

```{prf:lemma} layer transition
:label: lem-layer-transition
Fix $i \in \{0,\ldots,d-1\}$ and suppose the carried claim at Layer $i$ is false. Then at least one of the following holds:

1. V rejects during Layer $i$;
2. $L_{i,j}$ occurs for some round $j$, or ($i \le d-2$) $M_i$ occurs;
3. $i \le d-2$ and the carried claim at Layer $i+1$ is false.

Moreover, for $i = d-1$ the third alternative is empty: V rejects outright unless some $L_{d-1,j}$ occurs.
```

```{admonition} Proof of the lemma
:class: proof
Suppose V does not reject during Layer $i$ and no $L_{i,j}$ occurs; we show the lie must survive intact to the next layer (or be caught at the final one).

**The sum-check.** We claim $g_j^* \ne g_j$ and $g_j^*(r_j) \ne g_j(r_j)$ for every $j$, by induction. For $j = 0$: V's initial consistency check gives $\alpha_i = g_0^*(0) + g_0^*(1)$; if $g_0^* = g_0$, then $\alpha_i = g_0(0) + g_0(1) = \widetilde{W}_i(\rho_i)$, contradicting the false carried claim; so $g_0^* \ne g_0$, and since $L_{i,0}$ does not occur, $g_0^*(r_0) \ne g_0(r_0)$. For $j \ge 1$: the round-$j$ consistency check and the inductive hypothesis give
\begin{equation*}
g_j^*(0) + g_j^*(1) = g_{j-1}^*(r_{j-1}) \ne g_{j-1}(r_{j-1}) = g_j(0) + g_j(1),
\end{equation*}
so $g_j^* \ne g_j$, and since $L_{i,j}$ does not occur, $g_j^*(r_j) \ne g_j(r_j)$. In particular, writing $\gamma^* := g_{m-1}^*(r_{m-1})$ for the terminal value,
\begin{equation*}
\gamma^* \;\ne\; g_{m-1}(r_{m-1}) \;=\; g(r_x, r_y).
\end{equation*}
Note what did *not* happen here: unlike in the standalone protocol, V performs no oracle check at the end of the sum-check, so nothing yet forces a rejection: the lie survives to the terminal claim.

**The bridge.** Write $A := \widetilde{\mathrm{add}}_i(\rho_i, r_x, r_y)$, $M := \widetilde{\mathrm{mult}}_i(\rho_i, r_x, r_y)$, and let $z_x := \widetilde{W}_{i+1}(r_x)$, $z_y := \widetilde{W}_{i+1}(r_y)$ be the true endpoint values. By the definition of $g$,
\begin{equation*}
g(r_x, r_y) = A\,[z_x + z_y] + M\,[z_x z_y].
\end{equation*}
V's bridging check is $\gamma^* \overset{?}{=} A[z_x^* + z_y^*] + M[z_x^* z_y^*]$. If P sent the true endpoints, the right-hand side would equal $g(r_x,r_y) \ne \gamma^*$ and V would reject. Hence, if V does not reject at the bridge,
\begin{equation*}
(z_x^*, z_y^*) \ne (z_x, z_y).
\end{equation*}

**The fold ($i \le d-2$).** The true polynomial $q_{i+1} = \widetilde{W}_{i+1} \circ \ell_{i+1}$ satisfies $q_{i+1}(0) = z_x$ and $q_{i+1}(1) = z_y$, while V's boundary checks force $q_{i+1}^*(0) = z_x^*$ and $q_{i+1}^*(1) = z_y^*$. Since the endpoint pairs differ, $q_{i+1}^* \ne q_{i+1}$. If $M_i$ does not occur, then
\begin{equation*}
\alpha_{i+1} = q_{i+1}^*(\tau_{i+1}) \;\ne\; q_{i+1}(\tau_{i+1}) = \widetilde{W}_{i+1}(\ell_{i+1}(\tau_{i+1})) = \widetilde{W}_{i+1}(\rho_{i+1}):
\end{equation*}
the carried claim at Layer $i+1$ is false, which is alternative 3.

**The final layer ($i = d-1$).** Here V computes $z_x = \widetilde{W}_d(r_x)$ and $z_y = \widetilde{W}_d(r_y)$ itself from the public inputs, and its last check is
\begin{equation*}
\gamma^* \overset{?}{=} A[z_x + z_y] + M[z_x z_y] = g(r_x, r_y) \ne \gamma^*,
\end{equation*}
so V rejects.
```

```{admonition} Proof of the theorem
:class: proof
First, the output claim itself. Since $\widetilde{W}_0^* \ne \widetilde{W}_0$ and both are multilinear in $s_0$ variables, their difference is a nonzero polynomial of total degree at most $s_0$, fixed before $\rho_0$ is sampled. Let $E_0$ be the event $\widetilde{W}_0^*(\rho_0) = \widetilde{W}_0(\rho_0)$. By the Schwartz-Zippel lemma (see the [multilinear-extensions notebook](./02-multilinear-extensions.md)),
\begin{equation*}
\Pr[E_0] \le \frac{s_0}{\#\mathbb{F}}.
\end{equation*}
(When $s_0 = 0$, as in our worked example, the difference is a nonzero constant and $\Pr[E_0] = 0$: a false output claim about a single output gate cannot get lucky at Layer $0$.)

If $E_0$ does not occur, then $\alpha_0 = \widetilde{W}_0^*(\rho_0) \ne \widetilde{W}_0(\rho_0)$: the carried claim at Layer $0$ is false. Applying the lemma at Layers $0, 1, \ldots, d-1$ in turn: as long as no lucky event occurs and V does not reject, the false carried claim propagates, and at Layer $d-1$ the lemma leaves no third alternative. Therefore
\begin{equation*}
\{\text{V accepts}\} \;\subseteq\; E_0 \;\cup\; \bigcup_{i,\,j} L_{i,\,j} \;\cup\; \bigcup_{i \,\le\, d-2} M_i.
\end{equation*}

Now the probabilities, exactly as in the sum-check analysis. For $L_{i,j}$: the polynomials $g_j^*$ and $g_j$ are fixed after the transcript $(\rho_i; r_0, \ldots, r_{j-1})$ but *before* $r_j$ is chosen, so they are independent of $r_j$; V's degree check bounds $\deg g_j^* \le 2$, and $\deg g_j \le 2$; their difference is a nonzero univariate polynomial of degree at most $2$, and $r_j$ is uniform in $\mathbb{F}$, so by the univariate root bound
\begin{equation*}
\Pr[L_{i,\,j}] \le \frac{2}{\#\mathbb{F}}.
\end{equation*}
For $M_i$: the polynomials $q_{i+1}^*$ and $q_{i+1}$ are fixed before $\tau_{i+1}$ is chosen; V's degree check bounds $\deg q_{i+1}^* \le s_{i+1}$, and $\deg q_{i+1} \le s_{i+1}$; their difference is nonzero of degree at most $s_{i+1}$, and $\tau_{i+1}$ is uniform, so
\begin{equation*}
\Pr[M_i] \le \frac{s_{i+1}}{\#\mathbb{F}}.
\end{equation*}
There are $2s_{i+1}$ rounds at Layer $i$ for $0 \le i \le d-1$, and one fold for each $0 \le i \le d-2$. The union bound gives [](#eq-gkr-19), and [](#eq-gkr-20) follows since $s_i = \log_2 S_i \le \log_2 S$.
```

```{prf:remark} where the randomness is spent, and why the bound is nearly tight
:label: rem-randomness-spent
Two features of the proof deserve emphasis, because both are visible in the implementation's narration (run `gkr_example(dishonest=True)` and read the invisible-to-V blocks and the ground-truth ledger).

*The deterministic parts really are deterministic.* The bridging equation contributes nothing to the error budget: a P whose lie survived the sum-check simply solves $\gamma^* = A[z_x^* + z_y^*] + M[z_x^* z_y^*]$ for forged endpoints (one equation, two unknowns, solvable whenever $(A, M) \ne (0,0)$), and threads any degree-$s_{i+1}$ polynomial through the two forged boundary values. (In the degenerate case $A = M = 0$, the right-hand side is $0$ for *every* choice of endpoints, but then $g(r_x,r_y) = 0 \ne \gamma^*$ too, and V rejects with certainty: the degenerate bridge only ever helps V.) This is the precise sense in which a dishonest P can "lie consistently" from one sum-check to the next: between the random challenges, nothing stops it.

*Each lucky event fully converts.* Conversely, the moment any $L_{i,\,j}$ or $M_i$ occurs, P can *revert to honesty* (send the true polynomials, true endpoints, and true folds from that point on), and V accepts with certainty, exactly as in the standalone sum-check protocol (the implementation calls this laundering the lie). So the union in the proof is over events each of which suffices alone. Moreover P can typically realize each event's maximal probability: to plant two agreement points $a, b$ in round $j$, P sends $g_j^* = g_j + c\,(X-a)(X-b)$ and uses the one free scalar $c$ to satisfy the consistency condition, which is possible whenever $2ab - a - b + 1 \ne 0$. The implementation's cheating prover does exactly this (the advice blocks report *the roots of $g_j^* - g_j$*), which is why the measured false-positive rates below sit so close to the bound: the worst-case prover the theorem imagines is, almost always, the prover we actually implemented.
```

```{prf:example} the bound, in numbers
:label: eg-bound-numbers
For the worked example $(3 \times 2) + (4 + 1)$ we have $d = 2$ and $(s_0, s_1, s_2) = (0, 1, 2)$, so [](#eq-gkr-19) reads
\begin{equation*}
\Pr[\text{V accepts a false output claim}] \le \frac{0 + 4(1 + 2) + 1}{\#\mathbb{F}} = \frac{13}{\#\mathbb{F}},
\end{equation*}
thirteen chances: none at $\rho_0$, two per sum-check round ($2$ rounds at Layer $0$, $4$ at Layer $1$), and one at the single fold. For the two-output circuit $(1+2)(3+4);\ (5+6)+(7 \times 8)$, with $(s_0, s_1, s_2) = (1, 2, 3)$: $1 + 4(2+3) + 2 = 23$ chances.

Over $\mathbb{F} = \mathrm{GF}(101)$, deliberately tiny, the bounds are $13/101 \approx 0.129$ and $23/101 \approx 0.228$, and Monte Carlo agrees (the cell below reproduces the first line):

| circuit | union bound | measured false-positive rate |
|---|---|---|
| $(3 \times 2)+(4+1)$ | $13/101 \approx 0.129$ | $0.125 \pm 0.032$ ($400$ runs) |
| $(1+2)(3+4);\ (5+6)+(7 \times 8)$ | $23/101 \approx 0.228$ | $0.215 \pm 0.040$ ($400$ runs) |

Two lessons. First, the $1/\#\mathbb{F}$ intuition from a single Schwartz-Zippel event misleads badly here: a GKR run offers *many* independent chances to be fooled, and the soundness error grows linearly with circuit size ($d \log S$ chances, roughly). Second, this is precisely why GKR wants a large field: over $\mathrm{GF}(2^{31}-1)$, the very same $23$ chances amount to $23/(2^{31}-1) \approx 1.1 \times 10^{-8}$.
```

```{code-cell} python
# Reproduce the first row of the table: the worked example over GF(101).
# A dishonest machine prover corrupts the output claim and plants maximal
# roots at every opportunity; we count how often V accepts. Takes ~10 s.
import random

from gkr.ac import ArithmeticCircuit
from gkr.protocol import Sink, RandomVerifier, run_gkr
from gkr.protocol.gkr_parties import GkrMachineProver
from gkr.utils.display import TerminalOutput

random.seed(2026)
quiet = TerminalOutput(enable_paging=False)
quiet.print = lambda *a, **k: None            # discard the narration

ac = ArithmeticCircuit('(3*2) + (4 + 1)', prime=101)

N, accepted = 400, 0
for _ in range(N):
    sink = Sink(lambda e: True)
    prover = GkrMachineProver(ac, sink, secret_mode=False, dishonest_claim=True, out=quiet)
    result = run_gkr(ac, prover=prover, verifier=RandomVerifier(ac.field, out=quiet),
                     sink=sink, out=quiet)
    accepted += (result.status == "accept")

rate = accepted / N
half = 1.96 * (rate * (1 - rate) / N) ** 0.5
print(f"union bound:  13/101 = {13/101:.4f}")
print(f"measured:     {accepted}/{N} = {rate:.4f}  (+/- {half:.4f} at 95%)")
```

(sec-costs)=
## Costs

We do not develop the cost analysis here. See [@tha2022, §4.6.5] for a full account of the verifier's and prover's runtimes, the round complexity and communication cost, and [@tha2022, §4.6.6] for the separate question of evaluating $\widetilde{\mathrm{add}}_i$ and $\widetilde{\mathrm{mult}}_i$ efficiently, which is the delicate term in V's runtime and the reason the protocol is usually stated for circuits whose wiring has repeated structure. The techniques that bring P's runtime down to $O(S\log S)$ are due to [@cmt2012].

**A note on this implementation.** The code accompanying these notes makes no attempt at any of this. It constructs $\widetilde{\mathrm{add}}_i$,
$\widetilde{\mathrm{mult}}_i$ and $\widetilde{W}_i$ symbolically over the whole Boolean hypercube, which is exponential in the label lengths. The object here is to watch the protocol's structure, not to run it at scale, but it is why the worked examples are small.