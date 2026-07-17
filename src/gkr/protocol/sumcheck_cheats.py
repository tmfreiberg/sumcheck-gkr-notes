"""
Cheat constructions for a prover whose carried claim is false.
"""
from __future__ import annotations

import random
import time
from typing import Any, List, Optional, Tuple, Union

from sympy import Poly, isprime
from sympy.polys.domains.modularinteger import ModularInteger


def dishonest_polynomial_with_boundary_condition(g_0: Poly,
                                                 H_star: Union[int, ModularInteger],
                                                 max_degree: Union[None, int] = None,
                                                 random_roots: bool = False,
                                                 timeout: Optional[int] = None,) -> Tuple[Union[None, Poly], Union[None, List[Union[int, ModularInteger]]], Union[None, bool]]:
    """
    Constructs a modified polynomial g_0^* recursively under a boundary condition.

    This function modifies the polynomial g_0 such that:
        - g_0^* is distinct from g_0,
        - g_0^*(0) + g_0^*(1) = H_star (the `boundary condition`),
        - deg(g_0^*) <= deg(g_0) or is limited by `max_degree` if specified.

    If H_star = g_0(0) + g_0(1), the boundary condition is trivial, and the function calls
    `dishonest_polynomial_no_boundary_conditions` to construct g_0^* without the boundary constraint.

    Degenerate cases are handled:
        - If g_0 is constant or the field characteristic is 2, specific logic ensures that
          g_0^*(0) + g_0^*(1) = H_star while respecting field constraints.
        - If deg(g_0) = 0, g_0^* is constructed as a constant polynomial.
        - If deg(g_0) = 1, g_0^* is linear or constant, satisfying the required sum.

    Args:
        g_0 (Poly): A univariate polynomial defined over a prime field.
        H_star (Union[int, ModularInteger]): The target sum g_0^*(0) + g_0^*(1).
        max_degree (Union[None, int], optional): The maximum allowable degree for the constructed polynomial.
                                                 Defaults to None.
        random_roots (bool, optional): Whether to randomly select roots in the construction
                                       (used when H_star = g_0(0) + g_0(1)).
        timeout (Optional[int], optional): Maximum allowed time in seconds for constructing g_0^*.
                                           If exceeded, the function stops the process early and
                                           returns a timeout flag.

    Returns:
        Tuple[Union[None, Poly], Union[None, List[Union[int, ModularInteger]]], Union[None, bool]]:
            - The first element is the constructed polynomial (Poly) or None if no polynomial can be constructed.
            - The second element is the list of roots (as integers or modular integers) or None if no roots are found.
            - The third element is a boolean flag indicating whether a timeout occurred (True if timeout, None otherwise).

    Raises:
        ValueError: If g_0.domain is not a prime field.

    Notes:
        - If H_star = g_0(0) + g_0(1), the function reverts to `dishonest_polynomial_no_boundary_conditions`.
        - The recursive construction starts with alpha_0 = 0 and iteratively computes alpha_k
          to maximize the number of distinct roots, stopping early if no further roots can be added
          or the timeout is exceeded.
        - For fields of characteristic 2, the construction accounts for field-specific behavior
          and ensures validity even in edge cases.
    """
    # Ensure the field is a prime field
    field = g_0.domain
    if not isprime(field.mod):
        raise ValueError("g_0 must be defined over a prime field.")

    # Compute H as a field element
    H = field.convert(g_0.eval(0) + g_0.eval(1))
    # Convert H^* to a field element (if it isn't already)
    H_star = field.convert(H_star)
    # If H_star equals H, there is effectively no boundary condition
    if H_star == H:
        g_0_star, roots_of_g_0_star_minus_g = dishonest_polynomial_no_boundary_conditions(g=g_0, max_degree=max_degree, random_roots=random_roots)
        return g_0_star, roots_of_g_0_star_minus_g, None

    # Compute the difference delta in the field
    delta = H_star - H
    # Field size
    p = field.mod
    # d will be max potential degree of output g_0_star: cannot exceed p - 1 but otherwise should be as large as deg(g_0) (or max_degree, if specified) if possible
    if max_degree:
        assert g_0.degree() <= max_degree, "max_degree must be greater than or equal to deg(g_0)"
        d = min(max_degree, p - 1)
    else:
        d = min(g_0.degree(), p - 1)
    # Deal with some degenerate cases
    if d < 0: # g_0 is the zero polynomial and g_0_star must also be. But we require g_0_star to be distinct from g_0
        return None, None, None
    if d == 0: # g_0 is constant (possibly zero) and g_0_star must also be---a different constant.
        if p > 2:
            g_0_star = Poly(H_star / field.convert(2), g_0.gens[0], domain=field)  # So that 2*g_0_star = H_star
            if g_0_star == g_0:
                return None, None, None
            return g_0_star, [], None
        # Now we're in the case p = 2
        if H_star == field.one:
            return None, None, None  # For any constant polynomial g_0_star over Z/2Z, 2*g_0_star = 0 mod 2
        # H_star == field.zero
        g_0_star = Poly(field.zero, g_0.gens[0], domain=field)
        if g_0_star == g_0:
            return None, None, None
        return g_0_star, [], None
    if d == 1: # g_0_star must be constant or linear and satisfy g_0_star(0) + g_0_star(1) = H_star
        if p == 2: # g_0 is either x or x + 1 or 0 or 1
            if g_0.degree() == 1: # g_0 is either x or x + 1
                g_0_star = Poly(g_0 + 1, g_0.gens[0], domain=field)
                if field.convert(g_0_star.eval(0) + g_0_star.eval(1)) == H_star:
                    return g_0_star, [], None
                # Otherwise, g_0_star must be constant
                if H_star == field.one:
                    return None, None, None
                g_0_star = field.zero
                return g_0_star, [g_0.eval(0)], None
            # g_0 is 0 or 1
            if H_star == field.zero:
                g_0_star = Poly(0, g_0.gens[0], domain=field)
                if g_0_star == g_0:
                    return None, None, None
                return g_0_star, [], None
            # H_star == field.one
            g_0_star = Poly(g_0.gens[0], g_0.gens[0], domain=field)
            return g_0_star, [g_0.eval(0)], None
        # Now we're in the case p > 2
        # We'll return a linear polynomial g_0_star = a_star*x + b_star
        # We have to ensure g_0_star(0) + g_0_star(1) = a_star + 2*b_star = H_star
        # We'll choose b_star = b + 1 where g_0(x) = a*x + b. This guarantees g_0_star is different from g_0
        b_star = field.convert(g_0.eval(0) + 1)
        a_star = field.convert(H_star - 2*b_star)
        g_0_star = Poly(a_star*g_0.gens[0] + b_star, g_0.gens[0], domain=field)
        delta_a = a_star - g_0.nth(1)
        if delta_a%p != 0:
            roots = [1/field.convert(-delta_a)]
        else:
            roots = None
        return g_0_star, roots, None
    # Helper function to compute alpha_k
    def compute_alpha_k(alpha_list):
        """Compute the next alpha_k."""
        prod_0 = field.convert(1)
        prod_1 = field.convert(1)
        for alpha in alpha_list:
            prod_0 *= (field.convert(0) - alpha)
            prod_1 *= (field.convert(1) - alpha)
        denominator = prod_0 + prod_1
        if denominator == 0:
            return None  # Cannot compute alpha_k due to zero denominator
        numerator = delta - prod_1
        alpha_k = - numerator / denominator
        return field.convert(alpha_k)

    # Recursive construction of sets of alpha
    best_alpha_list: List[int] = []  # Track the best (longest) list of alpha
    out_of_time = False
    if timeout is not None:
        tic = time.time()  # Start timing
    for alpha_0 in range(p):  # Iterate over possible starting points for alpha_0
        alpha_list = [field.convert(alpha_0)]  # Start with alpha_0
        for _ in range(d - 1):  # Limit the length to d
            alpha_k = compute_alpha_k(alpha_list)
            if alpha_k is None or alpha_k in alpha_list:
                break  # Stop if alpha_k is invalid or not distinct
            alpha_list.append(alpha_k)
        if len(alpha_list) > len(best_alpha_list):
            best_alpha_list = alpha_list
        if timeout is not None:
            toc = time.time()  # Current time
            out_of_time = toc - tic > timeout
        else:
            out_of_time = False
        if len(best_alpha_list) == d or out_of_time:
            break  # Stop early if we find a list of length d, or if timeout is exceeded
    if not best_alpha_list:
        if timeout: # found nothing useful in the time given
            return None, None, out_of_time
        else: # found nothing useful
            return None, None, None
    # Construct the correction term using the best alpha list
    correction_term = Poly(1, g_0.gens[0], domain=field)
    for alpha in best_alpha_list:
        correction_term *= Poly(g_0.gens[0] - alpha, g_0.gens[0], domain=field)

    # Construct g_0^*
    g_0_star = g_0 + correction_term
    if timeout:
        return g_0_star, best_alpha_list, out_of_time
    return g_0_star, best_alpha_list, None

