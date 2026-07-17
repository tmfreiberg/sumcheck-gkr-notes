"""
GKR events, and the GkrTranscript: the PUBLIC slice of a run, i.e. the proof.

Several events here are composites carrying a whole narrated block rather than a
single fact, and the ground-truth ledger is accumulated mid-run but rendered
once, inside GkrGroundTruth, at the end.

The shared vocabulary (Audience, Event, Sink, the views) is in core.py;
sum-check's events are in sumcheck_events.py.
"""
from __future__ import annotations

import json as _json
from dataclasses import asdict as _asdict
from dataclasses import dataclass
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field
from pathlib import Path as _Path
from typing import TYPE_CHECKING, Optional, Tuple
from typing import (
    List as _List,
)
from typing import (
    Optional as _Optional,
)
from typing import (
    Sequence as _Sequence,
)
from typing import (
    Union as _Union,
)

from sympy import Poly

if TYPE_CHECKING:
    from ..ac import ArithmeticCircuit

from .core import Event, _poly_record
from .sumcheck_events import PolynomialSent as _PolynomialSent

# ---- initialization ---------------------------------------------------------

@dataclass(frozen=True)
class GkrInitialized(Event):
    """The Initialization block: circuit facts, public information, inputs.
    Carries the ArithmeticCircuit for the renderer (graphviz in notebooks)."""
    ac: "ArithmeticCircuit"
    depth: int
    layer_sizes: Tuple[int, ...]       # S_0..S_d
    label_bitlengths: Tuple[int, ...]  # s_0..s_d
    inputs_str: str


@dataclass(frozen=True)
class TrueOutputsShown(Event):
    """Narrator aside: the true output(s), displayed for the reader."""
    truth_str: str


@dataclass(frozen=True)
class ClaimsPhaseStarted(Event):
    """The 'Claimed output(s)' header."""


@dataclass(frozen=True)
class OutputsClaimed(Event):
    claims_str: str


@dataclass(frozen=True)
class ClaimedOutputsDishonest(Event):
    """Narrator aside: this run's claimed output(s) are intentionally false."""


@dataclass(frozen=True)
class MleFormed(Event):
    """W-tilde*_0 formation, and the uniqueness line."""
    s0: int
    num_outputs: int


@dataclass(frozen=True)
class RhoSamplingStarted(Event):
    s0: int


@dataclass(frozen=True)
class Rho0Announced(Event):
    point: Tuple[int, ...]
    trivial: bool          # s0 == 0: the '()' convention paragraph instead


@dataclass(frozen=True)
class Alpha0Computed(Event):
    alpha: int


@dataclass(frozen=True)
class InitialLieOdds(Event):
    """Narrator aside after a false claim: certainty (s0=0) or the
    Schwartz-Zippel bound, plus the 'Remarkably' note if rho_0 laundered the
    lie before the protocol started."""
    s0: int
    field_mod: int
    laundered_at_start: bool


# ---- layer transition -------------------------------------------------------

@dataclass(frozen=True)
class LayerStarted(Event):
    """Header + Thaler-identity preamble + degree-bounds line."""
    i: int
    rho_i: Tuple[int, ...]
    alpha_i: int
    m: int                              # 2 * s_next
    s_next: int
    x_names: Tuple[str, ...]
    y_names: Tuple[str, ...]


@dataclass(frozen=True)
class LayerSummandShown(Event):
    """Narrator aside: g displayed for the reader (V cannot compute it)."""
    i: int
    g_poly: Poly
    x_names: Tuple[str, ...]
    y_names: Tuple[str, ...]


@dataclass(frozen=True)
class LayerLieNote(Event):
    """Narrator aside: the carried claim is false; P is forced to forge."""
    i: int
    w_true: int
    alpha_i: int


@dataclass(frozen=True)
class LayerSumCheckFailed(Event):
    i: int


@dataclass(frozen=True)
class BridgingIntroduced(Event):
    """Post-sum-check narration: terminal claim gamma, wiring values A and M,
    and the bridging equation."""
    i: int
    m: int
    gamma: int
    r_x: Tuple[int, ...]
    r_y: Tuple[int, ...]
    A: int
    M: int


@dataclass(frozen=True)
class SumCheckLaunderNote(Event):
    """Narrator aside: a challenge laundered the lie during this sum-check."""
    i: int


