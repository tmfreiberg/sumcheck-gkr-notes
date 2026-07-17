"""
The sum-check text renderer: one function per event type.

Visibility is a pure audience filter (event.audience in view) -- no renderer
asks whose turn it is or what mode the session is in. Two exceptions, both
deliberate: the initialization and opening renders consult the view for
*phrasing*, because what a verifier is told is not a subset of what a spectator
is told; and a machine prover's private events render to nothing, since there is
no one to show them to.

Every mathematical symbol is composed through gkr.notation rather than written
literally, so that supplying a different Notation retargets the whole renderer.
tests/test_invariants.py enforces this by scanning this file's source.
"""
from __future__ import annotations

from typing import Callable, FrozenSet

from ..notation import DEFAULT_PALETTE, NOTEBOOK_NOTATION, Notation, Palette
from ..utils.display import (
    SupportsPrint,
    display_aligned,
    print_header,
    stringify,
    to_string,
)
from .core import Audience, Event
from .sumcheck_events import (
    AdviceBlockClosed,
    ChallengeSampled,
    CheatAdvice,
    ClaimAnnounced,
    CommitmentChecked,
    ConsistencyChecked,
    DegreeChecked,
    FinalCheckStarted,
    FinalClaimStated,
    GroundTruthRevealed,
    InitialClaimDishonest,
    Laundered,
    MachineForged,
    OpenedEvaluation,
    OpeningPrompted,
    OpeningRevealed,
    OracleQueried,
    PolynomialSent,
    ProtocolInitialized,
    RoundStarted,
    TrueSumRevealed,
    VerdictAnnounced,
)


