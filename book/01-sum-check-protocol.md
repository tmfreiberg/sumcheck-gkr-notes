---
title: Sum-check protocol
kernelspec:
    name: python3
    display_name: Python 3
---

```{code-cell} python
:tags: [remove-input]
import gkr
env = gkr.init(verbose=False)
```

(sec-introduction)=
## Introduction

These notes replicate Thaler's elegant presentation [@tha2015] of the sum-check protocol by Lund, Fortnow, Karloff, and Nisan [@lfkn1992], enriched with additional background information and interactive examples.

(sec-terminology)=
## Definitions, conventions, and notation

Let $\mathbb{F}$ be a finite field, $v$ a positive integer, and $g$ a $v$-variate polynomial with coefficients in $\mathbb{F}$:
\begin{equation}
\label{eq-poly}
 g(X_0,\ldots,X_{v - 1}) = \sum_{e \, \in \, \mathbb{N}^{v}} a_{e} X_0^{e_0}\cdots X_{v - 1}^{e_{v - 1}}, \quad a_e \in \mathbb{F}, \quad e = (e_0,\ldots,e_{v-1}), 
\end{equation}
where $a_e = 0$ for all but finitely many $e$. The ring of all such polynomials is denoted $\mathbb{F}[X_0,\ldots,X_{v - 1}]$. We use zero-based indexing throughout for consistency with the code and to minimize confusion, and define
\begin{equation*}
\mathbb{N} := \{0,1,2,\ldots\}.
\end{equation*}

```{prf:definition} 
:label: def-degree
Referring to [](#eq-poly) above, we call each $a_e$ a _coefficient_ of $g$. If $a_e = 0$ for all $e \in \mathbb{N}^v$, we call $g$ the _zero polynomial_. Suppose $g$ is _not_ the zero polynomial. The _total degree_ of $g$ is 
\begin{equation}
\label{eq-degree-total}
\mathrm{deg}(g) = \max \left\{ e_0 + \cdots + e_{v-1} : a_e \ne 0 \right\},
\end{equation}
i.e. the highest sum of the exponents of the indeterminates in any single term with a nonzero coefficient. The _degree of indeterminate $X_j$ in $g$_ is 
\begin{equation}
\label{eq-degree-indeterminate}
\mathrm{deg}_{X_j}(g) = \max \left\{ e_j : a_e \ne 0 \right\}, 
\end{equation}
i.e. the highest power of $X_j$ that appears in any single term with a nonzero coefficient. As the indeterminates are indexed we may denote this by $\mathrm{deg}_j(g)$. We call $g$ _multilinear_ if each $e_j$ in [](#eq-poly) is either $0$ or $1$. In other words, $g$ is multilinear if it is linear in each of its indeterminates individually.
```

```{prf:remark}
:label: rem-degree 
(i) The total degree of a univariate polynomial ($v = 1$) is just its degree. We may use the terms _degree_ and _total degree_ interchangeably. 

(ii) The zero polynomial is denoted by $0$. Context will always make clear whether $0$ denotes the zero polynomial or the zero element of $\mathbb{F}$. The nonzero constant polynomials are precisely those of total degree $0$. We leave the degree of the zero polynomial undefined. Some authors, however, define it as $-\infty$ for convenience, which simplifies statements like $\mathrm{deg}(g_1 + g_2) \le \max\{\mathrm{deg}(g_1),\mathrm{deg}(g_2)\}$ and $\mathrm{deg}(g_1g_2) = \mathrm{deg}(g_1) + \mathrm{deg}(g_2)$, without needing to exclude the zero polynomial as a special case. (iii) On the other hand, if we consider $g$ as a $v$-variate polynomial in $\mathbb{F}[X_0,\ldots,X_{v-1}]$, then $\mathrm{deg}_{j}(X_j)$ is defined and nonnegative for every $j$, $0 \le j \le v - 1$. Some authors might say, for instance, that the degree of $X_2$ in $X_0X_1 + X_1^2$, is undefined. In our case, if we understand the polynomial as belonging to $\mathbb{F}[X_0,X_1,X_2]$, then we note that we can multiply each term by $X_2^0$ without affecting the polynomial, whence the degree of $X_2$ in this polynomial is $0$. This convention ensures that $\mathrm{deg}_j(g)$ is defined for all $j$, which will be important when tracking degree bounds variable-by-variable in the sum-check protocol.
```