# ---- final layer -------------------------------------------------------------

@dataclass(frozen=True)
class GkrFinalCheck(Event):
    """The final-layer check against the public inputs, including the verdict
    and (audience GROUND_TRUTH: shown in every view) the
    DECEIVED / Interpretation lines."""
    i: int
    depth: int
    z_x: int
    z_y: int
    gamma: int
    rhs: int
    accepted: bool
    initial_claim_false: bool


# ---- folding ------------------------------------------------------------------

@dataclass(frozen=True)
class FoldingStarted(Event):
    """Header + 'V cannot check the bridging equation alone' preamble."""
    i: int


@dataclass(frozen=True)
class HonestAfterLaunder(Event):
    """Narrator aside: the laundered truth satisfies the bridge; P plays honestly."""
    i: int


@dataclass(frozen=True)
class CaughtImpossible(Event):
    """Narrator aside: A = M = 0 with gamma != 0; no pair can satisfy the bridge."""
    i: int


@dataclass(frozen=True)
class VacuousBridge(Event):
    """Narrator aside: A = M = 0 and gamma = 0; the lie evaporates."""
    i: int


@dataclass(frozen=True)
class TrueOutputRevealed(Event):
    """The true value of one output gate, told to the prover (who is entitled to
    it) just before being asked to claim it. Travels as an event, not inside the
    prompt string, so that on a routed run it lands on the prover's private
    channel while the shared screen shows a neutral prompt."""
    label_str: str
    value: int


@dataclass(frozen=True)
class EndpointAdvice(Event):
    """Interactive prover's INVISIBLE block before the endpoint prompt."""
    i: int
    z_x_true: int
    z_y_true: int
    gamma: int
    A: int
    M: int
    kept: Optional[str]        # "x" | "y" | None (generic)
    zx_suggestion: int
    zy_suggestion: int


@dataclass(frozen=True)
class EndpointForgeNote(Event):
    """Machine prover's narrator note describing which endpoint was forged."""
    i: int
    kept: Optional[str]


@dataclass(frozen=True)
class AdviceClosed(Event):
    """END-INVISIBLE marker (endpoint or q* advice)."""


@dataclass(frozen=True)
class EndpointsSent(Event):
    i: int
    zx_star: int
    zy_star: int


@dataclass(frozen=True)
class BridgingChecked(Event):
    i: int
    gamma: int
    rhs: int
    passed: bool


@dataclass(frozen=True)
class QIntroduced(Event):
    """The two-claims-fold-to-one narration: the line ell, q, and V's checks."""
    i: int
    s_next: int


@dataclass(frozen=True)
class QAdvice(Event):
    """Interactive prover's INVISIBLE block before the q* prompt."""
    i: int
    s_next: int
    field_mod: int
    q_true: Poly
    z_x_true: int
    z_y_true: int
    suggestion: Poly
    roots: Tuple[int, ...]


@dataclass(frozen=True)
class QForgeNote(Event):
    """Machine prover's narrator note: q* forged, with the planted roots."""
    i: int
    roots: Tuple[int, ...]


@dataclass(frozen=True)
class QSent(Event):
    i: int
    q_star: Poly


@dataclass(frozen=True)
class QDegreeChecked(Event):
    i: int
    degree: object   # int, or sympy -oo for the zero polynomial (printed as-is)
    s_next: int
    passed: bool


@dataclass(frozen=True)
class QEndpointsChecked(Event):
    i: int
    q0: int
    q1: int
    zx_star: int
    zy_star: int
    passed: bool


@dataclass(frozen=True)
class TauSampledAndFolded(Event):
    i: int
    tau: int
    rho_next: Tuple[int, ...]
    alpha_next: int


@dataclass(frozen=True)
class FoldLaunderAnnounced(Event):
    """Interactive prover's red DECEIVED block: tau hit a planted root."""
    i: int


@dataclass(frozen=True)
class FoldLaunderNote(Event):
    """Machine-run narrator note: tau hit a planted root; the lie is laundered."""
    i: int
    tau: int


# ---- ground-truth ledger -----------------------------------------------------
#
# The engine accumulates these mid-run but they are printed only in the
# epilogue, so a streaming renderer cannot defer them: they travel as data
# inside GkrGroundTruth. They are *structured* rather than preformatted, so
# that the renderer -- not the engine -- owns their wording and notation.

