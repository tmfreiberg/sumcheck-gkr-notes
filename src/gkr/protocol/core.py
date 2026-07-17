"""
The shared vocabulary of the protocol layer.

Everything both protocols need and neither owns: the Audience tag every event
carries, the views (which audiences a role may see), the Sink that logs and
renders, and make_routing_renderer, which sends one event stream to several
destinations at once (see gkr.protocol.secrets).

Protocol-specific events live in sumcheck_events.py and gkr_events.py; this
module deliberately knows about neither. The symmetry is the point: sumcheck_*
and gkr_* are two families over one core.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, FrozenSet, List, Optional, Sequence, Tuple

from sympy import Poly


class Audience(Enum):
    PUBLIC = auto()           # protocol messages: what P and V exchange
    PROVER_PRIVATE = auto()   # P's private reasoning: truths, advice, roots
    NARRATOR = auto()         # asides to the reader
    GROUND_TRUTH = auto()     # the post-protocol reveal

VERIFIER_VIEW = frozenset({Audience.PUBLIC, Audience.GROUND_TRUTH})

PROVER_VIEW = frozenset({Audience.PUBLIC, Audience.PROVER_PRIVATE, Audience.GROUND_TRUTH})

SPECTATOR_VIEW = frozenset(
    {Audience.PUBLIC, Audience.PROVER_PRIVATE, Audience.NARRATOR, Audience.GROUND_TRUTH}
)

@dataclass(frozen=True)
class Event:
    audience: Audience

def make_routing_renderer(
    routes: Sequence[Tuple[FrozenSet["Audience"], Callable[["Event"], None]]],
) -> Callable[["Event"], None]:
    """Send each event to every renderer whose audience-set contains its tag.

    This is the presentation-mode primitive: a shared screen and a private
    channel are just two routes over the same event stream --

        make_routing_renderer([
            (VERIFIER_VIEW, screen_renderer),          # the audience's screen
            (frozenset({Audience.PROVER_PRIVATE}),
             secrets_renderer),                        # the prover's side channel
        ])

    View selects *what a role may know*; a route selects *where it goes*. One
    renderer per run conflated the two, which is why 'secret mode with a user
    prover' used to be self-contradictory: the prover's entitlements and the
    audience's screen fought over a single output.
    """
    frozen = [(frozenset(view), render) for view, render in routes]

    def render(event: "Event") -> None:
        for view, r in frozen:
            if event.audience in view:
                r(event)

    return render

class Sink:
    """Appends every event to a log and renders it eagerly (streaming), so that
    party prompts interleave correctly with narration."""

    def __init__(self, renderer: Optional[Callable[[Event], None]] = None):
        self.log: List[Event] = []
        self._renderer = renderer

    def emit(self, event: Event) -> None:
        self.log.append(event)
        if self._renderer is not None:
            self._renderer(event)

def _poly_record(poly: Poly) -> dict:
    return {
        "gens": [str(g) for g in poly.gens],
        # all_coeffs for univariate; dict form is degree-robust either way
        "terms": {str(monom): int(coeff) for monom, coeff in poly.terms()},
        "expr": str(poly.as_expr()),
    }