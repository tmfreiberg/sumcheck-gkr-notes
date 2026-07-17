"""
Multilinear extensions.

Pure mathematics: no printing, no prompts, nothing interactive. Every function
here takes its inputs as arguments and returns a value.

The multilinear extension of f : {0,1}^v -> F is the unique multilinear
polynomial agreeing with f on the hypercube; this module builds it two ways
(via the beta/equality polynomial, and via a Lagrange basis) so the notebooks
can show they agree.

The worked example that used to live here -- 147 lines of prompts and
narration, which is a different job -- is now in gkr.examples.
"""
from itertools import product
from typing import Callable, List, Tuple, Union

import numpy as np
from sympy import Poly, isprime, symbols
from sympy.core.numbers import Integer
from sympy.core.symbol import Symbol
from sympy.polys.domains import GF
from sympy.polys.domains.finitefield import FiniteField
from sympy.polys.domains.modularinteger import ModularInteger


def tilde_beta_poly(
        field: FiniteField,
        v: int,
        X: Union[None, Tuple[Symbol]] = None,
        Y: Union[None, Tuple[Symbol]] = None
) -> Poly:
    """
    Computes the polynomial tilde_beta for a given finite field and number of variables.

    The polynomial tilde_beta is constructed from the terms (1 - x_j)(1 - y_j) + x_j * y_j
    for each pair of variables x_j and y_j, and then the product of these terms is taken over
    all variables to form the final polynomial.

    Args:
        field (FiniteField): The finite field over which the polynomial is defined.
                              It must be a prime-order field.
        v (int): The number of variables.
        X (Tuple[Symbol], optional): The symbolic variables for the x terms (default: None).
        Y (Tuple[Symbol], optional): The symbolic variables for the y terms (default: None).

    Returns:
        Poly: The final polynomial tilde_beta as the product of terms (1 - x_j)(1 - y_j) + x_j * y_j.

    Raises:
        ValueError: If the field's order is not prime.
    """
    # Ensure the field is prime
    if not isprime(field.mod):
        raise ValueError("Sorry, we're using SymPy and can only handle prime-order fields at present.")

    # Re-initialize field as GF(field.mod, symmetric=False)
    field = GF(field.mod, symmetric=False)

    # Default values for X and Y if not provided
    if X is None:
        X = symbols(f"x_:{v}")
    if Y is None:
        Y = symbols(f"y_:{v}")

    # Generate the arrays of polynomials for x and y variables
    XY = X + Y
    x: np.ndarray[Poly] = np.array([Poly(X[j], XY, domain=field) for j in range(v)])
    y: np.ndarray[Poly] = np.array([Poly(Y[j], XY, domain=field) for j in range(v)])

    # Compute the jth term for each pair (x_j, y_j) using (1 - x_j)(1 - y_j) + x_j * y_j
    jth_term: np.ndarray[Poly] = (1 - x) * (1 - y) + x * y

    # The final tilde_beta polynomial is the product of all jth terms
    tilde_beta: Poly = jth_term.prod()

    return tilde_beta