def dishonest_polynomial_no_boundary_conditions(g: Poly, max_degree: Union[None, int] = None, random_roots: bool = False) -> Tuple[Union[None, Poly], Union[None, List[Union[int, Any]]]]:
    """
    Given a univariate polynomial g over a finite field F (expected to be GF(p)),
    construct a new polynomial g*(x) = g(x) + h(x) satisfying the constraints:

    1. If deg(g) > 1:
       Let d = min(g.degree(), p-1, max_degree).
       If random_roots=False:
           h(x) = x*(x-1)*∏(x - i) for i=2,...,d-1.
       If random_roots=True:
           h(x) = x*(x-1)*∏(x - α_i), where α_i are d-2 distinct random elements from {2, 3, ..., p-1}.
       This ensures h(0)+h(1)=0 and gives d distinct roots.
       Returns a tuple (g(x) + h(x), list of chosen roots).

    2. If deg(g) = 1 and char(F) ≠ 2:
       Returns a tuple (g(x) + (x - 1/2), [1/2]), where 1/2 is the inverse of 2 mod p.

    3. If deg(g) = 1 and char(F) = 2:
       Then g(x) is either x or x+1 (over GF(2)).
       - If g(x)=x, returns (Poly(1), [1]) (constant polynomial 1).
       - If g(x)=x+1, returns (Poly(0), [1]) (constant polynomial 0).

    4. If deg(g) = 0, returns (None, None).

    Checks if F is a prime field by verifying that p is prime.

    Parameters
    ----------
    g : Poly
        Univariate polynomial over GF(p).
    max_degree : Union[None, int], optional
        The maximum allowable degree for the constructed polynomial. If provided, it constrains
        the degree of h(x). Defaults to None.
    random_roots : bool, optional
        If True and deg(g) > 1, choose the d-2 elements randomly
        from {2, 3, ..., p-1}. If False, use the sequence 2,...,d-1.

    Returns
    -------
    Tuple[Union[None, Poly], Union[None, List[Union[int, Any]]]]
        A tuple where:
        - The first element is either the modified polynomial g* (Poly) or None.
        - The second element is either the list, as integers or modular integers, of field elements r such that g^*_0(r) = g_0(r) (i.e. the roots of g^*_0 - g_0), or None.

    Raises
    ------
    ValueError
        If F is not a prime field or if conditions are not met.
    """
    if len(g.gens) != 1:
        raise ValueError("Polynomial g must be univariate.")

    F = g.domain

    # Check if F is a prime field by checking if characteristic is prime.
    if F.has_CharacteristicZero:
        raise ValueError("We need a finite prime field. Characteristic zero not allowed.")

    p = F.mod
    if not isprime(p):
        raise ValueError(
            "We are using SymPy and therefore can only handle polynomials over prime fields."
        )

    X = g.gens[0]
    # Set d = min(g.degree(), p - 1)
    if max_degree is not None:
        d = min(max_degree, p - 1)
    else:
        d = min(g.degree(), p - 1)

    if d == 0:
        # deg(g)=0 means g is constant. Return None.
        return None, None

    if d == 1:
        # If deg(g)=1, handle char(F)=p cases
        if p != 2:
            # Need 1/2 in GF(p). Using Fermat's little theorem: 1/2 = 2^(p-2) mod p
            inv_2 = F.convert(pow(2, p - 2, p))
            # h(x) = x - inv_2
            h = Poly(X - inv_2, X, domain=F)
            return g + h, [inv_2]
        else:
            # p=2, g(x)=x or g(x)=x+1
            coeffs = g.all_coeffs()
            # For deg=1: g(x)=a*x+b, coeffs=[a,b]
            a, b = coeffs[0], coeffs[1]
            if a == F.one and b == F.zero:
                # g(x)=x, return constant polynomial 1
                return Poly(F.one, X, domain=F), [F.one]
            elif a == F.one and b == F.one:
                # g(x)=x+1, return constant polynomial 0
                return Poly(F.zero, X, domain=F), [F.one]
            else:
                raise ValueError("In characteristic 2 and deg=1, g(x) should be x or x+1.")

    if d > 1:
        # h(x) = x*(x-1)*prod(x - i) for i=2,...,d-1
        # If random_roots=True, pick d-2 distinct random elements from {2,...,p-1}.
        if d == 2:
            h = Poly(X * (X - F.one), X, domain=F)
            alphas = [F.zero, F.one]
        else:
            # We need d-2 elements. If random_roots is False, we use 2,...,d-1.
            # If random_roots is True, we pick them at random from {2,...,p-1}.
            if random_roots:
                candidates = list(range(2, p))
                random.shuffle(candidates)
                chosen_ints = candidates[:(d - 2)]  # d-2 elements
            else:
                chosen_ints = list(range(2, d))

            alphas = [F.convert(i) for i in chosen_ints]
            h = Poly(X * (X - F.one), X, domain=F)
            for alpha in alphas:
                h *= Poly(X - alpha, X, domain=F)

        return g + h, alphas

    return None, None