In the RHS of [](#eq-poly), we may replace a subset of $w$ indeterminates $X_j$ with field elements $r_j$, resulting in a $(v - w)$-variate polynomial in the remaining indeterminates, with their original indices preserved, and which we denote by substituting the corresponding $r_j$ for each replaced $X_j$ in the LHS. For instance, if $v > 1$ then $g(X_0,r_1,\ldots,r_{v-1})$ denotes the univariate polynomial in the indeterminate $X_0$, obtained by substituting $X_1,\ldots,X_{v - 1}$ with $r_1,\ldots,r_{v - 1}$ in the RHS. For a more explicit example: if $g(X_0,X_1,X_2) = X_0X_1X_2 + X_0X_1^2 + X_2$ then $g(X_0,1,1) = 2X_0 + 1$.

Formally, substituting field elements for indeterminates defines a ring homomorphism
\begin{equation*}
\mathbb{F}[X_0,\ldots,X_{v - 1}] \mapsto \mathbb{F}[X_{i_1},\ldots,X_{i_{v - w}}].
\end{equation*}
The expression $g(r_0,\ldots,r_{v - 1})$ therefore denotes a constant polynomial in $0$ indeterminates, which we identify with the corresponding field element. We call this the _evaluation_ of $g$ at the point $(r_0,\ldots,r_{v - 1})$. We call $(r_0,\ldots,r_{v-1})$ a _root_ or _zero_ of $g$ in $\mathbb{F}^v$ if $g(r_0,\ldots,r_{v-1}) = 0$. For example, over $\mathbb{F} = \mathbb{Z}/2\mathbb{Z}$, the evaluation of $g(X_0,X_1,X_2) = X_0X_1X_2 + X_0X_1^2 + X_2$ at the point $(1,1,1)$ is $g(1,1,1) = 1$, so $(1,1,1)$ is not a root of $g$, but $g(0,0,0) = 0$, so $(0,0,0)$ is a root of $g$, as are $(0,1,0)$ and $(1,0,0)$.

```{prf:definition}
:label: def-poly-function
We call $f : \mathbb{F}^v \to \mathbb{F}$ a _polynomial function_ if there is a $g \in \mathbb{F}[X_0,\ldots,X_{v - 1}]$ such that $f(x_0,\ldots,x_{v - 1}) = g(x_0,\ldots,x_{v - 1})$ for each $(x_0,\ldots,x_{v - 1}) \in \mathbb{F}^v$. 
```
```{prf:remark}
:label: rem-polynomial-vs-function
The distinction between constant polynomials and constants, and between polynomials and polynomial functions, may seem pedantic but are particularly important for polynomials over finite fields. Over a finite field, a polynomial function may be represented by many distinct polynomials. In fact, _every_ function $f : \mathbb{F}^v \to \mathbb{F}$ is a polynomial function, a consequence of the finiteness of $\mathbb{F}$.

If $\mathbb{F}$ has order $q$, then $X^q - X$ is certainly not the zero polynomial in $\mathbb{F}[X]$, but $x \mapsto x^q - x$ is the zero function on $\mathbb{F}$, by Fermat's little theorem (equivalently, the Frobenius endomorphism). Polynomials are really just sequences of coefficients that we add and multiply in a certain way. Indeterminates $X_j$ serve as placeholders&mdash;not variables&mdash;to encode formal algebraic operations independently of evaluation. If this remark seems opaque, consider that a univariate polynomial can be represented as a sequence of coefficients $(a_0, a_1, a_2, \ldots)$, where only finitely many $a_i$ are nonzero. Given two polynomials $g = (a_0, a_1, a_2, \ldots)$ and $h = (b_0, b_1, b_2, \dots)$, their product $g \cdot h$ is another sequence of coefficients $(c_0, c_1, c_2, \ldots)$ defined by $c_k = \sum_{i=0}^k a_i b_{k-i}$. 
```

````{prf:example}
:label: eg-degree
For simplicity, the demo below uses $\mathbb{F}_p$ with prime $p$. The same degree notions work over any finite field $\mathbb{F}_{p^k}$.
```{code-cell} python
from gkr import total_degree_example
total_degree_example(interactive=False)
```
````

In the sum-check protocol we will repeatedly substitute random field elements for some variables, so tracking $\mathrm{deg}_j(g)$ is useful because it bounds the degree of the univariate polynomials sent in each round.

(sec-schwartz-zippel)=
## DeMillo–Lipton–Schwartz–Zippel Lemma

This result, commonly referred to as the Schwartz-Zippel lemma, tells us that the roots of a multivariate polynomial over a field are sparse. This insight has useful implications; for instance, it suggests that two multivariate polynomials over a field are unlikely to agree at a randomly selected point, which is the crux of the soundness error in the sum-check protocol.

The lemma was first proved jointly by DeMillo and Lipton [@dml1978], preceding the independent discoveries by both Schwartz [@sch1980] and Zippel [@zip1979] around the late 1970s. In fact, for the special case of finite fields—which is the only case relevant here—the result was originally established by Ore in 1922 [@ore1922].

To set up the proof of the Schwartz-Zippel lemma, we begin by stating a foundational proposition upon which the proof relies.

```{prf:proposition}
:label: prop-root-bound
Let $\mathbb{F}$ be a field and $g \in \mathbb{F}[X]$ a nonzero univariate polynomial over $\mathbb{F}$. If $g$ has degree $d$, then $g$ has at most $d$ roots in $\mathbb{F}$, counted with multiplicity. 
```

```{admonition} Proof outline
:class: proof
Let $r_0 \in \mathbb{F}$ be a root of $g$. By the division algorithm, we may write
\begin{equation*}
g(X) = (X - r_0)q(X)
\end{equation*}
for some polynomial $q(X) \in \mathbb{F}[X]$ of degree $d - 1$. If $r_0$ is a repeated root, then there exists a maximal integer $m_0 \ge 1$ such that
\begin{equation*}
g(X) = (X - r_0)^{m_0}q_0(X), \quad q_0(r_0) \ne 0.
\end{equation*}
Now let $r_1 \ne r_0$ be another root of $g$. Since $\mathbb{F}$ is an integral domain, $(r_1 - r_0)^{m_0} \ne 0$, and hence 
\begin{equation*}
0 = g(r_1) = (r_1 - r_0)^{m_0}q_0(r_1)
\end{equation*}
implies $q_0(r_1) = 0$. Thus $q_0(X)$ is divisible by $X - r_1$. 

Repeating this process for distinct roots, each new root reduces the degree of the remaining factor by at least one. Since the original polynomial has degree $d$, the total number of roots, counted with multiplicity, cannot exceed $d$.
```

```{prf:lemma}DeMillo–Lipton–Schwartz–Zippel
:label: lem-schwartz-zippel
Let $g$ be a $v$-variate ($v \ge 1$), nonzero polynomial of total degree $d$ over a finite field $\mathbb{F}$. We have 
\begin{equation*}
\#\{\mathbf{r} \in \mathbb{F}^v : g(\mathbf{r}) = 0\} \le (\#\mathbb{F})^{v - 1}d.
\end{equation*}
In other words, if $r_0,\ldots,r_{v - 1}$ are selected at random independently and uniformly from $\mathbb{F}$, then 
\begin{equation}
\label{eq-schwartz-zippel-bound}
 \mathrm{Pr}[g(r_0,\ldots,r_{v - 1}) = 0] \le \frac{d}{\# \mathbb{F}}.
\end{equation}
```

```{admonition} Proof
:class: proof
The proof is by induction on $v$. The base case $v = 1$ is the previous proposition. Let $v \ge 2$ and assume the statement holds for all nonzero polynomials in $u$ indeterminates, $1 \le u \le v - 1$. 

Writing $g$ as in [](#eq-poly), note that 
\begin{equation*}
\begin{align}
g(X_0,\ldots,X_{v - 1}) 
& = \sum_{e \, \in \, \mathbb{N}^{v}} a_{e} X_0^{e_0}\cdots X_{v - 1}^{e_{v - 1}} \\
& = \sum_{e_{v-1} \, \in \, \mathbb{N}} X_{v-1}^{e_{v-1}} \sum_{(e_0,\ldots,e_{v-2}) \, \in \, \mathbb{N}^{v-1}} a_{e} X_0^{e_0}\cdots X_{v - 2}^{e_{v - 2}} \\
& = \sum_{k \, = \, 0}^{d} X_{v-1}^k h_k(X_0,\ldots,X_{v-2}),
\end{align}
\end{equation*}
say, where we have replaced $e_{v - 1}$ by $k$ in the outer sum and truncated it at $k = d$, because total degree $d$ implies $e_{v - 1} \le d$ for every monomial with nonzero coefficient. We can't have $h_k \equiv 0$ for every $k$, for in that case we'd also have $g \equiv 0$. Let $j = \max\{k: h_k \not\equiv 0\}$ be the largest $k$ for which $h_k$ is a nonzero polynomial. 

We now separate the roots of $g$ according to whether the leading coefficient (as a polynomial in $X_{v - 1}$) vanishes:
\begin{equation*}
\{\mathbf{r} \in \mathbb{F}^{v} : g(\mathbf{r}) = 0\} \subseteq \{\mathbf{r} \in \mathbb{F}^{v} : h_j(r_0,\ldots,r_{v-2}) = 0\} \cup \{\mathbf{r} \in \mathbb{F}^v :  h_j(r_0,\ldots,r_{v-2}) \ne 0 \,\, \text{and} \,\, g(\mathbf{r}) = 0 \}.
\end{equation*}
We will show that the sets on the RHS have sizes bounded by $(\#\mathbb{F})^{v - 1}(d - j)$ and $(\#\mathbb{F})^{v - 1}j$ respectively.

Since $X_{v-1}^jh_j(X_0,\ldots,X_{v-2})$ has degree at most $\mathrm{deg} \, (g) = d$, we have $\mathrm{deg} \, (h_j) \le d - j$. Therefore, by inductive hypothesis, 
\begin{equation*}
 \#\{(r_0,\ldots,r_{v - 2}) \in \mathbb{F}^{v - 1} : h_j(r_0,\ldots,r_{v-2}) = 0\} \le (\#\mathbb{F})^{v - 2}(d - j).
\end{equation*}
Consequently,
\begin{equation*}
 \#\{(r_0,\ldots,r_{v - 2},r_{v-1}) \in \mathbb{F}^v : h_j(r_0,\ldots,r_{v-2}) = 0\} \le (\#\mathbb{F})^{v - 1}(d - j).
\end{equation*}

If $h_j(r_0,\ldots,r_{v - 2}) \ne 0$, then $g(r_0,\ldots,r_{v-2},X_{v-1})$ is a nonzero univariate polynomial of degree $j$ (its leading term is $X_{v-1}^jh_j(r_0,\ldots,r_{v-2}))$. There are trivially at most $(\#\mathbb{F})^{v-1}$ tuples $(r_0,\ldots,r_{v-2}) \in \mathbb{F}^{v - 1}$ such that $h_j(r_0,\ldots,r_{v-2}) \ne 0$, and for each such tuple, there are at most $j$ elements $r_{v - 1}$ of $\mathbb{F}$ such that $g(r_0,\ldots,r_{v-1}) = 0$. This follows from the univariate case, since such $r_{v-1}$ are roots of a nonzero univariate polynomial of degree $j$. Hence,
\begin{equation*}
\#\{(r_0,\ldots,r_{v - 1}) \in \mathbb{F}^v :  h_j(r_0,\ldots,r_{v-2}) \ne 0 \,\, \text{and} \,\, g(r_0,\ldots,r_{v-1}) = 0 \} \le (\#\mathbb{F})^{v-1}j.
\end{equation*}
```

```{prf:remark} dimension-independence of the bound
:label: rem-dimension-independence-sz
A striking feature of the Schwartz-Zippel bound is that it depends on the degree of the polynomial but not on the number of variables. This reflects the fact that low degree, rather than low dimension, is what prevents a polynomial from vanishing on a large fraction of points.
```

```{prf:remark} dimension-independence of the bound

(i) The proof shows that $\mathbb{F}$ can actually be replaced by any integral domain $R$ (whether finite or infinite), provided we select $r_0, \ldots, r_{v - 1}$ from a finite subset $S \subseteq R$ and substitute $\#S$ for $\#\mathbb{F}$ in the denominator on the right-hand side. This generalization—the full result established by DeMillo and Lipton, Schwartz, and Zippel—is not required for our current purposes. 

(ii) Some people mistakenly refer to the base case as the much deeper fundamental theorem of algebra, which states that a non-zero polynomial of degree $d$ over $\mathbb{C}$ has exactly $d$ roots in $\mathbb{C}$, counted with multiplicity. 
```

````{prf:example}
:label: eg-roots

```{code-cell} python
from sympy import symbols, Poly, GF
from gkr import roots_example

X = symbols("X_:2")
g_small = Poly(X[0]*X[1] + 1, X, domain=GF(5, symmetric=False))

Y = symbols("X_:3")
g_big = Poly(Y[0]*Y[1] + Y[2]**2, Y, domain=GF(331, symmetric=False))

roots_example(polynomials=[g_small, g_big], time_out=3)
```
````

(sec-sum-check)=
## Sum-check protocol of Lund, Fortnow, Karloff, and Nisan, as described by Thaler

This is a description of the sum-check protocol as presented by Lund, Fortnow, Karloff, and Nisan in [@lfkn1992], with the exposition following Thaler’s treatment in [@tha2015]

**Initialization.** Given a nonzero $v$-variate polynomial $g$ over a finite field $\mathbb{F}$, let 
\begin{equation}
\label{eq-hypercube-sum}
 H := \sum_{b_0 \in \{0,1\}} \cdots \sum_{b_{v-1} \in \{0,1\}} g(b_0,\ldots,b_{v - 1}).
\end{equation}
Although verifier V does not know $g$, the number of indeterminates $v$ and upper bounds $\mathrm{deg}_{X_j}(g) \le d_j$ are known to V. Prover P claims that 
\begin{equation*}
H \overset{\mathsf{P}}{\underset{\text{claim}}{=}} H^*,
\end{equation*}
sending this claim to V, who needs to verify that this claim is true by interacting with P. 

```{prf:remark} notation and epistemic status
:label: rem-notation-and-epistemic-status
We distinguish between *ground-truth objects* and objects that the prover P merely **claims** to be ground-truth by using an asterisk. Thus, $H$ denotes the true value of the right-hand side of $(5)$, whereas $H^{*}$ denotes the value that P claims it to be. Any expression involving asterisked notation may therefore be false, and the verifier V's goal is to detect such inconsistencies with high probability.

To make the epistemic status of equalities explicit, we use the notation
\begin{equation*}
\overset{\mathsf{P}}{\underset{\text{claim}}{=}}
\end{equation*}
to denote an equality explicitly asserted by P, which may be false.

Finally, we use the notation
\begin{equation*}
\stackrel{?}{=}, \, \stackrel{?}{\le}
\end{equation*}
to denote an (in)equality that the verifier checks as part of the sum-check protocol. Such an equality is not asserted outright by P, but is instead *forced by the protocol transcript*: if P behaves honestly, the equality holds deterministically, whereas if P behaves dishonestly, the verifier accepts a false equality only with negligible probability.
```

**Round 0.** Let 
\begin{equation}
\label{eq-g_0}
g_0(X_0) := \sum_{b_1 \in \{0,1\}} \cdots \sum_{b_{v-1} \in \{0,1\}} g(X_0,b_1,\ldots,b_{v - 1}).
\end{equation}
P sends polynomial $g^*_0$ to V, claiming that 
\begin{equation*}
g^*_0 \overset{\mathsf{P}}{\underset{\text{claim}}{=}} g_0.
\end{equation*}
(Here, 'P sends a polynomial' means P sends an explicit representation, e.g., its coefficients.) If so, then 
\begin{equation*}
 \mathrm{deg}(g^*_0) \stackrel{?}{=} \mathrm{deg}(g_0) \le \mathrm{deg}_0(g) = d_0.
\end{equation*}
V verifies this: if $\mathrm{deg}(g^*_0) > d_0$ then V 'rejects' and the protocol terminates. Otherwise, we continue. If P's claims that 
\begin{equation*}
H \overset{\mathsf{P}}{\underset{\text{claim}}{=}} H^* \quad \text{and} \quad g^*_0 \overset{\mathsf{P}}{\underset{\text{claim}}{=}} g_0 
\end{equation*}
are both true, then 
\begin{equation}
\label{eq-h-star}
H^* \stackrel{?}{=} g^*_0(0) + g^*_0(1).
\end{equation}
This is because $H = g_0(0) + g_0(1)$. V verifies [](#eq-h-star), which is easy because $g^*_0$ is explicitly given as a univariate polynomial, even though V cannot compute $g_0$ efficiently from scratch. If [](#eq-h-star) does not hold, then V rejects and the protocol terminates. Otherwise, V chooses $r_0$ uniformly at random from $\mathbb{F}$, and sends it to P.

**Round j** ($1 \le j \le v - 1$). Let 
\begin{equation}
\label{eq-g-j}
g_j(X_j) := \sum_{b_{j+1} \in \{0,1\}} \cdots \sum_{b_{v-1} \in \{0,1\}} g(r_0,r_1,\ldots,r_{j-1},X_j,b_{j+1},\ldots,b_{v - 1}).
\end{equation}
P responds to V's random challenge $r_{j - 1}$ by sending V a polynomial $g^*_{j}$, claiming that 
\begin{equation*}
g^*_{j} \overset{\mathsf{P}}{\underset{\text{claim}}{=}} g_j. 
\end{equation*}
If so, then 
\begin{equation*}
 \mathrm{deg}(g^*_j) \stackrel{?}{=} \mathrm{deg}(g_j) \le \mathrm{deg}_j(g) = d_j.
\end{equation*}
V verifies this: if $\mathrm{deg}(g^*_j) > d_j$ then V 'rejects' and the protocol terminates. Otherwise, we continue. If P's previous claims that 
\begin{equation*}
g^*_{j-1} \overset{\mathsf{P}}{\underset{\text{claim}}{=}} g_{j - 1} \quad \text{and} \quad g^*_{j} \overset{\mathsf{P}}{\underset{\text{claim}}{=}} g_{j} 
\end{equation*}
are both true, then 
\begin{equation}
\label{eq-g-star-j}
g^*_{j - 1}(r_{j - 1}) \stackrel{?}{=} g^*_j(0) + g^*_j(1).
\end{equation}
This is because $g_{j - 1}(r_{j - 1}) = g_j(0) + g_j(1)$. To see this, note that by definition [](#eq-g-j),
\begin{equation*}
g_{j - 1}(r_{j - 1}) & = \sum_{b_{j} \in \{0,1\}} \cdots \sum_{b_{v-1} \in \{0,1\}} g(r_0,r_1,\ldots,r_{j-2},r_{j-1},b_{j},\ldots,b_{v - 1})
\end{equation*}
and 
\begin{equation*}
\begin{align}
g_j(0) + g_j(1) & = \sum_{b_{j+1} \in \{0,1\}} \cdots \sum_{b_{v-1} \in \{0,1\}} g(r_0,r_1,\ldots,r_{j-1},0,b_{j+1},\ldots,b_{v - 1})
 + \sum_{b_{j+1} \in \{0,1\}} \cdots \sum_{b_{v-1} \in \{0,1\}} g(r_0,r_1,\ldots,r_{j-1},1,b_{j+1},\ldots,b_{v - 1}) \\
 & = \sum_{b_{j} \in \{0,1\}} \cdots \sum_{b_{v-1} \in \{0,1\}} g(r_0,r_1,\ldots,r_{j-1},b_j,b_{j+1},\ldots,b_{v - 1}).
\end{align}
\end{equation*}
V verifies [](#eq-g-star-j), which is easy because $g_{j - 1}$ and $g_{j}$ are explicitly given as univariate polynomials, even though V cannot compute $g_{j - 1}$ and $g_{j}$ efficiently from scratch. If [](#eq-g-star-j) does not hold, V rejects and the protocol terminates. Otherwise, V chooses $r_j$ uniformly at random from $\mathbb{F}$, independently of $r_0,\ldots,r_{j-1}$, and sends it to P.

It helps to write out Round $v - 1$ explicitly. In the final round, P sends $g^*_{v - 1}$ to V, claiming that 
\begin{equation*}
g^*_{v - 1} \overset{\mathsf{P}}{\underset{\text{claim}}{=}} g_{v - 1},
\end{equation*}
where
\begin{equation}
\label{eq-g-v-minus-1}
g_{v - 1}(X_{v - 1}) := g(r_0,\ldots,r_{v - 2},X_{v - 1}).
\end{equation}
V verifies that $\mathrm{deg}(g^*_{v-1}) \stackrel{?}{\le} d_{v-1}$ and that $g^*_{v - 2}(r_{v - 2}) \stackrel{?}{=} g^*_{v - 1}(0) + g^*_{v - 1}(1)$. If either the degree bound or [](#eq-g-star-j) with $j = v - 1$ does not hold, V rejects and the protocol terminates. Otherwise, we continue.

**Final check.** V chooses $r_{v - 1}$ uniformly at random from $\mathbb{F}$, independently of $r_0,\ldots,r_{v-2}$, and verifies that 
\begin{equation}
\label{eq-g-star-v-minus-1}
g^*_{v - 1}(r_{v - 1}) \stackrel{?}{=} g(r_0,\ldots,r_{v - 2},r_{v - 1}),
\end{equation}
which holds if $g^*_{v-1} \overset{\mathsf{P}}{\underset{\text{claim}}{=}} g_{v-1}$ is true, in view of [](#eq-g-v-minus-1). If [](#eq-g-star-v-minus-1) does not hold, then V rejects. Otherwise, V accepts that $H \overset{\mathsf{P}}{\underset{\text{claim}}{=}} H^*$ is true and P passes the sum-check protocol. The protocol is complete. 

```{prf:remark} oracle access and evaluation
:label: rem-oracle-access-and-evaluation
In the original interactive-proof setting, the verifier is assumed to have **oracle access to the evaluation map induced by the polynomial** $g$. That is, although $g$ is formally an element of $\mathbb{F}[X_0,\ldots,X_{v-1}]$, the verifier may query the oracle at any point $\mathbf r \in \mathbb{F}^v$ and receive the value $g(\mathbf r)$. We will freely identify a polynomial with the polynomial function it induces on $\mathbb{F}^v$, since the verifier only ever interacts with $g$ through such evaluations.

In cryptographic implementations, this oracle access is replaced by a **binding commitment** to $g$ (or to a witness that uniquely determines $g$), together with a separate mechanism that allows the verifier to check claimed point evaluations. Concretely, when the verifier requests the value of $g$ at $(r_0,\ldots,r_{v-1})$ in the final check, the prover supplies both the value $g(r_0,\ldots,r_{v-1})$ and a proof that this value is consistent with the committed polynomial. This evaluation-consistency check is provided by the commitment scheme itself (for example, a polynomial commitment), and is not an invocation of the sum-check protocol.

Although the verifier may have oracle access to evaluations of $g$, computing $H$ directly from the oracle would require $2^v$ queries. The sum-check protocol shows how to reduce verification of this exponentially large sum to a linear number of oracle queries by exploiting the low-degree structure of $g$. 
```

````{prf:example}
:label: eg-sum-check

```{code-cell} python
from gkr import sum_check_example
sum_check_example(interactive=False)
```
````

(sec-soundness)=
## Why V should be convinced if P passes sum check

The sum-check protocol is _complete_: if P's claims are true, P will pass the protocol, assuming V's calculations are accurate. If V rejects, then at least one of P’s claims is inconsistent with the protocol checks.

In terms of _soundness_, a dishonest P may provide an incorrect value for the initial sum $H$ and still pass sum check. However, we can make the probability of this event—the soundness error—as small as desired by choosing a large field size $\#\mathbb{F}$ relative to $vd$. The probability of V being convinced of a false value for the initial sum is at most $vd/\#\mathbb{F}$.

To recap the sum-check protocol, we have 
\begin{equation*}
\begin{align}
 H & := \sum_{b_0 \, \in \, \{0,1\}} \cdots \sum_{b_{v - 1} \, \in \, \{0,1\}} g(b_0,\ldots,b_{v-1}) \\
 g_0(X_0) & := \sum_{b_1 \, \in \, \{0,1\}} \cdots \sum_{b_{v - 1} \, \in \, \{0,1\}} g(X_0,b_1,\ldots,b_{v-1}) 
\end{align}
\end{equation*}
Also, $r_0,\ldots,r_{v-1}$ are selected independently and uniformly at random from $\mathbb{F}$, and 
\begin{equation*}
\begin{align}
 g_j(X_j) & := \sum_{b_{j + 1} \, \in \, \{0,1\}} \cdots \sum_{b_{v - 1} \, \in \, \{0,1\}} g(r_0,\ldots,r_{j-1},X_j,b_{j+1},\ldots,b_{v-1}), \quad 0 \le j \le v - 2 \\
 g_{v-1}(X_{v-1}) & := g(r_0,\ldots,r_{v-2},X_{v-1})
\end{align}
\end{equation*}
Letting $d_j := \mathrm{deg}_{j}(g)$ for $0 \le j \le v - 1$, we have 
\begin{equation*}
 \mathrm{deg}(g_j) \le d_j, \quad 0 \le j \le v - 1.
\end{equation*}
Also,
\begin{equation*}
\begin{align}
 H & = g_0(0) + g_0(1) \\
 g_{j-1}(r_{j-1}) & = g_j(0) + g_j(1), \quad 1 \le j \le v - 1 \\
 g_{v-1}(r_{v-1}) & = g(r_0,\ldots,r_{v-1})
\end{align}
\end{equation*}
P claims that $H \overset{\mathsf{P}}{\underset{\text{claim}}{=}} H^*$ and $g_j \overset{\mathsf{P}}{\underset{\text{claim}}{=}} g_j^*$ for $0 \le j \le v - 1$, passing sum check if and only if the V's acceptance conditions hold:
\begin{align}
\label{eq-acceptance-criteria}
\begin{split}
\mathrm{deg}(g^*_j) & \stackrel{?}{\le} d_j, \quad 0 \le j \le v - 1, \\
 H^* & \stackrel{?}{=} g^*_0(0) + g^*_0(1) \\
 g^*_{j-1}(r_{j-1}) & \stackrel{?}{=} g^*_j(0) + g^*_j(1), \quad 1 \le j \le v - 1 \\
 g^*_{v-1}(r_{v-1}) & \stackrel{?}{=} g(r_0,\ldots,r_{v-1}) 
 \end{split}
\end{align}

Suppose P's claim for the value of the initial sum is false, i.e. in fact $H^* \ne H$, and that P passes sum-check in spite of this, i.e. V's acceptance conditions [](#eq-acceptance-criteria) all hold. If we had $g^*_0 = g_0$, then we'd have $g^*_0(0) + g^*_0(1) = g_0(0) + g_0(1) = H \ne H^*$, and so V would reject in Round 0. Therefore, $g^*_0 \ne g_0$. 

**Case 1.** $g^*_j \ne g_j$ for all $j$, $0 \le j \le v - 1$. In particular, $g^*_{v - 1} \ne g_{v - 1}$, and by the final acceptance condition,
\begin{equation*}
g^*_{v-1}(r_{v - 1}) = g_{v-1}(r_{v-1}) = g(r_0,\ldots,r_{v-1}).
\end{equation*}

**Case 2.** There is a minimal $k$, $1 \le k \le v - 1$, such that $g^*_{k-1} \ne g_{k-1}$ and $g^*_k = g_k$. By the acceptance condition of Round k,
\begin{equation*}
g^*_{k-1}(r_{k-1}) = g^*_k(0) + g^*_k(1) = g_k(0) + g_k(1) = g_{k - 1}(r_{k - 1}).
\end{equation*}

If Case 1 holds, take $k = v\,$; else take $k$ as in Case 2. In either case, there is a sequence of polynomials $g^*_0 \ne g_0,\ldots,g^*_{k-1} \ne g_{k-1}$, where $1 \le k \le v$, such that $g^*_{k-1}(r_{k-1}) = g_{k-1}(r_{k-1})$. Since $g_{k - 1}$ and $g^*_{k-1}$ are fixed after seeing the transcript $(r_0,\ldots,r_{k - 1})$ but _before_ $r_{k - 1}$ is chosen, they are independent of $r_{k - 1}$. Moreover, by the degree bounds, the (univariate) polynomial $g^*_{k - 1} - g_{k - 1}$ is nonzero and has degree at most $d_{k - 1} \le d := \mathrm{deg}(g)$. Therefore, since $r_{k - 1}$ is uniform in $\mathbb{F}$, 
\begin{equation*}
 \mathrm{Pr}[(g^*_{k - 1} - g_{k - 1})(r_{k-1}) = 0] \le \frac{d_{k - 1}}{\#\mathbb{F}} \le \frac{d}{\#\mathbb{F}} \tag{12}
\end{equation*}
by the univariate root bound (equivalently, the $v = 1$ case of Schwartz-Zippel [Schwartz-Zippel](#lem-schwartz-zippel)).

In each round $j \ge 1$, while V verifies that $g^*_{j-1}(r_{j-1}) = g^*_j(0) + g^*_j(1)$ (which could hold even if $g^*_{j-1}(r_{j-1}) \ne g_{j-1}(r_{j-1})$), P can check whether $g^*_{j - 1}(r_{j - 1}) = g_{j-1}(r_{j - 1})$. (This check is possible because the prover knows [or can compute from a witness defining] the underlying polynomial $g$ and can efficiently evaluate $g$ at arbitrary points. In particular, P can compute the value $g_{j - 1}(r_{j - 1})$ directly as a sum of evaluations of $g$ without ever expanding $g_{j - 1}$ symbolically.) If this equality holds, P can then revert to sending the 'true' polynomials $g^*_j = g_j$ for subsequent rounds $j$ and pass the sum-check protocol.

Finally, we note that V will accept a false value for the sum $H$ in the end in the event that the above occurs for any $k$, $1 \le k \le v$. Therefore, by the union bound and $(12)$, 
\begin{equation}
\label{eq-soundness-error-bound}
 \mathrm{Pr}[ \text{V accepts} \, | \, H^* \ne H] \le \frac{\sum_{j = 0}^{v - 1}d_j}{\#\mathbb{F}} \le \frac{vd}{\#\mathbb{F}}.
\end{equation}

```{prf:remark}
:label: rem-dishonest-prover-strategy
(i) If P provides a false value $H^*$ for the initial sum, their strategy to pass the sum-check protocol might involve finding a polynomial $g^*_0 \ne g_0$, of degree at most $d_0$, such that $g^*_0 - g_0$ has as many roots as possible in $\mathbb{F}$, while satisfying the condition $g^*_0(0) + g^*_0(1) = H^*$. This maximizes the likelihood that $g^*_0(r_0) = g_0(r_0)$. If this coincidence occurs, P can immediately switch to sending the 'true' polynomials to V, starting with $g^*_1 = g_1$, since the acceptance condition $g^*_0(r_0) = g^*_1(0) + g^*_1(1)$ will hold (because $g_0(r_0) = g_1(0) + g_1(1)$). Notably, the acceptance condition might still hold even if $g^*_0(r_0) \ne g_0(r_0)$. In that case, P would seek a polynomial $g^*_1 \ne g_1$ such that $g^*_1 - g_1$ has as many roots as possible in $\mathbb{F}$, and so on.

For instance, suppose $\mathbb{F}$ is a prime field of order $p$, and that $g_0$ has degree $d_0$, where $2 \le d_0 < p$. If $\{\alpha_0,\ldots,\alpha_{k-1}\}$ is any set of $k$ distinct field elements such that 
\begin{equation*}
[(0 - \alpha_0)\cdots (0 - \alpha_{k-1})] + [(1 - \alpha_0)\cdots (1 - \alpha_{k-1})] \ne 0,
\end{equation*}
and if $\alpha_{k} \in \mathbb{F}$ satisfies
\begin{equation*}
 (0 - \alpha_{k}) = \frac{[H^* - H] - [(1 - \alpha_0)\cdots (1 - \alpha_{k-1})]}{[(0 - \alpha_0)\cdots (0 - \alpha_{k-1})] + [(1 - \alpha_0)\cdots (1 - \alpha_{k-1})]},
\end{equation*}
then 
\begin{equation*}
[(0 - \alpha_0)\cdots (0 - \alpha_{k})] + [(1 - \alpha_0)\cdots (1 - \alpha_{k})] = H^* - H \ne 0.
\end{equation*}
If $\alpha_{k} \not\in \{\alpha_0,\ldots,\alpha_{k - 1}\}$, then we now have $k + 1$ distinct field elements $\alpha_0,\ldots,\alpha_k$ such that 
\begin{equation*}
g^*_0(X_0) := g_0(X_0) + (X_0 - \alpha_0)\cdots (X_0 - \alpha_{k})
\end{equation*}
satisfies 
\begin{equation*}
g^*_0(0) + g^*_0(1) = H^*.
\end{equation*}
A dishonest prover P may try to generate such a polynomial $g^*_0$ with $k$ as large as possible while not exceeding $d_0 - 1$. Then $g_0^*$ is distinct from $g_0$, has degree at most $d_0$, and $g^*_0(r_0) = g_0(r_0)$ if and only if $r_0 \in \{\alpha_0,\alpha_1,\ldots,\alpha_{k}\}$. That is, $\mathrm{Pr}[ g^*_0(r_0) = g_0(r_0) ] = (k+1)/\#\mathbb{F}$. Given that $g^*_0 \ne g_0$ and $\mathrm{deg}(g^*_0) \le \mathrm{deg}(g_0) \le \mathrm{deg}(g)$, this probability can be at most $d/\#\mathbb{F}$, by the [Schwartz-Zippel lemma](#lem-schwartz-zippel).

Alternatively, P could start with a multivariate polynomial $g^*$ different from $g$, where $\mathrm{deg}(g^*) \le d$ and the sum of $g^*$ over the Boolean hypercube equals $H^* \ne H$. P would then respond to all of V's challenges as though $g^*$ were the same as $g$. For the final check to pass, it would require that $g^*(r_0, \ldots, r_{v-1}) = g(r_0, \ldots, r_{v-1})$. P could maximize the likelihood of this by choosing a $g^* \ne g$ such that $g^* - g$ has as many roots as possible in $\mathbb{F}^v$. By the Schwartz-Zippel lemma, the probability that $(r_0, \ldots, r_{v - 1})$ is a root of $g^* - g$ remains at most $vd/\#\mathbb{F}$.

(ii) If the degree $d$ of $g$ were concealed from V, a dishonest P could inflate the degrees of the $g^*_j$ polynomials, increasing the probability of passing.

(iii) In the sum-check protocol, the degree $d$ of $g$ and the number of indeterminates $v$ are typically known to V beforehand, as they are determined by the structure of the problem being verified. These parameters are either agreed upon during the setup phase or are intrinsic to the function being evaluated (e.g., a [multilinear extension](./02-multilinear-extensions.md) or arithmetic circuit). The verifier ensures the prover's adherence to these parameters by checking that the submitted polynomials meet the degree constraints at each round.

```

````{prf:example}
:label: eg-sum-check-true-negative

```{code-cell} python
from sympy import symbols, Poly, GF
from gkr import sum_check_example

x, y, z = symbols("x y z")
g = Poly(x**2 + 2*x*y*z + y*z**2, x, y, z, domain=GF(331, symmetric=False))

sum_check_example(scenario={"poly": g, "claim": 7, "challenges": [6, 77, 4]})
```
````

````{prf:example}
:label: eg-sum-check-false-positive

```{code-cell} python
from sympy import symbols, Poly, GF
from gkr import sum_check_example

x, y, z = symbols("x y z")
g = Poly(x**2 + 2*x*y*z + y*z**2, x, y, z, domain=GF(331, symmetric=False))

sum_check_example(scenario={"poly": g, "claim": 7, "challenges": [2, 4, 1]})
```
````

(sec-complexity-and-proof-size)=
## Complexity and proof size

(subsec-verifier-runtime)=
### Verifier's runtime

In Round $j$ of the sum-check protocol, verifier V performs the following steps:
1. **Degree bound check:** verify that $\deg(g_j^*) \le d_j$.
2. **Consistency check:** verify that $g^*_{j-1}(r_{j-1}) = g^*_j(0) + g^*_j(1)$ (with $H^*$ substituted for $g^*_{-1}(r_{-1})$ in Round $0$, i.e. $H^* = g^*_0(0) + g^*_0(1)$).
3. Sample a random field element $r_j \in \mathbb{F}$.
4. **Final check:** verify that $g^*_{v-1}(r_{v-1}) = g(r_0,\ldots,r_{v-1})$.

Note that each $d_j := \deg_j(g)$ satisfies $d_j \le d$, where $d := \deg(g)$ is the total degree. Since each $g^*_j$ is a univariate polynomial, the work in Round $j$ is:

1. **Degree verification:** $O(t_j)$ field operations, where $t_j$ is the number of terms used to represent $g_j^*$ (e.g. the number of nonzero coefficients sent as pairs $(i,c_i)$). In the dense-coefficient representation this is $O(d)$.
2. **Evaluation check:** $O(d)$ field operations, because evaluating a univariate polynomial of degree at most $d$ can be done with $d$ multiplications and $d$ additions using Horner's method.
3. **Random field element generation:** this is often treated as $O(1)$ in protocol analyses (randomness is assumed available). In bit complexity, sampling a uniform element from $\mathbb{F}_{p^k}$ costs $O(k\log p)$ expected time (e.g. by rejection sampling in $\mathbb{F}_p$ and sampling $k$ coefficients for $\mathbb{F}_{p^k}$).
4. **Final round verification:** $O(d)$ field operations to compute $g^*_{v-1}(r_{v-1})$, plus the cost of obtaining and verifying the value $g(r_0,\ldots,r_{v-1})$ (one oracle query in the interactive-proof model, or one commitment opening verification in cryptographic implementations).

**Horner's method** is an efficient way to evaluate a polynomial given its coefficients. Rewrite a degree-$d$ polynomial
\begin{equation*}
P(X) = c_0 + c_1X + \cdots + c_d X^d
\end{equation*}
in nested form:
\begin{equation*}
P(X) = c_0 + X\bigl(c_1 + X\bigl(c_2 + \cdots + X(c_{d-1} + Xc_d)\cdots\bigr)\bigr).
\end{equation*}
Given $a \in \mathbb{F}$, set $A_d := c_d$ and compute recursively
\begin{equation*}
A_j = c_j + aA_{j+1}, \quad j = d-1, d-2,\ldots,0.
\end{equation*}
Then $P(a) = A_0$.

In practical implementations, $d$ is usually much smaller than $k\log p$, so random number generation can dominate if done online. To mitigate this, $r_0,\ldots,r_{v-1}$ are typically precomputed. We assume this is the case.

**Complexity of evaluating $g$ at a point.** A $v$-variate polynomial of total degree $d$ has at most
\begin{equation*}
\binom{v + d}{d}
\end{equation*}
monomials (nonzero terms): one for each exponent tuple $(e_0,\ldots,e_{v-1})$ with $e_0 + \cdots + e_{v-1} \le d$.

Using a monomial-sum representation, one can evaluate $g(r_0,\ldots,r_{v-1})$ by evaluating and summing all monomials. Each monomial evaluation requires $O(v)$ field operations (e.g. multiplying together the $v$ contributions $r_i^{e_i}$, with $e_i \le d$), so the total is
\begin{equation*}
O\!\left(\binom{v + d}{d}\cdot v\right).
\end{equation*}
Since $\binom{v + d}{d} = \Theta(v^d)$ for constant $d$, this becomes $O(v^{d+1})$ when $d$ is bounded (in many applications $d$ is $2$ or $3$).

**Verifier's total runtime.** Ignoring randomness generation (or assuming it is done offline), V's work across all rounds is
\begin{equation*}
O(vd),
\end{equation*}
plus the cost of a single oracle query / commitment opening verification for $g(r_0,\ldots,r_{v-1})$ in the final check.

(subsec-verifier-space-complexity)=
### Verifier's space complexity

The verifier generates and stores the $v$ random field elements $r_0, \ldots, r_{v-1}$, all of which must be retained because $g(r_0,\ldots,r_{v-1})$ is compared against $g^*_{v-1}(r_{v-1})$ in the final round.

In each round $j$ ($0 \le j \le v-1$), V receives a univariate polynomial $g_j^*$ of degree at most $d_j \le d$. If $g_j^*$ is sent in coefficient form, storing it requires $O(d+1)$ field elements (or $O(t_j)$ in sparse form). Evaluating $g_j^*$ at a point via Horner's method uses only $O(1)$ working memory beyond access to the coefficients (one running accumulator), and each polynomial is needed for at most two consecutive rounds.

Thus, measured in field elements, the total space complexity for the verifier is $O(v + d)$. If the field is $\mathbb{F}_{p^k}$ and each field element is represented using $O(k\log p)$ bits, then the bit space complexity is $O((v + d)k\log p)$.

(subsec-prover-runtime)=
### Prover's runtime

In Round $0$, an honest prover P computes
\begin{equation*}
g_0(X_0) := \sum_{b_1 \in \{0,1\}} \cdots \sum_{b_{v-1} \in \{0,1\}} g(X_0,b_1,\ldots,b_{v-1}).
\end{equation*}
Computing $g_0$ by direct summation requires evaluating $g$ at each point $(X_0,b_1,\ldots,b_{v-1})$ with $(b_1,\ldots,b_{v-1}) \in \{0,1\}^{v-1}$, i.e. at $2^{v-1}$ points. If $g$ is represented as a sum of monomials, evaluating $g$ at one point takes
\begin{equation*}
O\!\left(\binom{v + d}{d}\cdot v\right)
\end{equation*}
field operations, so the total cost in Round $0$ is
\begin{equation*}
O\!\left(\binom{v + d}{d}\cdot v \cdot 2^{v-1}\right).
\end{equation*}

In Round $j$, $1 \le j \le v-1$, an honest prover P computes
\begin{equation*}
g_j(X_j) := \sum_{b_{j+1} \in \{0,1\}} \cdots \sum_{b_{v-1} \in \{0,1\}} g(r_0,\ldots,r_{j-1},X_j,b_{j+1},\ldots,b_{v-1}),
\end{equation*}
which involves $2^{v-j-1}$ evaluations of (a specialization of) $g$. Using the same monomial-sum evaluation model, the work in Round $j$ is at most
\begin{equation*}
O\!\left(\binom{v + d}{d}\cdot v \cdot 2^{v-j-1}\right).
\end{equation*}
Summing across all rounds gives
\begin{equation*}
\sum_{j=0}^{v-1} O\!\left(\binom{v + d}{d}\cdot v \cdot 2^{v-j-1}\right)
= O\!\left(\binom{v + d}{d}\cdot v \cdot 2^v\right),
\end{equation*}
since $2^{v-1} + 2^{v-2} + \cdots + 1 = 2^v - 1$.

Equivalently,
\begin{equation*}
O\!\left(\binom{v + d}{d}\cdot v \cdot 2^v\right)
= O\!\left(\frac{v(v + d)^d 2^v}{d!}\right).
\end{equation*}
If $d$ is bounded, this simplifies to $O(v^{d+1}2^v)$, dominated by the exponential term $2^v$ arising from the Boolean hypercube.

(subsec-prover-space-complexity)=
### Prover's space complexity

P's space complexity is dominated by storing the multivariate polynomial $g(X_0,\ldots,X_{v-1})$. In a monomial-sum representation, $g$ may have up to $\binom{v + d}{d}$ nonzero terms, and each term requires storing a coefficient together with its exponent tuple. Thus the storage for $g$ is $O\!\left(\binom{v + d}{d}\right)$ field elements (up to constant-factor overhead for exponents).

During each round, P computes and sends a univariate polynomial $g_j(X_j)$ of degree at most $d$, which can be stored using $O(d+1)$ field elements. The working memory needed to sum over the hypercube can be kept small: P can stream through the $2^{v-j-1}$ points, maintaining only an accumulator for each coefficient of $g_j$ (i.e. $O(d+1)$ field elements), plus whatever temporary values are needed to evaluate $g$ at one point. If P precomputes the powers $r_i^0,\ldots,r_i^d$ for the specialized point, this adds $O(vd)$ field elements; otherwise the working memory can be treated as $O(1)$ beyond the accumulator.

Overall, the prover's space is dominated by the representation size of $g$, namely $O\!\left(\binom{v + d}{d}\right)$ field elements (or $O(v^d)$ for bounded $d$), plus lower-order terms such as $O(vd)$ and $O(d)$.

(subsec-proof-size)=
### Proof size

The **proof size** is the total amount of information communicated from the prover to the verifier during the sum-check protocol.

In each round $j$, $0 \le j \le v-1$, P sends a univariate polynomial of degree at most $d_j \le d$ to V. In coefficient form this requires at most $d+1$ field elements per round (or fewer in sparse form). Thus, counting only the sum-check messages, the total proof size is
\begin{equation*}
O(vd)
\end{equation*}
field elements. In bit terms, since each element of $\mathbb{F}_{p^k}$ can be encoded using $O(k\log p)$ bits, the sum-check proof size is
\begin{equation*}
O(vdk\log p)
\end{equation*}
bits. (In cryptographic implementations, one must additionally account for the size of the opening proof used in the final check to justify the value $g(r_0,\ldots,r_{v-1})$.)