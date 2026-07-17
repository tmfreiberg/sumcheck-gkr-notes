"""
Sum-check events, and the Transcript: the PUBLIC slice of a run, i.e. the proof.

The shared vocabulary (Audience, Event, Sink, the views, make_routing_renderer)
is in core.py; GKR's events are in gkr_events.py.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union

from sympy import Poly

from .core import Event, _poly_record


@dataclass(frozen=True)
class ProtocolInitialized(Event):
    """The initialization block.

    The commitment phrasing of this block differs between
    the secret and non-secret views (not a subset relationship), so its render
    function branches on the view for phrasing. Candidate for
    decomposition in the re-narration pass. Audience is PUBLIC because every
    view shows *some* form of it.
    """
    g: Poly
    degree_bounds: Tuple[int, ...]
    num_vars: int
    use_commitment: bool = False
    commit_hash: Optional[str] = None

@dataclass(frozen=True)
class TrueSumRevealed(Event):
    """The true H, told to the party entitled to it (the prover). Emitted just
    before the prover is asked for their claim, so that on a routed run the
    value appears on the private channel while the shared screen shows only a
    neutral prompt."""
    value: int

@dataclass(frozen=True)
class ClaimAnnounced(Event):
    """P claims that H = H*. Emitted by machine provers; an interactive prover's
    claim is established at the prompt instead ."""
    claim: int

@dataclass(frozen=True)
class InitialClaimDishonest(Event):
    """Narrator aside: this run's H* is intentionally false."""

@dataclass(frozen=True)
class ChallengeSampled(Event):
    """V samples r_j. Renders the 'V samples ... here r_j = v.' line.

    (Rendered separately from the round header because line order
    interleaves launder announcements between the two.)
    """
    j: int
    value: int

@dataclass(frozen=True)
class RoundStarted(Event):
    j: int
    num_vars: int
    var_name: str
    fixed_challenges: Tuple[int, ...]  # r_0..r_{j-1}
    bound_var_names: Tuple[str, ...]   # b_{j+1}..b_{v-1}

@dataclass(frozen=True)
class CheatAdvice(Event):
    """The INVISIBLE-TO-VERIFIER advice block shown to an interactive dishonest
    prover, up to (but not including) the input prompt."""
    j: int
    var_name: str
    true_poly: Poly
    carried_claim: int
    degree_bound: int
    suggestion: Optional[Poly]
    roots: Optional[Tuple[int, ...]]
    field_mod: int

@dataclass(frozen=True)
class AdviceBlockClosed(Event):
    """The END-INVISIBLE marker after the interactive prover's input."""

@dataclass(frozen=True)
class MachineForged(Event):
    """A machine prover forged this round's polynomial. Renders EMPTY: there is
    no one to show a machine prover's private reasoning to mid-run. It exists
    for the log/JSON and for future renderers."""
    j: int
    suggestion: Poly
    roots: Optional[Tuple[int, ...]]

@dataclass(frozen=True)
class PolynomialSent(Event):
    """P's message for round j, plus the verifier-side framing line."""
    j: int
    var_name: str
    poly: Poly

@dataclass(frozen=True)
class DegreeChecked(Event):
    j: int
    degree: object   # int, or sympy -oo for the zero polynomial (printed as-is)
    bound: int
    passed: bool
    prev_challenge: Optional[int] = None   # r_{j-1}; None in round 0. The renderer

@dataclass(frozen=True)
class ConsistencyChecked(Event):
    j: int
    prev_challenge: Optional[int]   # r_{j-1}; None in round 0 (LHS is the claim H*)
    lhs_value: int
    rhs_value: int
    passed: bool
    carried_claim: int    # for the j == 0 phrasing

@dataclass(frozen=True)
class Laundered(Event):
    """A challenge hit a root of a forged polynomial: the carried claim became
    TRUE and honest play suffices from now on. PROVER_PRIVATE when announced to
    an interactive prover; machine occurrences render EMPTY in the
    renderer (but exist in the log)."""
    j: int
    challenge: int
    announced: bool       # the block is printed only for an interactive prover
    at_final: bool = False

