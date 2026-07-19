---
title: Multilinear extensions
kernelspec:
  name: python3
  display_name: Python 3
---

(sec-introduction)=
## Introduction

In our [sum-check protocol](./01-sum-check-protocol.md) notebook, we followed Thaler's [@tha2015] presentation of the sum-check protocol, supplementing it with background material and interactive examples. 

In this notebook, we turn to **multilinear extensions**, which play a central role in the GKR interactive proof for circuit evaluation (Goldwasser, Kalai, and Rothblum [@gkr2008; @gkr2015]).

(sec-mle-definition)=
## Multilinear extensions: definition, existence, and uniqueness

Recall from [the definitions in the sum-check notebook](./01-sum-check-protocol.md#sec-terminology) that a multivariate polynomial $g$ is multilinear if the degree of $g$ in each variable is at most $1$. For example, over any field $\mathbb{F}$, the polynomial $g_1(X_0, X_1, X_2) = X_0 X_1 X_2 + X_1 X_2 + X_1$ is multilinear, while $g_2(X_0, X_1, X_2) = X_0 X_1 X_2 + X_1^2 X_2$ is not.

Also recall that a polynomial function is obtained by evaluating a polynomial at each input. (Over finite fields, distinct polynomials may define the same polynomial function, so it is useful to keep the distinction explicit.) If the polynomial is multilinear, we call it a multilinear polynomial function. For instance, let $f_1 : \mathbb{F}^3 \to \mathbb{F}$ be defined by $f_1(x_0, x_1, x_2) = g_1(x_0, x_1, x_2)$ and $f_2 : \mathbb{F}^3 \to \mathbb{F}$ by $f_2(x_0, x_1, x_2) = g_2(x_0, x_1, x_2)$. Then both $f_1$ and $f_2$ are polynomial functions, but only $f_1$ is a multilinear polynomial function.

```{prf:definition} multilinear extension
:label: def-mle
Let $\mathbb{F}$ be a finite field, $v$ a positive integer, and $f : \{0,1\}^v \to \mathbb{F}$ a function. A function $\tilde{f} : \mathbb{F}^v \to \mathbb{F}$ is called a _multilinear extension (MLE)_ of $f$ if:

1. $\tilde{f}$ is a multilinear polynomial function, and
2. $\tilde{f}(\mathbf{b}) = f(\mathbf{b})$ for all $\mathbf{b} \in \{0,1\}^v$
```

```{prf:example}
:label: eg-verify-mle
We can confirm that each $\tilde{f}$ provided below is indeed a multilinear extension of the corresponding function. We defer the general construction and proof of existence and uniqueness until afterward.

```{code-cell} python
from gkr import multilinear_extension_example

multilinear_extension_example(examples=[
    {"p": 11, "v": 2, "values": {(0,0): 1, (0,1): 2, (1,0): 3, (1,1): 4}},
]);
```

```{prf:definition} equality function
:label: def-equality
**Definition [equality function].** Given a field $\mathbb{F}$, a positive integer $v$, and $\mathbf{b} \in \{0,1\}^v$, define $\beta_{\mathbf{b}} : \{0,1\}^v \to \mathbb{F}$ by
\begin{equation*}
\beta_{\mathbf{b}}(\mathbf{b}') = \begin{cases} 1 & \text{if } \mathbf{b}' = \mathbf{b},\\ 0 & \text{otherwise} \end{cases}
\end{equation*}
Define $\tilde{\beta}_{\mathbf{b}} : \mathbb{F}^v \to \mathbb{F}$ by
\begin{equation*}
\tilde{\beta}_{\mathbf{b}}(y_0,\ldots,y_{v-1}) = \prod_{i = 0}^{v-1} \left[(1 - b_i)(1 - y_i) + b_i y_i\right], \quad \mathbf{b} = (b_0,\ldots,b_{v-1}).
\end{equation*}
Note that $\tilde{\beta}_{\mathbf{b}}$ is multilinear, as it is a product of linear polynomial functions in distinct variables. Also, for each $i$, the factor equals $1 - y_i$ when $b_i = 0$ and equals $y_i$ when $b_i = 1$, so $\tilde{\beta}_{\mathbf{b}}(\mathbf{b}') = \beta_{\mathbf{b}}(\mathbf{b}')$ for all $\mathbf{b}' \in \{0,1\}^v$. Thus, $\tilde{\beta}_{\mathbf{b}}$ is a multilinear extension of $\beta_{\mathbf{b}}$. More generally, define $\beta : \{0,1\}^v \times \{0,1\}^v \to \mathbb{F}$ by $\beta(\mathbf{b},\mathbf{b}') = \beta_{\mathbf{b}}(\mathbf{b}')$ and $\tilde{\beta} : \mathbb{F}^v \times \mathbb{F}^v \to \mathbb{F}$ by 
\begin{equation*}
\tilde{\beta}((x_0,\ldots,x_{v-1}),(y_0,\ldots,y_{v-1})) = \prod_{i = 0}^{v-1} \left[(1 - x_i)(1 - y_i) + x_i y_i\right].
\end{equation*}
Then $\tilde{\beta}$ is multilinear and $\tilde{\beta}(\mathbf{b}, \mathbf{b}') = \beta(\mathbf{b}, \mathbf{b}')$ for all $(\mathbf{b}, \mathbf{b}') \in \{0,1\}^v \times \{0,1\}^v$. Thus, $\tilde{\beta}$ is a multilinear extension of $\beta$. We call $\beta$ the _equality_ function on $\{0,1\}^v \times \{0,1\}^v$.
```

```{prf:remark}
:label: rem-beta-unique
(i) We stated that $\tilde{\beta}_{\mathbf{b}}$ is _a_ multilinear extension of $\beta_{\mathbf{b}}$ and $\tilde{\beta}$ is _a_ multilinear extension of $\beta$. In fact, multilinear extensions are unique by the next proposition, so we may say _the_ multilinear extension in both cases. 

(ii) Technically, we defined multilinear extensions for functions defined on $\{0,1\}^v$ as functions defined on $\mathbb{F}^v$. Here, we identify the domain of $\beta$ with $\{0,1\}^{2v}$ and that of $\tilde{\beta}$ with $\mathbb{F}^{2v}$. 

(iii) The function $\beta$ is an indicator function for the diagonal in $\{0,1\}^v\times\{0,1\}^v$, and $\tilde{\beta}$ agrees with it on Boolean inputs. However, $\tilde{\beta}$ is not an equality test on all of $\mathbb{F}^v$ in general. For example, over $\mathbb{F}_5$ one has
\begin{equation*}
\tilde{\beta}((0,2),(0,2)) = 0 \quad \text{and} \quad \tilde{\beta}((0,0),(2,2)) = 1,
\end{equation*}
so $\tilde{\beta}$ can vanish even when its two inputs are equal, and can be $1$ even when they are different.
```

The proof of the existence part of the following result shows how to use $\tilde{\beta}$ to construct a multilinear extension of a given function $f : \{0,1\}^v \to \mathbb{F}$. The result also establishes uniqueness, so that we may speak of _the_ multilinear extension of $f$.

```{prf:proposition}
:label: prop-mle-exists-unique
Let $\mathbb{F}$ be a finite field, $v$ a positive integer, and $f : \{0,1\}^v \to \mathbb{F}$ a function. There exists a _unique_ multilinear extension $\tilde{f} : \mathbb{F}^v \to \mathbb{F}$ of $f$.
```

```{admonition} Proof
:class: proof
Define $\tilde{f} : \mathbb{F}^v \to \mathbb{F}$ by 
\begin{equation*}
 \tilde{f}(x_0,\ldots,x_{v - 1}) = \sum_{\mathbf{b} \, \in \, \{0,1\}^v} f(\mathbf{b}) \tilde{\beta}_{\mathbf{b} }(x_0,\ldots,x_{v-1}).
\end{equation*}
Then $\tilde{f}(\mathbf{b} ) = f(\mathbf{b} )$ for all $\mathbf{b}  \in \{0,1\}^v$. Since each term in the sum is a product of linear polynomial functions in distinct variables, $\tilde{f}$ is multilinear.

To show uniqueness, let $\tilde{g} : \mathbb{F}^v \to \mathbb{F}$ be any multilinear extension of $f$. Consider the polynomial function $h := \tilde{g} - \tilde{f}$. Since $\tilde{g}$ and $\tilde{f}$ are both multilinear, $h$ can be written as

\begin{equation*}
h(x_0, \ldots, x_{v-1}) = \sum_{J \subseteq \{0, \ldots, v-1\}} c_J \prod_{j \, \in \, J} x_j,
\end{equation*}

where each $c_J \in \mathbb{F}$ and $J$ is a subset of $\{0, \ldots, v-1\}$. We can establish a one-to-one correspondence between bit strings $\mathbf{b} = (b_0, \ldots, b_{v-1}) \in \{0,1\}^v$ and subsets $J \subseteq \{0, \ldots, v - 1\}$ by defining

\begin{equation*}
J(\mathbf{b}) = \{j : b_j = 1\}.
\end{equation*}

For each $\mathbf{b} \in \{0,1\}^v$ and subset $J$ of $\{0,\ldots,v-1\}$, the product $\prod_{j \, \in \, J} b_j$ acts as an indicator function, being $1$ if $J \subseteq J(\mathbf{b})$ and $0$ otherwise. (Note that the empty product is equal to $1$ and $J((0,\ldots,0)) = \emptyset$.) Thus, we find that for each $\mathbf{b} \in \{0,1\}^v$,

\begin{equation*}
\sum_{J \subseteq J(\mathbf{b})} c_J = \sum_{J \subseteq \{0, \ldots, v-1\}} c_J \prod_{j \, \in \, J} b_j = h(\mathbf{b}) = (\tilde{g} - \tilde{f})(\mathbf{b}) = 0.
\end{equation*}

It immediately follows that $c_{\emptyset} = 0$. Next, by considering bit strings $\mathbf{b}$ of the form $(0, \ldots, 1, \ldots, 0)$ — with a $1$ in the $j$-th position and $0$ in all other positions — we find that $c_{\{j\}} = 0$ for each $j = 0, \ldots, v - 1$. Extending this to bit strings containing exactly two $1$ s shows that $c_J = 0$ for all two-element subsets $J$ of $\{0, \ldots, v - 1\}$. Continuing in this manner, we conclude that $c_J = 0$ for every subset $J$, which implies that $h$ is identically zero.



Therefore, $\tilde{g} = \tilde{f}$, proving that the multilinear extension is unique.
```

```{prf:remark}
:label: rem-mle-agree
If two functions $f: \{0,1\}^v \to \mathbb{F}$ and $g : \{0,1\}^v \to \mathbb{F}$ differ anywhere, their multilinear extensions $\tilde{f}$ and $\tilde{g}$ will differ at many points. If $f$ and $g$ are different, the proportion of points in $\{0,1\}^v$ at which they agree may be up to $1 - 2^{-v}$. Regardless, by the [Schwartz-Zippel lemma](./02-multilinear-extensions.md#lem-schwartz-zippel), the proportion of points in $\mathbb{F}^v$ at which $\tilde{f}$ and $\tilde{g}$ agree can be at most $v/\#\mathbb{F}$. (If $\tilde f-\tilde g$ is multilinear and nonzero, its total degree is at most $v$.) We may think of multilinear extensions as 'discrepancy amplifiers' when $\#\mathbb F$ is large compared to $v$.
```

````{prf:example}
:label: eg-mle-compare
We extend a function f : {0,1}^2 -> GF(11) to a function f̃ : GF(11)^2 -> GF(11).

```{code-cell} python
from gkr import multilinear_extension_example

multilinear_extension_example(
    compare=True,
    examples=[
        {"p": 11, "v": 2, "values": {(0,0): 1, (0,1): 2, (1,0): 3, (1,1): 4}},
        {"p": 11, "v": 2, "values": {(0,0): 1, (0,1): 2, (1,0): 3, (1,1): 3}},
    ],
);
```
````

````{prf:example}
:label: eg-mle-compare-three-variables
A comparison in three indeterminates, where the evaluation table has $13^3 = 2197$ entries and so is too large to display.

```{code-cell} python
from gkr import multilinear_extension_example

multilinear_extension_example(
    compare=True,
    examples=[
        {"p": 13, "v": 3, "values": {
            (0,0,0): 2, (0,0,1): 3, (0,1,0): 4, (0,1,1): 5,
            (1,0,0): 6, (1,0,1): 7, (1,1,0): 8, (1,1,1): 9}},
        {"p": 13, "v": 3, "values": {
            (0,0,0): 2, (0,0,1): 3, (0,1,0): 4, (0,1,1): 4,
            (1,0,0): 5, (1,0,1): 6, (1,1,0): 7, (1,1,1): 8}},
    ],
);
```
````

(sec-mle-properties)=
## Properties of multilinear extensions

```{prf:proposition}
:label: prop-mle-linear
**Proposition.** Let $\mathbb{F}$ be a finite field and $v$ a positive integer. Let $f : \{0,1\}^v \to \mathbb{F}$ and $g : \{0,1\}^v \to \mathbb{F}$ have respective multilinear extensions $\tilde{f} : \mathbb{F}^v \to \mathbb{F}$ and $\tilde{g} : \mathbb{F}^v \to \mathbb{F}$. Finally, let $c$ and $d$ be elements of $\mathbb{F}$. Then 
\begin{equation*}
\widetilde{cf + dg} = c\tilde{f} + d\tilde{g}.
\end{equation*}
```

```{admonition} Proof
:class: proof
First of all, $cf + dg$ is a multilinear function. (Exercise.) Given any $\mathbf{b} \in \{0,1\}^v$, we have
\begin{equation*}
 (c\tilde{f} + d\tilde{g})(\mathbf{b}) = c\tilde{f}(\mathbf{b}) + d\tilde{g}(\mathbf{b}) = cf(\mathbf{b}) + dg(\mathbf{b}) = (cf + dg)(\mathbf{b}),
\end{equation*}
where the second equality holds because $\tilde{f}$ is the multilinear extension of $f$ and $\tilde{g}$ is the multilinear extension of $g$. Therefore, $c\tilde{f} + d\tilde{g}$ is _a_ multilinear extension of $cf + dg$. By uniqueness of multilinear extensions, it is _the_ multilinear extension of $cf + dg$, i.e., $\widetilde{cf + dg} = c\tilde{f} + d\tilde{g}$.
```

What about the multilinear extension of the product of two functions? In general, the product of multilinear functions is not multinear, so there is no immediate analog of the above proposition for products. For example, define 
\begin{equation*}
f : \{0,1\}^2 \to \mathbb{F} \quad \text{by} \quad f(0,0) = f(0,1) = f(1,0) = 0 \quad \text{and} \quad f(1,1) = 1,
\end{equation*}
and define 
\begin{equation*}
g : \{0,1\}^2 \to \mathbb{F} \quad \text{by} \quad g(0,0) = 0 \quad \text{and} \quad g(0,1) = g(1,0) = g(1,1) = 1.
\end{equation*}
Then $\tilde{f} : \mathbb{F}^2 \to \mathbb{F}$ is given by 
\begin{equation*}
\tilde{f}(x,y) = xy
\end{equation*}
and $\tilde{g} : \mathbb{F}^2 \to \mathbb{F}$ is given by 
\begin{equation*}
\tilde{g}(x,y) = x + y - xy. 
\end{equation*}
However, $fg = f$, whence $\widetilde{fg} = \tilde{f}$, but $(\tilde{f}\tilde{g})(x,y) = xy(x + y - xy)$, which is not multilinear. Hence $\tilde{f}\tilde{g}$ is not a multilinear extension of $fg$.

```{prf:proposition}
:label: prop-mle-product
Let $\mathbb{F}$ be a finite field and $v$ a positive integer. Let $f : \{0,1\}^v \to \mathbb{F}$ and $g : \{0,1\}^v \to \mathbb{F}$ have respective multilinear extensions $\tilde{f} : \mathbb{F}^v \to \mathbb{F}$ and $\tilde{g} : \mathbb{F}^v \to \mathbb{F}$. Let $\{j_0,\ldots,j_{u-1}\} \cup \{j_{u},\ldots,j_{v-1}\}$ be a partition of $\{0,\ldots,v - 1\}$, and suppose that there exist functions $f_0 : \{0,1\}^u \to \mathbb{F}$ and $g_0 : \{0,1\}^{v - u} \to \mathbb{F}$ such that $f(b_0,\ldots,b_{v-1}) = f_0(b_{j_0},\ldots,b_{j_{u-1}})$ and $g(b_0,\ldots,b_{v-1}) = g_0(b_{j_{u}},\ldots,b_{j_{v-1}})$ for all $b_0,\ldots,b_{v-1} \in \{0,1\}^v$. Then 
1. For all $(x_0,\ldots,x_{v-1}) \in \mathbb{F}^v$,
\begin{equation*}
\tilde{f}(x_0,\ldots,x_{v-1}) = \widetilde{f_0}(x_{j_0},\ldots,x_{j_{u - 1}}) \quad \text{and} \quad \tilde{g}(x_0,\ldots,x_{v-1}) = \widetilde{g_0}(x_{j_u},\ldots,x_{j_{v - 1}})
\end{equation*}
2. $\widetilde{fg} = \widetilde{f}\widetilde{g}$
```

```{admonition} Proof
:class: proof
First note that the multilinear extension of the function that is identically equal to $1$ on $\{0,1\}^w$ is the function that is identically equal to $1$ on $\mathbb{F}^w$. We denote it by $\tilde{\mathbf{1}}$. Let $(x_0,\ldots,x_{v-1}) \in \mathbb{F}^v$. Recalling the construction for multilinear extensions, we have:
\begin{align}
\label{eq-prod-mle}
 \tilde{f}(x_0,\ldots,x_{v-1}) 
 & = \sum_{b_0 \in \{0,1\}} \cdots \sum_{b_{v-1} \in \{0,1\}} f(b_0,\ldots,b_{v-1}) \prod_{i \, = \, 0}^{v-1} \left[(1 - b_i)(1 - x_i) + b_ix_i\right] \\
& =  \sum_{b_{0} \in \{0,1\}} \cdots \sum_{b_{v - 1} \in \{0,1\}} f_0(b_{j_0},\ldots,b_{j_{u-1}}) \prod_{i \, = \, 0}^{u-1} \left[(1 - b_{j_i})(1 - x_{j_i}) + b_{j_i}x_{j_i}\right] \prod_{i \, = \, u}^{v-1} \left[(1 - b_{j_i})(1 - x_{j_i}) + b_{j_i}x_{j_i}\right] \\
& = \sum_{b_{j_0} \in \{0,1\}} \cdots \sum_{b_{j_{u-1}} \in \{0,1\}} \left\{f_0(b_{j_0},\ldots,b_{j_{u-1}})\prod_{i \, = \, 0}^{u-1} \left[(1 - b_{j_i})(1 - x_{j_i}) + b_{j_i}x_{j_i}\right]\right\} \sum_{b_{j_{u}} \in \{0,1\}} \cdots \sum_{b_{j_{v-1}} \in \{0,1\}} \prod_{i \, = \, u}^{v-1} \left[(1 - b_{j_i})(1 - x_{j_i}) + b_{j_i}x_{j_i}\right] \\
& = \widetilde{f_0}(x_{j_0},\ldots,x_{j_{u-1}}) \widetilde{\mathbf{1}}(x_{j_u},\ldots,x_{j_{v - 1}}) \\
 & = \widetilde{f_0}(x_{j_0},\ldots,x_{j_{u-1}}).
\end{align}
Similarly, $\tilde{g}(x_0,\ldots,x_{v-1}) = \widetilde{g_0}(x_{j_u},\ldots,x_{j_{v - 1}})$. More generally,  

\begin{equation*}
\begin{align}
 \widetilde{fg}(x_0,\ldots,x_{v-1}) 
 & = \sum_{b_0 \in \{0,1\}} \cdots \sum_{b_{v-1} \in \{0,1\}} (fg)(b_0,\ldots,b_{v-1}) \prod_{i \, = \, 0}^{v-1} \left[(1 - b_i)(1 - x_i) + b_ix_i\right] \\
& =  \sum_{b_0 \in \{0,1\}} \cdots \sum_{b_{v-1} \in \{0,1\}} f_0(b_{j_0},\ldots,b_{j_{u-1}}) g_0(b_{j_u},\ldots,b_{j_{v-1}})\prod_{i \, = \, 0}^{u-1} \left[(1 - b_{j_i})(1 - x_{j_i}) + b_{j_i}x_{j_i}\right] \prod_{i \, = \, u}^{v-1} \left[(1 - b_{j_i})(1 - x_{j_i}) + b_{j_i}x_{j_i}\right] \\
& = \sum_{b_{j_0} \in \{0,1\}} \cdots \sum_{b_{j_{u-1}} \in \{0,1\}} \left\{f_0(b_{j_0},\ldots,b_{j_{u-1}})\prod_{i \, = \, 0}^{u-1} \left[(1 - b_{j_i})(1 - x_{j_i}) + b_{j_i}x_{j_i}\right]\right\} \sum_{b_{j_{u}} \in \{0,1\}} \cdots \sum_{b_{j_{v-1}} \in \{0,1\}} \left\{ g_0(b_{j_u},\ldots,b_{j_{v-1}}) \prod_{i \, = \, u}^{v-1} \left[(1 - b_{j_i})(1 - x_{j_i}) + b_{j_i}x_{j_i}\right] \right\}\\
& = \widetilde{f_0}(x_{j_0},\ldots,x_{j_{u-1}}) \widetilde{g_0}(x_{j_u},\ldots,x_{j_{v-1}}) \\
 & = \tilde{f}(x_0,\ldots,x_{v-1}) \tilde{g}(x_0,\ldots,x_{v-1})
\end{align}
\end{equation*}
by [](#eq-prod-mle). Note that since $\widetilde{f_0}(x_{j_0},\ldots,x_{j_{u-1}})$ and $\widetilde{g_0}(x_{j_u},\ldots,x_{j_{v-1}})$ are multilinear functions involving disjoint sets of variables, their product is indeed multilinear.
```

(sec-mle-special)=
## Multilinear extensions of special functions

We have [already seen](#def-equality) the 'equality' function $\beta$ and its multilinear extension $\tilde{\beta}$. It is also clear that if $c \in \mathbb{F}$ and $f : \{0,1\}^v \to \mathbb{F}$ is defined by $f(\mathbf{b}) = c$ for all $\mathbf{b} \in \{0,1\}^v$, then $\tilde{f} : \mathbb{F}^v \to \mathbb{F}$ defined by $\tilde{f}(\mathbf{x}) = c$ for all $\mathbf{x} \in \mathbb{F}^v$ is the multilinear extension of $f$. (We used this fact in the case $c = 1$ in the above proof.)

Let $\mathbb{F}$ be given. We can define Boolean operators on $\{0,1\}$ and extend their definitions to all of $\mathbb{F}$ as follows.
* **Negation.** Define $\mathrm{NEG}: \{0,1\} \to \mathbb{F}$ by $\mathrm{NEG}(0) = 1$ and $\mathrm{NEG}(1) = 0$. Then $\widetilde{\mathrm{NEG}} : \mathbb{F} \to \mathbb{F}$ is given by $\widetilde{\mathrm{NEG}}(x) = 1 - x$.
* **Conjunction.** Define $\mathrm{AND} : \{0,1\}^2 \to \mathbb{F}$ by $\mathrm{AND}(0,0) = \mathrm{AND}(0,1) = \mathrm{AND}(1,0) = 0$ and $\mathrm{AND}(1,1) = 1$. Then $\widetilde{\mathrm{AND}}: \mathbb{F}^2 \to \mathbb{F}$ is given by $\widetilde{\mathrm{AND}}(x_0,x_1) = x_0x_1$.
* **Disjunction.** Define $\mathrm{OR} : \{0,1\}^2 \to \mathbb{F}$ by $\mathrm{OR}(0,1) = \mathrm{OR}(1,0) = \mathrm{OR}(1,1) = 1$ and $\mathrm{OR}(0,0) = 0$. Then $\widetilde{\mathrm{OR}}: \mathbb{F}^2 \to \mathbb{F}$ is given by $\widetilde{\mathrm{OR}}(x_0,x_1) = x_0 + x_1 - x_0x_1$.
* **Exclusive OR.** Define $\mathrm{XOR} : \{0,1\}^2 \to \mathbb{F}$ by $\mathrm{XOR}(0,0) = \mathrm{XOR}(1,1) = 0$ and $\mathrm{XOR}(1,0) = \mathrm{XOR}(0,1) = 1$. Then $\widetilde{\mathrm{XOR}}: \mathbb{F}^2 \to \mathbb{F}$ is given by $\widetilde{\mathrm{XOR}}(x_0,x_1) = x_0 + x_1 - 2x_0x_1$.

Note that these extensions agree with the Boolean operators only on $\{0,1\}^2$; over $\mathbb{F}^2$ they define polynomial relaxations rather than Boolean operations.