def make_renderer(
    *,
    out: SupportsPrint,
    field,
    view: FrozenSet[Audience],
    notation: Notation = NOTEBOOK_NOTATION,
    palette: Palette = DEFAULT_PALETTE,
) -> Callable[[Event], None]:
    """Build a streaming renderer bound to an output, a field (for 'GF(p)' in
    prose), a view, a notation, and a palette."""
    F = field
    n = notation
    RED, GREEN, YELLOW, RESET = palette.LIE, palette.TRUTH, palette.ASIDE, palette.RESET
    H = n.H()                         # "H"
    Hs = n.H(star=True)               # "H*"
    g = n.g()                         # "g"

    def _lhs_label(event) -> str:
        """The left-hand side of round j's consistency check: the claim H* in
        round 0, else P's previous message evaluated at the last challenge."""
        if event.prev_challenge is None:
            return Hs
        return f"{n.g(event.j - 1, star=True)}({to_string(event.prev_challenge)})"

    def render(event: Event) -> None:
        if event.audience not in view:
            return None

        # ------------------------------------------------------------------
        if isinstance(event, ProtocolInitialized):
            print_header("Initialization", out=out)
            degs = [int(b) for b in event.degree_bounds]
            X_ = stringify(event.g.gens)
            b_ = stringify([f"b_{k}" for k in range(event.num_vars)])
            if Audience.NARRATOR in view:
                out.print(f"\nLet\n\n{g}({X_}) = {event.g.as_expr()}.")
                out.print(
                    f"\n{YELLOW}We display {g} for the reader. In the protocol, V does not receive {g} explicitly;{RESET} "
                    f"{YELLOW}V only has oracle/committed evaluation access to {g}.{RESET}"
                )
                if event.use_commitment and event.commit_hash is not None:
                    out.print(f"\nCommitment hash (binding commitment to {g}): {event.commit_hash}")
                out.print(f"\nFor soundness, V relies on degree bounds per variable (this is public information): {degs}.")
            else:
                if event.use_commitment and event.commit_hash is not None:
                    out.print(f"\nV receives a commitment to {g} (not {g} itself).")
                    out.print(f"\nCommitment hash: {event.commit_hash}")
                    out.print(f"\nFor soundness, V relies on degree bounds per variable (this is public information): {degs}.")
                    out.print(f"\nV proceeds knowing only the field, arity, degree bounds, and a binding commitment to {g}.")
                else:
                    out.print(f"\nFor soundness, V relies on degree bounds per variable (this is public information): {degs}.")
            out.print(f"\nLet\n\n{H} := sum {g}({b_}) over ({b_}) in {{0,1}}^{event.num_vars}.")

        # ------------------------------------------------------------------
        elif isinstance(event, TrueSumRevealed):
            out.print(f"\nThe true value is {H} = {event.value}.")

        elif isinstance(event, ClaimAnnounced):
            out.print(f"\nP claims that {H} = {Hs}, where {Hs} = {event.claim}.")

        elif isinstance(event, InitialClaimDishonest):
            out.print(
                f"\n{RED}In this run, P's initial claim {Hs} is intentionally false, and P will try to get away with it.{RESET}"
            )

        # ------------------------------------------------------------------
        elif isinstance(event, ChallengeSampled):
            out.print(
                f"\nV samples an element uniformly at random from {F}; here {n.r(event.j)} = {event.value}."
            )

        elif isinstance(event, Laundered):
            if not event.announced:
                return  # a machine prover has no one to show this to
            # The lie was laundered because V's challenge r_j landed on a root of
            # g*_j - g_j, so the round index is j in BOTH cases. (An earlier
            # version printed g*_{j+1}: it reported the challenge at the *next*
            # round's step, where its loop variable had already advanced, while
            # its final-check block used the correct index. No golden covered
            # this path, which is why the inconsistency survived.)
            out.print(f"\n{RED}=== START INVISIBLE TO VERIFIER ==={RESET}")
            out.print(
                f"\n{RED}YOU HAVE SUCCESSFULLY DECEIVED THE VERIFIER: "
                f"{n.g(event.j, star=True)}({event.challenge}) = {n.g(event.j)}({event.challenge}){RESET}"
            )
            if not event.at_final:
                # No rounds remain after the final one, so "from now on" would be empty.
                out.print(f"\n{RED}From now on, the {n.g('j', star=True)} will automatically be set to {n.g('j')}.{RESET}")
            out.print(f"\n{RED}=== END INVISIBLE TO VERIFIER ==={RESET}")

        # ------------------------------------------------------------------
        elif isinstance(event, RoundStarted):
            print_header(f"Round {event.j}", out=out)
            j, v = event.j, event.num_vars
            mixed_input = stringify(
                list(event.fixed_challenges), [event.var_name], list(event.bound_var_names)
            )
            if v - 1 - j > 0:
                out.print(
                    f"\nLet\n\n{n.g(j)}({event.var_name}) := sum {g}({mixed_input}) "
                    f"over ({stringify(list(event.bound_var_names))}) in {{0,1}}^{v - 1 - j}"
                )
            else:
                out.print(f"\nLet\n\n{n.g(j)}({event.var_name}) := {g}({mixed_input})")

        # ------------------------------------------------------------------
        elif isinstance(event, CheatAdvice):
            j, var, d, p = event.j, event.var_name, event.degree_bound, event.field_mod
            out.print(f"\n{RED}=== START INVISIBLE TO VERIFIER ==={RESET}")
            out.print(f"\nIn fact, \n\n{GREEN}{n.g(j)}({var}) = {event.true_poly.as_expr()}{RESET}.")
            out.print(
                f"\nYour goal is to convince V that the polynomial {n.g(j, star=True)} you're about to send is {n.g(j)} (a false claim)."
            )
            out.print("\nV will check that:")
            out.print(f"\n(a) {n.deg(n.g(j, star=True))} \u2264 {n.deg(g, wrt=j)} = {d}")
            out.print(f"\n(b) {n.g(j, star=True)}(0) + {n.g(j, star=True)}(1) = {event.carried_claim}")
            out.print(
                f"\nIf it turns out that\n"
                f"\n(c) {n.g(j, star=True)}({n.r(j)}) = {n.g(j)}({n.r(j)}),\n"
                f"\nwhere {n.r(j)} is the random element of {F} that V will sample next,"
            )
            out.print(
                f"\nthen V will accept your original claim if you send the 'true' "
                f"polynomials {n.g('k', star=True)} = {n.g('k')} in subsequent rounds."
            )
            out.print(
                f"\nAs you don't know what {n.r(j)} will be, the best you can do is choose {n.g(j, star=True)} satisfying (a) and (b) such that"
            )
            out.print(
                f"\n(d) {n.g(j, star=True)} - {n.g(j)} has as many roots as possible in {F} "
                f"(there can be at most {n.deg(n.g(j, star=True) + ' - ' + n.g(j))} \u2264 {d})."
            )
            if event.suggestion is not None and event.roots:
                roots = [int(z) for z in event.roots]
                print_roots = ", ".join([f"{YELLOW}{str(z)}{RESET}" for z in roots])
                out.print(
                    f"\nFor example, if{RED}\n\n{n.g(j, star=True)}({var}) = {event.suggestion.as_expr()}{RESET},\n\nthen (a) and (b) hold, "
                    f"and the roots (in {F}) of {n.g(j, star=True)} - {n.g(j)} are: {print_roots}."
                )
                out.print(f"\nThe probability of V sampling one of these roots as the next challenge is "
                      f"{len(roots)}/{p} = {len(roots)/p:.10f}.")
                out.print(
                    f"\nIn general, by Schwartz-Zippel, this probability cannot exceed "
                    f"{n.deg(g, wrt=j)}/#F = {d}/{p} = {d/p:.10f}."
                )
                out.print(f"\nIn this event, V will ultimately accept the original false claim for the value of {H}.")
                out.print(
                    "\nEven if this does not happen, as long as (a) and (b) hold, V will accept in this round "
                    "and we will have another chance to pull off the deception."
                )
            elif event.suggestion is not None:
                out.print(
                    f"\nFor example, if\n\n{RED}{n.g(j, star=True)}({var}) = {event.suggestion.as_expr()}{RESET},\n\nthen (a) and (b) hold, "
                    f"but {n.g(j, star=True)} - {n.g(j)} has no roots in {F}."
                )
                out.print(
                    f"\nWe are unable to suggest a polynomial satisfying (a) and (b) such that {n.g(j, star=True)} - {n.g(j)} has a root "
                    f"in {F}\u2014perhaps no such polynomial exists."
                )
                out.print(
                    "\nEven if no such polynomial exists, as long as (a) and (b) hold, V will accept in this round "
                    "and we will have another chance to pull off the deception."
                )
            else:
                out.print("\nWe are unable to suggest a polynomial satisfying (a) and (b)\u2014perhaps no such polynomial exists.")
                out.print("\nIf no such polynomial exists, we've been caught in a lie and V will reject immediately.")

        elif isinstance(event, AdviceBlockClosed):
            out.print(f"\n{RED}=== END INVISIBLE TO VERIFIER ==={RESET}")

        elif isinstance(event, MachineForged):
            return  # nothing mid-run; the event exists for the log/JSON

        # ------------------------------------------------------------------
        elif isinstance(event, PolynomialSent):
            out.print(
                f"\nP claims that {n.g(event.j)}({event.var_name}) = {n.g(event.j, star=True)}({event.var_name}), where \n\n"
                f"{n.g(event.j, star=True)}({event.var_name}) = {event.poly.as_expr()}."
            )

        elif isinstance(event, DegreeChecked):
            j = event.j
            RHS = f"{n.g(j, star=True)}(0) + {n.g(j, star=True)}(1)"
            out.print(
                f"\nIf P's last two claims are true, then {n.deg(n.g(j, star=True))} \u2264 {n.deg(g, wrt=j)} and {_lhs_label(event)} = {RHS}."
            )
            if event.passed:
                out.print(
                    f"\nV checks the degree bound: {n.deg(n.g(j, star=True))} = {event.degree} \u2264 {n.deg(g, wrt=j)} = {event.bound}."
                )
            else:
                out.print(f"\nV finds that {n.deg(n.g(j, star=True))} = {event.degree} > {n.deg(g, wrt=j)} = {event.bound}.")
                out.print(f"\nV {RED}REJECTS{RESET} (degree bound violated). The protocol terminates.")

        elif isinstance(event, ConsistencyChecked):
            j = event.j
            RHS = f"{n.g(j, star=True)}(0) + {n.g(j, star=True)}(1)"
            if event.prev_challenge is None:
                out.print(f"\nP's claim is that {H} = {Hs} = {event.carried_claim}. V proceeds to compute:\n")
                out.print(f"{RHS} = {event.rhs_value}")
                out.print(f"\nThis is easy because {n.g(j, star=True)} is given explicitly, so V can evaluate it at 0 and 1.")
            else:
                out.print("\nV proceeds to compute:\n")
                display_aligned(f"{_lhs_label(event)} = {event.lhs_value}", f"{RHS} = {event.rhs_value}", out=out)
                out.print(
                    "\nThis is easy because both claimed polynomials are given explicitly, "
                    "and V only needs univariate evaluations at 0 and 1."
                )
            if event.passed:
                out.print("\nV sees that P's claims so far are consistent.")
            else:
                out.print(f"\nV {RED}REJECTS{RESET} upon exposing an inconsistency in P's claims. The protocol terminates.")

        # ------------------------------------------------------------------
        elif isinstance(event, FinalCheckStarted):
            print_header("\nFinal check", level=2, out=out)

        elif isinstance(event, FinalClaimStated):
            r_ = stringify(list(event.all_challenges))
            LHS = f"{n.g(event.last_j, star=True)}({to_string(event.last_challenge)})"
            RHS = f"{g}({r_})"
            out.print(f"\nIf all of P's claims are true, then\n\n{LHS} = {RHS}.")
            out.print(f"\nV computes\n\n{LHS} = {event.terminal_claim}.")

        # ------------------------------------------------------------------
        elif isinstance(event, OpeningPrompted):
            out.print("\nP now reveals g (this is the 'opening' step in our toy commitment demo).")
            out.print(f"\n{YELLOW}CAVEAT (real protocols): "
                f"In practice, P does *not* reveal g. Instead, P commits to g using a binding "
                f"(and typically hiding) polynomial commitment scheme and later proves that "
                f"g(r) equals the claimed value using a succinct opening proof.{RESET}"
                )

        elif isinstance(event, OpeningRevealed):
            if event.poly is None:
                out.print(f"\nV {RED}REJECTS{RESET}: no polynomial provided at opening.")
                return None
            if event.dishonest and Audience.NARRATOR in view:
                out.print(f"\n{RED}In this run, P will attempt to open with a different polynomial.{RESET}")
            if event.dishonest:
                out.print(f"\nRevealed polynomial:\n\n{RED}{g}({event.gens_str}) = {event.poly.as_expr()}{RESET}.")
            else:
                out.print(f"\nRevealed polynomial:\n\n{GREEN}{g}({event.gens_str}) = {event.poly.as_expr()}{RESET}.")

        elif isinstance(event, CommitmentChecked):
            out.print("\nV recomputes the hash of the revealed polynomial and checks it matches the original commitment.")
            out.print(f"\nCommitment check: {GREEN}PASS{RESET}" if event.ok else f"\nCommitment check: {RED}FAIL{RESET}")
            out.print(f"\nOriginal hash:   {event.original_hash}")
            if event.ok:
                out.print(f"Recomputed hash: {GREEN}{event.recomputed_hash}{RESET}")
            if not event.ok:
                out.print(f"Recomputed hash: {RED}{event.recomputed_hash}{RESET}")
                out.print(f"\nV {RED}REJECTS{RESET}: the revealed polynomial does not match the original commitment.")

        elif isinstance(event, OpenedEvaluation):
            RHS = f"{g}({stringify(list(event.all_challenges))})"
            out.print(f"\nFor the purposes of this demo (see caveat above): since {g} is revealed, V can evaluate it directly:\n\n{RHS} = {event.value}.")

        elif isinstance(event, OracleQueried):
            RHS = f"{g}({stringify(list(event.all_challenges))})"
            out.print(
                f"\nFinally, V queries an oracle for {g} at {n.r()} to obtain\n\n{RHS} = {event.value}."
            )

        elif isinstance(event, VerdictAnnounced):
            if event.accepted:
                out.print(f"\nP passes the final verification, and V {GREEN}ACCEPTS{RESET} P's initial claim that {H} = {Hs}.")
                if event.initially_dishonest:
                    out.print(f"\n{RED}P HAS DECEIVED V: THE TRUE VALUE OF {H} IS IN FACT {event.true_sum}.{RESET}")
                    out.print(
                        f"\n{YELLOW}P GOT LUCKY:{RESET} the final random check happened not to expose the inconsistency "
                        f"this time. Over a large field, this success event should be rare."
                    )
            else:
                out.print(f"\nP fails the final verification, and V {RED}REJECTS{RESET} P's initial claim that {H} = {Hs}.")
                out.print(
                    f"\n{YELLOW}Interpretation: P can often keep the transcript locally consistent round-by-round, "
                    f"but the final random evaluation ties the transcript to the true {g} and typically catches a lie.\n{RESET}"
                )

        # ------------------------------------------------------------------
        elif isinstance(event, GroundTruthRevealed):
            print_header("Ground truth", level=1, out=out)
            expr_str = str(event.g.as_expr())
            MAX = 800  # characters
            if len(expr_str) > MAX:
                expr_str = expr_str[:MAX] + " ... (truncated)"
            out.print(f"\nTrue polynomial {g}:\n\n{g}({event.gens_str}) = {expr_str}")
            if event.use_commitment:
                out.print("\nCommitment behavior:")
                if event.dishonest_opening:
                    out.print(f"\nProver attempted a {RED}dishonest opening{RESET}.")
                else:
                    out.print(f"\nProver opened the {GREEN}correct polynomial{RESET}.")
            out.print(f"\nTrue value of {H} := sum {g}(b) over b in {{0,1}}^{event.num_vars} is: {event.true_sum}")
            out.print(f"\nProver claimed that this is equal to: {Hs} = {event.claimed_sum}.")
            if event.accepted:
                out.print(f"\nOutcome: V {GREEN}ACCEPTED{RESET}.")
                if event.claimed_sum == event.true_sum:
                    out.print(f"\n{GREEN}This was a TRUE POSITIVE{RESET}: the claim {H} = {Hs} was correct.")
                else:
                    out.print(f"\n{RED}This was a FALSE POSITIVE{RESET}: V accepted a false claim (P got lucky).")
            else:
                out.print(f"\nOutcome: V {RED}REJECTED{RESET}.")
                if event.claimed_sum == event.true_sum:
                    out.print(f"{YELLOW}\nThis was a FALSE NEGATIVE{RESET}: rejection happened despite a true claim (should be rare unless opening failed / transcript inconsistent).")
                else:
                    out.print(f"{GREEN}\nThis was a TRUE NEGATIVE{RESET}: V rejected a false claim.")
            out.print("")

    return render