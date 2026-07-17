"""
The sum-check engine.

A plain loop that plays the verifier's
mechanical role: it emits narration events, asks the prover for each message,
runs the public checks (degree bound, boundary consistency), asks the verifier
for each challenge, and hands the terminal claim to an *oracle* for the final
check. The engine holds only public information: arity, degree bounds, the
carried claim, the challenges. The polynomial g lives with the parties and the
oracle -- exactly the information model of the protocol itself.

The oracle is a parameter: `PolynomialOracle(g)` performs the standalone
final evaluation (optionally through the toy commitment); `DeferredToCaller`
returns the terminal claim untested, for GKR, where truth is judged by the
bridging equation. This is why the engine needs no `show_final_check` /
`return_final_value` flag pair; the engine does not know GKR exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import List, Optional, Sequence, Tuple, Union

from sympy import Poly

from ..utils.display import TerminalOutput
from ..utils.display import out as default_out
from .commitment import poly_commitment_sha256
from .core import Audience, Sink
from .sumcheck_events import (
    ChallengeSampled,
    CommitmentChecked,
    ConsistencyChecked,
    DegreeChecked,
    FinalCheckStarted,
    FinalClaimStated,
    OpenedEvaluation,
    OpeningPrompted,
    OpeningRevealed,
    OracleQueried,
    PolynomialSent,
    RoundStarted,
    VerdictAnnounced,
)
from .sumcheck_parties import Cancelled, NoOpening

# ----------------------------------------------------------------------------
# Verdicts
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class Accepted:
    pass


@dataclass(frozen=True)
class Rejected:
    reason: str          # "degree" | "consistency" | "commitment" | "no_opening" | "final"
    at_round: Optional[int] = None


@dataclass(frozen=True)
class Aborted:
    stage: str           # "claim" | "round" | "challenge" | "opening"


@dataclass(frozen=True)
class TerminalValue:
    """GKR mode: the transcript survived the rounds; here is the terminal claim
    gamma = g*_{v-1}(r_{v-1}). Truth is the caller's business."""
    value: int


Verdict = Union[Accepted, Rejected, Aborted, TerminalValue]


@dataclass
class SumCheckResult:
    verdict: Verdict
    claim: Optional[int]                 # H* as announced/entered
    challenges: Tuple[int, ...]


# ----------------------------------------------------------------------------
# Contexts handed to parties
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class RoundContext:
    j: int
    num_vars: int
    degree_bound: int
    carried_claim: int
    out: TerminalOutput


@dataclass(frozen=True)
class OpeningContext:
    out: TerminalOutput


# ----------------------------------------------------------------------------
# Oracles for the final check
# ----------------------------------------------------------------------------

class PolynomialOracle:
    """Owns g; performs the final check (optionally via the toy
    commitment: P opens, V recomputes the hash, then evaluates)."""

    def __init__(self, g: Poly, *, use_commitment: bool = False,
                 commit_hash: Optional[str] = None):
        self.g = g
        self.F = g.domain
        self.use_commitment = use_commitment
        self.commit_hash = commit_hash

    def true_sum(self) -> int:
        F, g = self.F, self.g
        X, v = g.gens, len(g.gens)
        H = F(sum(
            g.eval({X[k]: b_k for k, b_k in enumerate(b)})
            for b in product([F(0), F(1)], repeat=v)
        ))
        return int(H)

    def begin_final(self, *, sink: Sink) -> None:
        """Announce the final-check section, before V's last challenge is
        reported. (GKR has no such section: see DeferredToCaller.)"""
        sink.emit(FinalCheckStarted(audience=Audience.PUBLIC))

    def finalize(self, *, prover, sink: Sink, challenges: Sequence[int],
                 terminal_claim: int, initial_claim: int,
                 out: TerminalOutput) -> Verdict:
        F, g = self.F, self.g
        subs = {g.gens[k]: challenges[k] for k in range(len(challenges))}
        g_comm_at_r = int(F(g.eval(subs)))
        all_ch = tuple(int(c) for c in challenges)
        v = len(challenges)
        last = challenges[-1]

        sink.emit(FinalClaimStated(
            audience=Audience.PUBLIC,
            last_j=v - 1,
            last_challenge=int(F.convert(last)),
            all_challenges=all_ch,
            terminal_claim=int(terminal_claim),
        ))

        check_val: int
        if self.use_commitment and self.commit_hash is not None:
            sink.emit(OpeningPrompted(audience=Audience.PUBLIC))
            g_open = prover.opening(OpeningContext(out=out))
            if isinstance(g_open, Cancelled):
                return Aborted(stage="opening")
            if isinstance(g_open, NoOpening):
                sink.emit(OpeningRevealed(
                    audience=Audience.PUBLIC, poly=None, gens_str="",
                    dishonest=True, announced_dishonest=False,
                ))
                return Rejected(reason="no_opening")
            dishonest_opening = bool(g_open != g)
            from ..utils.display import stringify
            sink.emit(OpeningRevealed(
                audience=Audience.PUBLIC,
                poly=g_open,
                gens_str=stringify(g.gens),
                dishonest=dishonest_opening,
                announced_dishonest=dishonest_opening,
            ))
            recomputed = poly_commitment_sha256(g_open)
            ok = (recomputed == self.commit_hash)
            sink.emit(CommitmentChecked(
                audience=Audience.PUBLIC, ok=ok,
                original_hash=self.commit_hash, recomputed_hash=recomputed,
            ))
            if not ok:
                return Rejected(reason="commitment")
            check_val = int(F(g_open.eval(subs)))
            sink.emit(OpenedEvaluation(audience=Audience.PUBLIC,
                                       all_challenges=all_ch, value=check_val))
        else:
            check_val = g_comm_at_r
            sink.emit(OracleQueried(audience=Audience.PUBLIC,
                                    all_challenges=all_ch, value=check_val))

        accepted = (F.convert(terminal_claim) == F.convert(check_val))
        H = self.true_sum()
        sink.emit(VerdictAnnounced(
            audience=Audience.GROUND_TRUTH,
            accepted=accepted,
            initially_dishonest=(F.convert(initial_claim) != F.convert(H)),
            true_sum=H,
        ))
        return Accepted() if accepted else Rejected(reason="final")


