"""
The parties of the protocol.

The engine plays the verifier's mechanical role (the checks) and delegates
every *choice* to a party object; it never knows whether an answer came from
an honest computation, the cheating machinery, or a human at a prompt.

Return-contract note: any choice may come back as `Cancelled` (the human typed
'cancel'/'c', or exhausted their attempts). The engine handles it in one
place, which makes the v0.1.x crash class ("coerced None into a field
element") unrepresentable.

I/O note: parties own their prompts and the micro-text immediately around them
(parse errors, retry counters, the cancel notice). All protocol *narration*
goes through events; prompt plumbing is an I/O-adapter concern and stays with
the party. An interactive prover also emits its own PROVER_PRIVATE advice
events -- the advice is P's reasoning, so it belongs to P.
"""
from __future__ import annotations

from itertools import product
from typing import Optional, Union

from sympy import Poly

from ..prompts import choose_polynomial_in_ring, parse_poly, random_field_element
from ..utils.display import RED, RESET, TerminalOutput
from ..utils.display import out as default_out
from .core import Audience, Sink
from .sumcheck_cheats import dishonest_polynomial_with_boundary_condition
from .sumcheck_events import (
    AdviceBlockClosed,
    CheatAdvice,
    ClaimAnnounced,
    InitialClaimDishonest,
    Laundered,
    MachineForged,
    TrueSumRevealed,
)


class Cancelled:
    """Sentinel: the human cancelled or exhausted their attempts."""

    def __repr__(self) -> str:  # pragma: no cover
        return "Cancelled()"


class NoOpening:
    """Sentinel: the prover provided no polynomial at the commitment opening."""


# ----------------------------------------------------------------------------
# Shared prover machinery: tracking the true g_j as challenges arrive
# ----------------------------------------------------------------------------

class _ProverBase:
    """A prover knows g. This base tracks the partially-substituted g and the
    carried claim, so printed polynomials
    and laundering decisions are value-identical."""

    def __init__(self, g: Poly, sink: Sink):
        self.g_init = g
        self.g_current = g               # g with challenges r_0..r_{j-1} substituted
        self.F = g.domain
        self.sink = sink
        self.carried_claim = None        # H*, then g*_j(r_j) after each round
        self.lying = False
        self._last_true_g0: Optional[Poly] = None
        self._last_sent: Optional[Poly] = None

    # -- truth ------------------------------------------------------------

    def _true_round_polynomial(self) -> Poly:
        """Sum g_current over Boolean values of all variables except the first
        ."""
        g = self.g_current
        F = self.F
        X, v = g.gens, len(g.gens)
        g_0 = sum(
            g.subs({X[k + 1]: F(b_k) for k, b_k in enumerate(b)})
            for b in product([F(0), F(1)], repeat=v - 1)
        )
        return g_0

    # -- engine callbacks ---------------------------------------------------

    def observe_challenge(self, j: int, challenge: int, *, at_final: bool) -> None:
        """Called by the engine after V samples r_j. Updates the carried claim,
        substitutes the challenge into g, and detects laundering."""
        F = self.F
        X = self.g_current.gens
        sent = self._last_sent
        true_g0 = self._last_true_g0
        self.carried_claim = sent.eval({sent.gens[0]: F(challenge)}) if sent is not None else None

        if self.lying and true_g0 is not None and sent is not None:
            if F(self.carried_claim) == F(true_g0.eval({X[0]: F(challenge)})):
                self.lying = False
                self.sink.emit(
                    Laundered(
                        audience=Audience.PROVER_PRIVATE,
                        j=j,
                        challenge=int(challenge),
                        announced=self._announces_laundering,
                        at_final=at_final,
                    )
                )

        self.g_current = self.g_current.subs({self.g_current.gens[0]: F(challenge)})

    _announces_laundering = False   # the block is printed only for a human prover


# ----------------------------------------------------------------------------
# Provers
# ----------------------------------------------------------------------------