def multilinear_extension(
    field: FiniteField,
    v: int,
    func: Callable[[Tuple[int, ...]], int],
) -> Poly:
    """
    Creates the multilinear extension of a function on the Boolean hypercube {0,1}^v.

    Args:
        field (FiniteField): The finite field over which the function is defined.
        v (int): The number of variables.
        func (Callable[[Tuple[int, ...]], int]): A Boolean function defined on the hypercube {0,1}^v,
                                                 which is to be extended.

    Returns:
        Poly: The multilinear polynomial corresponding to the function 'func' on {0,1}^v.
    """
    # Initialize the finite field
    field = GF(field.mod, symmetric=False)

    if v == 0:
        # Degenerate case: return a constant polynomial
        b: Tuple[int, ...] = ()
        fb = field(func(b))
        # Introduce a dummy variable x_0
        X = symbols(f"x_:{v+1}")
        return Poly(fb, X, domain=field)
    else:
        # Create symbols for the x and y variables
        X = symbols(f"x_:{v}")
        Y = symbols(f"y_:{v}")

        # Compute the tilde_beta polynomial
        tilde_beta = tilde_beta_poly(field=field, v=v, X=X, Y=Y)

        # Initialize the multilinear extension polynomial to zero
        tilde_f = Poly(0, X, domain=field)

        # Iterate over all possible Boolean values for the v variables
        B = product([0, 1], repeat=v)
        for b in B:
            # Evaluate the function at the point b
            fb = field(func(b))

            # Create a mapping from y variables to the values in b
            b_point = {Y[j]: b[j] for j in range(v)}

            # Compute the term fb * tilde_beta evaluated at b
            term = fb * tilde_beta.subs(b_point)
            tilde_f += term

        return tilde_f


# Create Lagrange basis polynomials for two points, 0 and 1
def lagrange_basis(v: int,
                   field: FiniteField) -> List[Tuple[Poly, Poly]]:
    """Creates Lagrange basis polynomials for the points 0 and 1 in each variable."""
    field = GF(field.mod, symmetric=False)
    X: Tuple[Symbol, ...] = symbols(f"x_:{v}")
    basis = []
    for j in range(v):
        # Basis polynomials are (1 - x_j) for point 0 and x_j for point 1
        L_0 = Poly(1 - X[j], X, domain=field)
        L_1 = Poly(X[j], X, domain=field)
        basis.append((L_0, L_1))
    return basis


def multilinear_extension_using_lagrange_basis(
        field: FiniteField,
        v: int,
        func: Callable[[Tuple[int, ...]], Union[int, Integer, ModularInteger]],
) -> Poly:
    """The multilinear extension of a function on {0,1}^v, built from the
    Lagrange basis rather than from the beta polynomial.

    Same interface and same answer as multilinear_extension: the two agree
    because the multilinear extension is unique. Building it both ways is how
    you see that.
    """

    # Set the field with non-negative representatives
    field = GF(field.mod, symmetric=False)

    # Define symbolic variables
    X: Tuple[Symbol, ...] = symbols(f"x_:{v}")

    basis=lagrange_basis(v=v,
                         field=field,)

    # Initialize tilde_f as the zero polynomial over the given field
    tilde_f = Poly(0, X, domain=field)

    # Iterate over all combinations in the hypercube {0,1}^v
    for binary_vector in product([0, 1], repeat=v):
        # Compute func(binary_vector) for current binary input
        f_val = field(func(binary_vector))

        # Compute the product of Lagrange basis polynomials at `point`.
        # int(f_val): Poly rejects a ModularInteger as its constant term
        # ("not iterable"), but takes the plain integer and the domain.
        term = Poly(int(f_val), X, domain=field)
        for i in range(v):
            term *= basis[i][binary_vector[i]]

        # Add the term to tilde_f
        tilde_f += term

    return tilde_f


def evaluation_array(polynomial: Poly) -> np.ndarray:
    """
    Evaluate a polynomial over all points in GF(p)^v and store in a numpy array.

    Important: use `polynomial.gens` (not freshly-created symbols), otherwise SymPy may not
    substitute/evaluate correctly and can become extremely slow.
    """
    F = GF(int(polynomial.domain.mod), symmetric=False)
    gens = polynomial.gens
    v = len(gens)

    elements = [F(a) for a in range(F.mod)]
    shape = (len(elements),) * v
    results = np.zeros(shape, dtype=int)

    # Evaluate on every point
    for point in product(elements, repeat=v):
        # dict maps the *actual* generators to field elements
        subs = dict(zip(gens, point))
        val = polynomial.eval(subs)

        # Ensure we coerce into GF(p) then into int
        valF = F(val)
        idx = tuple(int(x) for x in point)
        results[idx] = int(valF)

    return results