@dataclass(frozen=True)
class Note:
    """A ground-truth ledger entry."""
    i: int


@dataclass(frozen=True)
class CarriedClaimWasFalse(Note):
    alpha: int
    true_value: int


@dataclass(frozen=True)
class LaunderedInSumCheck(Note):
    pass


@dataclass(frozen=True)
class SumCheckRejected(Note):
    pass


@dataclass(frozen=True)
class FinalCheckFailed(Note):
    pass


@dataclass(frozen=True)
class BridgeVacuous(Note):
    pass


@dataclass(frozen=True)
class EndpointForged(Note):
    kept: Optional[str]     # "x" | "y" | None (both forged)


@dataclass(frozen=True)
class BridgeFailed(Note):
    pass


@dataclass(frozen=True)
class QForged(Note):
    roots: Tuple[int, ...]


@dataclass(frozen=True)
class QDegreeViolated(Note):
    pass


@dataclass(frozen=True)
class QEndpointsMismatched(Note):
    pass


@dataclass(frozen=True)
class FoldLaundered(Note):
    tau: int


# ---- ground truth --------------------------------------------------------------

@dataclass(frozen=True)
class GkrGroundTruth(Event):
    truth_str: str
    claims_str: str
    notes: Tuple[Note, ...]
    accepted: bool
    initial_claim_false: bool


# ----------------------------------------------------------------------------
# GkrTranscript: the PUBLIC slice of a GKR run, i.e. the proof itself
# ----------------------------------------------------------------------------


@_dataclass
class GkrTranscript:
    """The GKR proof: per layer, the inner sum-check messages and challenges,
    the claimed endpoints, the restriction q*, and the fold challenge tau --
    exactly the PUBLIC events, exactly what Fiat-Shamir would hash."""
    field_mod: int
    depth: int = 0
    claims: _Optional[str] = None
    rho_0: _Optional[list] = None
    alpha_0: _Optional[int] = None
    layers: _List[dict] = _field(default_factory=dict().copy if False else list)
    verdict: _Optional[str] = None

    @classmethod
    def from_events(cls, events: _Sequence, *, field_mod: int) -> "GkrTranscript":
        t = cls(field_mod=field_mod)
        layer: _Optional[dict] = None
        for e in events:
            if isinstance(e, GkrInitialized):
                t.depth = e.depth
            elif isinstance(e, OutputsClaimed):
                t.claims = e.claims_str
            elif isinstance(e, Rho0Announced):
                t.rho_0 = list(e.point)
            elif isinstance(e, Alpha0Computed):
                t.alpha_0 = e.alpha
            elif isinstance(e, LayerStarted):
                layer = {"i": e.i, "alpha_i": e.alpha_i, "polynomials": []}
                t.layers.append(layer)
            elif isinstance(e, _PolynomialSent) and layer is not None:
                layer["polynomials"].append(_poly_record(e.poly))
            elif isinstance(e, BridgingIntroduced) and layer is not None:
                layer["challenges"] = list(e.r_x) + list(e.r_y)
                layer["gamma"] = e.gamma
            elif isinstance(e, EndpointsSent) and layer is not None:
                layer["endpoints"] = {"zx_star": e.zx_star, "zy_star": e.zy_star}
            elif isinstance(e, QSent) and layer is not None:
                layer["q_star"] = _poly_record(e.q_star)
            elif isinstance(e, TauSampledAndFolded) and layer is not None:
                layer["tau"] = e.tau
                layer["rho_next"] = list(e.rho_next)
                layer["alpha_next"] = e.alpha_next
            elif isinstance(e, GkrFinalCheck):
                t.verdict = "accepted" if e.accepted else "rejected"
            elif isinstance(e, (LayerSumCheckFailed, BridgingChecked, QDegreeChecked, QEndpointsChecked)):
                if getattr(e, "passed", True) is False or isinstance(e, LayerSumCheckFailed):
                    t.verdict = "rejected"
        return t

    def to_json(self, indent: int = 2) -> str:
        return _json.dumps(_asdict(self), indent=indent)

    def save(self, path: _Union[str, _Path]) -> _Path:
        path = _Path(path)
        path.write_text(self.to_json() + "\n", encoding="utf-8")
        return path