class DeferredToCaller:
    """GKR mode: no oracle evaluation and no final-check section -- the caller
    (the GKR layer transition) judges truth via the bridging equation instead.

    Note that V's last challenge IS announced, by the engine, for every oracle.
    Suppressing it (returning before the final block, as an earlier design did)
    left the reader to reverse-engineer r_{m-1} from the r_y vector printed
    later -- and left the event log missing
    a challenge that was genuinely sampled and used."""

    def begin_final(self, *, sink: Sink) -> None:
        return None

    def finalize(self, *, prover, sink: Sink, challenges: Sequence[int],
                 terminal_claim: int, initial_claim: int,
                 out: TerminalOutput) -> Verdict:
        return TerminalValue(value=int(terminal_claim))


# ----------------------------------------------------------------------------
# The engine
# ----------------------------------------------------------------------------

def run_sum_check(
    *,
    field,
    gens: Sequence,                       # sympy symbols of g (names drive narration)
    degree_bounds: Sequence[int],
    prover,
    verifier,
    oracle,
    sink: Sink,
    out: TerminalOutput = default_out,
) -> SumCheckResult:
    F = field
    v = len(gens)
    bounds = [int(b) for b in degree_bounds]
    b_names = tuple(f"b_{k}" for k in range(v))

    # ---- the claim ---------------------------------------------------------
    claim = prover.sum_value(RoundContext(j=0, num_vars=v, degree_bound=bounds[0],
                                          carried_claim=0, out=out))
    if isinstance(claim, Cancelled):
        return SumCheckResult(verdict=Aborted(stage="claim"), claim=None, challenges=())
    carried = F.convert(claim)
    initial_claim = int(carried)

    challenges: List[int] = []

    # ---- rounds ------------------------------------------------------------
    for j in range(v):
        sink.emit(RoundStarted(
            audience=Audience.PUBLIC,
            j=j,
            num_vars=v,
            var_name=str(gens[j]),
            fixed_challenges=tuple(int(c) for c in challenges),
            bound_var_names=b_names[j + 1:],
        ))

        ctx = RoundContext(j=j, num_vars=v, degree_bound=bounds[j],
                           carried_claim=int(carried), out=out)
        g_star = prover.round_polynomial(ctx)
        if isinstance(g_star, Cancelled):
            return SumCheckResult(verdict=Aborted(stage="round"),
                                  claim=initial_claim,
                                  challenges=tuple(challenges))

        sink.emit(PolynomialSent(audience=Audience.PUBLIC, j=j,
                                 var_name=str(gens[j]), poly=g_star))

        prev_challenge = int(F.convert(challenges[j - 1])) if j > 0 else None
        degree = g_star.degree()   # may be sympy -oo for the zero polynomial
        degree_ok = (degree <= bounds[j])
        sink.emit(DegreeChecked(audience=Audience.PUBLIC, j=j,
                                degree=degree, bound=bounds[j],
                                passed=degree_ok, prev_challenge=prev_challenge))
        if not degree_ok:
            return SumCheckResult(verdict=Rejected(reason="degree", at_round=j),
                                  claim=initial_claim,
                                  challenges=tuple(challenges))

        rhs = F(g_star.eval({g_star.gens[0]: F(0)}) + g_star.eval({g_star.gens[0]: F(1)}))
        consistent = (F(carried) == rhs)
        sink.emit(ConsistencyChecked(
            audience=Audience.PUBLIC, j=j,
            prev_challenge=prev_challenge, lhs_value=int(F.convert(carried)),
            rhs_value=int(rhs), passed=consistent,
            carried_claim=int(F.convert(carried)),
        ))
        if not consistent:
            return SumCheckResult(verdict=Rejected(reason="consistency", at_round=j),
                                  claim=initial_claim,
                                  challenges=tuple(challenges))

        challenge = verifier.challenge(ctx)
        if isinstance(challenge, Cancelled):
            return SumCheckResult(verdict=Aborted(stage="challenge"),
                                  claim=initial_claim,
                                  challenges=tuple(challenges))
        challenges.append(challenge)
        carried = g_star.eval({g_star.gens[0]: F(challenge)})

        if j < v - 1:
            sink.emit(ChallengeSampled(audience=Audience.PUBLIC, j=j,
                                       value=int(F.convert(challenge))))
            prover.observe_challenge(j, challenge, at_final=False)

    # ---- final check --------------------------------------------------------
    # Every challenge V samples is announced and observed by P, including the
    # last: the log is the record of what happened, and rendering decides what
    # is shown. The oracle owns the *section* around it -- PolynomialOracle
    # opens a "Final check" header first and states the claim afterwards; GKR's
    # DeferredToCaller adds neither.
    last = challenges[-1]
    oracle.begin_final(sink=sink)
    sink.emit(ChallengeSampled(audience=Audience.PUBLIC, j=v - 1,
                               value=int(F.convert(last))))
    prover.observe_challenge(v - 1, last, at_final=True)

    verdict = oracle.finalize(
        prover=prover, sink=sink, challenges=list(challenges),
        terminal_claim=int(F.convert(carried)), initial_claim=initial_claim,
        out=out,
    )
    return SumCheckResult(verdict=verdict, claim=initial_claim,
                          challenges=tuple(int(F.convert(c)) for c in challenges))