class MachineProver(_ProverBase):
    """A machine prover. Claim honesty and opening honesty are independent
    axes. With a false claim it
    forges round polynomials for exactly as long as its carried claim stays
    false, and flips itself honest the moment a challenge launders the lie --
    an expliciticit state."""

    def __init__(self, g: Poly, true_sum, sink: Sink, *,
                 dishonest_claim: bool = False,
                 dishonest_opening: bool = False,
                 fixed_claim=None):
        super().__init__(g, sink)
        self.true_sum = true_sum
        self.dishonest_claim = dishonest_claim
        self.dishonest_opening = dishonest_opening
        # When set, the prover claims exactly this value instead of drawing a
        # random false claim. Used by reproducible scripted examples so the
        # transcript is byte-identical every run.
        self.fixed_claim = fixed_claim

    def sum_value(self, ctx) -> Union[int, Cancelled]:
        F = self.F
        if not self.dishonest_claim:
            self.carried_claim = self.true_sum
            self.sink.emit(ClaimAnnounced(audience=Audience.PUBLIC,
                                          claim=int(F.convert(self.true_sum))))
            return self.true_sum
        if self.fixed_claim is not None:
            claim = F.convert(self.fixed_claim)
        else:
            claim = self.true_sum
            while claim == self.true_sum:   # draw loop; identical RNG consumption
                claim = random_field_element(field=F, user_input=False, out=ctx.out)
        self.carried_claim = claim
        self.lying = True
        self.sink.emit(ClaimAnnounced(audience=Audience.PUBLIC, claim=int(F.convert(claim))))
        self.sink.emit(InitialClaimDishonest(audience=Audience.NARRATOR))
        return claim

    def round_polynomial(self, ctx) -> Union[Poly, Cancelled]:
        g_0 = self._true_round_polynomial()
        self._last_true_g0 = g_0
        if not self.lying:
            self._last_sent = g_0
            return g_0
        forged, roots, _ = dishonest_polynomial_with_boundary_condition(
            g_0=g_0, max_degree=ctx.degree_bound, H_star=self.carried_claim
        )
        self.sink.emit(
            MachineForged(
                audience=Audience.PROVER_PRIVATE,
                j=ctx.j,
                suggestion=forged,
                roots=tuple(int(z) for z in roots) if roots else None,
            )
        )
        self._last_sent = forged
        return forged

    def opening(self, ctx) -> Union[Poly, NoOpening, Cancelled]:
        if self.dishonest_opening:
            return self.g_init + self.F(1)
        return self.g_init


def HonestProver(g: Poly, true_sum, sink: Sink) -> MachineProver:
    """Convenience constructor: an honest machine prover."""
    return MachineProver(g, true_sum, sink, dishonest_claim=False)


class InteractiveProver(_ProverBase):
    """A human prover. Honest or dishonest is *emergent from their claim*: if
    they claim the true sum, no advice ever appears; if they lie, they are
    walked through the forced-cheat reasoning each round and can accept the
    suggested forgery with 'y', type their own, or cancel."""

    _announces_laundering = True

    def __init__(self, g: Poly, true_sum, sink: Sink, *, secret_mode: bool,
                 out: TerminalOutput = default_out):
        super().__init__(g, sink)
        self.true_sum = true_sum
        self.secret_mode = secret_mode
        self.out = out

    def sum_value(self, ctx) -> Union[int, Cancelled]:
        F = self.F
        # The true H is prover-private, and you are the prover: you need it to
        # decide whether to lie. It travels as an EVENT rather than inside the
        # prompt string, because on a routed run (a live presentation with
        # secrets_to=...) the renderer sends PROVER_PRIVATE to the side channel
        # while the prompt is typed at the shared screen -- a prompt that said
        # "(the true value is 5)" would leak it to the audience.
        #
        # secret_mode still masks what you TYPE, so a live audience does not
        # learn whether the claim you entered was the truth or a lie.
        self.sink.emit(TrueSumRevealed(
            audience=Audience.PROVER_PRIVATE,
            value=int(self.true_sum),
        ))
        raw = self.out.input(
            "\nAs prover, enter your claim H* for the value of H: ",
            hidden=self.secret_mode,
        )
        try:
            claim = F.convert(int(raw))
        except (TypeError, ValueError):
            return Cancelled()
        self.carried_claim = claim
        self.lying = bool(claim != F.convert(self.true_sum))
        return claim

    def round_polynomial(self, ctx) -> Union[Poly, Cancelled]:
        F = self.F
        g_0 = self._true_round_polynomial()
        self._last_true_g0 = g_0
        if not self.lying:
            self._last_sent = g_0
            return g_0

        j = ctx.j
        var = g_0.gens[0]
        suggestion, roots, _ = dishonest_polynomial_with_boundary_condition(
            g_0=g_0, max_degree=ctx.degree_bound, H_star=self.carried_claim
        )
        self.sink.emit(
            CheatAdvice(
                audience=Audience.PROVER_PRIVATE,
                j=j,
                var_name=str(var),
                true_poly=g_0,
                carried_claim=int(F.convert(self.carried_claim)),
                degree_bound=ctx.degree_bound,
                suggestion=suggestion,
                roots=tuple(int(z) for z in roots) if roots else None,
                field_mod=int(F.mod),
            )
        )

        # ---- prompt loop (I/O plumbinggacy) ----
        if suggestion is not None:
            prompt = (
                f"\nEnter 'y' to send the suggested polynomial, type your own "
                f"g*_{j}({str(var)}), or type 'cancel' to abort: "
            )
        else:
            prompt = f"\nType 'cancel' to abort, or your g*_{j}({str(var)}): "

        chosen: Optional[Poly] = None
        max_attempts = 3
        attempts = 0
        while chosen is None and attempts < max_attempts:
            attempts += 1
            raw = self.out.input(prompt).strip()
            if raw.lower() == "cancel":
                # NO END-INVISIBLE marker on this path.
                self.out.print(f"\n{RED}Input cancelled. Aborting this run.{RESET}")
                return Cancelled()
            if raw.lower() == "y" and suggestion is not None:
                chosen = suggestion
                break
            try:
                chosen = parse_poly(
                    raw, field=F, gens=[var], preferred_order=None, strict=True
                )
            except Exception as e:
                self.out.print(f"\nCould not parse polynomial: {e}")
                if attempts < max_attempts:
                    self.out.print(f"Try again ({attempts}/{max_attempts}).")
        if chosen is None:
            # NO END-INVISIBLE marker on this path either.
            self.out.print(f"\n{RED}Input cancelled or invalid too many times. Aborting this run.{RESET}")
            return Cancelled()

        self.sink.emit(AdviceBlockClosed(audience=Audience.PROVER_PRIVATE))
        self._last_sent = chosen
        return chosen

    def opening(self, ctx) -> Union[Poly, NoOpening, Cancelled]:
        choice = self.out.input(
            "\nChoose a, b, or c: About the opened polynomial g, you, as prover, will "
            "(a) be honest. "
            "(b) enter a polynomial (honest or dishonest) yourself. "
            "(c) be dishonest.",
            hidden=self.secret_mode,
        ).strip().lower()
        if choice == "a":
            return self.g_init
        if choice == "b":
            g_open = choose_polynomial_in_ring(
                field=self.F,
                gens=self.g_init.gens,
                custom_message="\nEnter the polynomial you, as prover, want to open with: ",
                secret_mode_for_poly=bool(self.secret_mode),
                out=self.out,
            )
            if g_open is None:
                return NoOpening()
            return g_open
        return self.g_init + self.F(1)