@dataclass(frozen=True)
class FinalCheckStarted(Event):
    pass

@dataclass(frozen=True)
class FinalClaimStated(Event):
    last_j: int
    last_challenge: int
    all_challenges: Tuple[int, ...]
    terminal_claim: int

@dataclass(frozen=True)
class OpeningPrompted(Event):
    """Toy-commitment mode: the caveat + reveal framing before P opens."""

@dataclass(frozen=True)
class OpeningRevealed(Event):
    poly: Optional[Poly]   # None: P provided nothing at the opening
    gens_str: str
    dishonest: bool
    announced_dishonest: bool  # red pre-announcement only when not secret

@dataclass(frozen=True)
class CommitmentChecked(Event):
    ok: bool
    original_hash: str
    recomputed_hash: str

@dataclass(frozen=True)
class OpenedEvaluation(Event):
    all_challenges: Tuple[int, ...]
    value: int

@dataclass(frozen=True)
class OracleQueried(Event):
    all_challenges: Tuple[int, ...]
    value: int

@dataclass(frozen=True)
class VerdictAnnounced(Event):
    accepted: bool
    initially_dishonest: bool
    true_sum: Optional[int]   # printed in the DECEIVED line when accepted despite a lie
    rejected_at_commitment: bool = False

@dataclass(frozen=True)
class GroundTruthRevealed(Event):
    g: Poly
    gens_str: str
    num_vars: int
    true_sum: int
    claimed_sum: int
    accepted: bool
    use_commitment: bool = False
    dishonest_opening: bool = False

@dataclass
class Transcript:
    """The interactive proof: P's messages and V's challenges, in order.

    This is exactly the PUBLIC slice of the event log, and exactly what a
    Fiat-Shamir transform would hash to make the proof non-interactive.
    """
    field_mod: int
    num_vars: int
    degree_bounds: List[int]
    claim: Optional[int] = None
    rounds: List[dict] = field(default_factory=list)   # {"j", "polynomial", "challenge"}
    final: dict = field(default_factory=dict)
    verdict: Optional[str] = None

    @classmethod
    def from_events(cls, events: Sequence[Event], *, field_mod: int) -> "Transcript":
        t = cls(field_mod=field_mod, num_vars=0, degree_bounds=[])
        pending: dict = {}
        for e in events:
            if isinstance(e, ProtocolInitialized):
                t.num_vars = e.num_vars
                t.degree_bounds = list(e.degree_bounds)
                if e.commit_hash is not None:
                    t.final["commitment"] = e.commit_hash
            elif isinstance(e, ClaimAnnounced):
                t.claim = e.claim
            elif isinstance(e, PolynomialSent):
                pending = {"j": e.j, "polynomial": _poly_record(e.poly)}
            elif isinstance(e, ChallengeSampled):
                if pending.get("j") == e.j:
                    pending["challenge"] = e.value
                    t.rounds.append(pending)
                    pending = {}
                else:  # final challenge with no pending message (defensive)
                    t.final["challenge"] = e.value
            elif isinstance(e, FinalClaimStated):
                # the last challenge closes the last round
                if pending:
                    pending["challenge"] = e.last_challenge
                    t.rounds.append(pending)
                    pending = {}
                t.final["challenge"] = e.last_challenge
                t.final["terminal_claim"] = e.terminal_claim
            elif isinstance(e, OpeningRevealed):
                t.final["opened_polynomial"] = _poly_record(e.poly)
            elif isinstance(e, CommitmentChecked):
                t.final["commitment_check"] = {
                    "ok": e.ok,
                    "original": e.original_hash,
                    "recomputed": e.recomputed_hash,
                }
            elif isinstance(e, (OracleQueried, OpenedEvaluation)):
                t.final["oracle_value"] = e.value
            elif isinstance(e, VerdictAnnounced):
                t.verdict = "accepted" if e.accepted else "rejected"
        return t

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(asdict(self), indent=indent)

    def save(self, path: Union[str, Path]) -> Path:
        path = Path(path)
        path.write_text(self.to_json() + "\n", encoding="utf-8")
        return path