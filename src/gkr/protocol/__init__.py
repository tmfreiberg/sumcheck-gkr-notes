"""
gkr.protocol: the engine, parties, events and renderers for both protocols.

    core.py            the shared vocabulary: Audience, Event, Sink, the views,
                       and make_routing_renderer
    commitment.py      a toy polynomial commitment
    secrets.py         the prover's private channel, for live presentations
    sumcheck_*.py      the sum-check family: engine, parties, events, render,
                       cheats, session
    gkr_*.py           the GKR family, same shape, plus support

Every event carries an audience tag; a view is a set of audiences; a renderer
shows an event iff its tag is in the active view. GKR's engine drives the
sum-check engine layer by layer.
"""
from ..notation import DEFAULT_PALETTE, NOTEBOOK_NOTATION, Notation, Palette
from .core import PROVER_VIEW, SPECTATOR_VIEW, VERIFIER_VIEW, Audience, Sink
from .gkr_engine import GkrRunResult, run_gkr
from .gkr_events import GkrTranscript
from .gkr_parties import GkrInteractiveProver, GkrMachineProver
from .gkr_render import make_combined_renderer, make_gkr_renderer
from .gkr_session import gkr
from .gkr_support import choose_arithmetic_circuit
from .secrets import SecretsChannel
from .sumcheck_engine import (
    Aborted,
    Accepted,
    DeferredToCaller,
    PolynomialOracle,
    Rejected,
    SumCheckResult,
    TerminalValue,
    run_sum_check,
)
from .sumcheck_events import Transcript
from .sumcheck_parties import (
    Cancelled,
    HonestProver,
    InteractiveProver,
    InteractiveVerifier,
    MachineProver,
    NoOpening,
    RandomVerifier,
)
from .sumcheck_render import make_renderer
from .sumcheck_session import sum_check

__all__ = [
    "Audience", "Sink", "Transcript",
    "VERIFIER_VIEW", "PROVER_VIEW", "SPECTATOR_VIEW",
    "Notation", "Palette", "NOTEBOOK_NOTATION", "DEFAULT_PALETTE",
    "Cancelled", "NoOpening",
    "HonestProver", "MachineProver", "InteractiveProver",
    "RandomVerifier", "InteractiveVerifier",
    "make_renderer",
    "Accepted", "Rejected", "Aborted", "TerminalValue",
    "SumCheckResult", "PolynomialOracle", "DeferredToCaller",
    "run_sum_check", "sum_check", "SecretsChannel",
    "run_gkr", "GkrRunResult", "GkrTranscript",
    "GkrMachineProver", "GkrInteractiveProver",
    "make_gkr_renderer", "make_combined_renderer",
    "gkr", "choose_arithmetic_circuit",
]