# ----------------------------------------------------------------------------
# Verifiers
# ----------------------------------------------------------------------------

class RandomVerifier:
    def __init__(self, field, *, out: TerminalOutput = default_out):
        self.F = field
        self.out = out

    def challenge(self, ctx) -> Union[int, Cancelled]:
        return random_field_element(field=self.F, user_input=False, out=self.out)

    def gkr_rho_coordinate(self, j: int) -> Union[int, Cancelled]:
        return random_field_element(field=self.F, user_input=False, out=self.out)

    def gkr_tau(self, i: int) -> Union[int, Cancelled]:
        return random_field_element(field=self.F, user_input=False, out=self.out)


class ScriptedVerifier:
    """A verifier whose challenges are fixed in advance rather than random.

    It plays back a given sequence of field elements as its round challenges,
    in order. This is for reproducible worked examples: a book cell can show a
    specific run of the protocol -- a particular sequence of verifier choices --
    and get byte-identical output every time. The narration is unchanged; from
    the transcript's point of view these look exactly like random draws, because
    for soundness what matters is only that P could not predict them, not how
    they were produced here.
    """

    def __init__(self, field, challenges, *, out: TerminalOutput = default_out):
        self.F = field
        self.out = out
        self._challenges = [int(c) for c in challenges]
        self._i = 0

    def _next(self) -> int:
        if self._i >= len(self._challenges):
            raise ValueError(
                f"ScriptedVerifier ran out of challenges after {self._i}; "
                f"the protocol asked for more than the {len(self._challenges)} provided."
            )
        value = self._challenges[self._i]
        self._i += 1
        return int(self.F.convert(value))

    def challenge(self, ctx) -> Union[int, Cancelled]:
        return self._next()

    def gkr_rho_coordinate(self, j: int) -> Union[int, Cancelled]:
        return self._next()

    def gkr_tau(self, i: int) -> Union[int, Cancelled]:
        return self._next()


class InteractiveVerifier:
    def __init__(self, field, *, out: TerminalOutput = default_out):
        self.F = field
        self.out = out

    def challenge(self, ctx) -> Union[int, Cancelled]:
        prompt = (
            f"\nAs verifier, choose an element of {self.F} uniformly at random, "
            f"independent of any previous choice:"
        )
        value = random_field_element(
            field=self.F, user_input=True, custom_message=prompt, out=self.out
        )
        if value is None:
            return Cancelled()
        return value

    def gkr_rho_coordinate(self, j: int) -> Union[int, Cancelled]:
        prompt = (
            f"\nAs verifier, choose an element of {self.F} uniformly at random, independent of "
            f"any previous choice (coordinate {j} of \u03c1_0):"
        )
        value = random_field_element(
            field=self.F, user_input=True, custom_message=prompt, out=self.out
        )
        if value is None:
            return Cancelled()
        return value

    def gkr_tau(self, i: int) -> Union[int, Cancelled]:
        prompt = (
            f"\nAs verifier, choose an element of {self.F} uniformly at random, independent of any "
            f"previous choice (this will be \u03c4_{i + 1}):"
        )
        value = random_field_element(
            field=self.F, user_input=True, custom_message=prompt, out=self.out
        )
        if value is None:
            return Cancelled()
        return value