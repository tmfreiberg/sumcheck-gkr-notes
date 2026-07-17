"""
The interactive GKR session: prompts, parties, and the epilogue.

Mirrors gkr.protocol.sumcheck_session: the mode and role prompts happen here,
the protocol runs through `run_gkr`, and the ground-truth epilogue is emitted as
a GROUND_TRUTH event. `secrets_to` routes the prover's private events to a file
so a presenter can play prover at a shared screen; see gkr.protocol.secrets.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from ..ac import ArithmeticCircuit, CircuitError
from ..utils.display import RED, RESET, YELLOW, TerminalOutput, stringify
from ..utils.display import out as default_out
from .core import SPECTATOR_VIEW, VERIFIER_VIEW, Audience, Sink, make_routing_renderer
from .gkr_engine import run_gkr
from .gkr_events import (
    GkrGroundTruth,
    GkrInitialized,
    GkrTranscript,
    TrueOutputsShown,
)
from .gkr_parties import GkrInteractiveProver, GkrMachineProver
from .gkr_render import make_combined_renderer
from .gkr_support import _label_bitlength, choose_arithmetic_circuit, validate_for_gkr
from .secrets import SecretsChannel
from .sumcheck_parties import InteractiveVerifier, RandomVerifier


def gkr(
    ac: Optional[ArithmeticCircuit] = None,
    *,
    secret_mode: Optional[bool] = None,
    secrets_to: Optional[Union[str, Path]] = None,
    interactive: Optional[bool] = None,
    dishonest_claim: Optional[bool] = None,
    show_steps: bool = True,
    out: TerminalOutput = default_out,
    save_transcript: Optional[Union[str, Path]] = None,
) -> Optional[bool]:
    """Interactive GKR session. Returns True (V accepted), False (V rejected),
    or None (aborted). If `save_transcript` is given, the PUBLIC slice of the
    event log -- the proof -- is written there as JSON.

    `secrets_to` is presentation mode, exactly as in sum_check: you play prover
    at a shared screen, the audience plays verifier, and everything
    prover-private (the true output values, the per-round cheat advice, which
    depends on challenges the audience just called out) is appended to that file
    instead of the screen. Watch it in a second terminal with `gkr watch PATH`.
    Implies secret_mode. Playing prover with secret_mode but no secrets file is
    refused -- your entitlements and the audience's screen would be fighting over
    one output."""
    if hasattr(out, "flush"):
        out.flush()

    # ---- interactivity and roles (mirrors sum_check) ----
    # interactive / dishonest_claim default to None, meaning "ask". Supplying
    # them settles the question silently, which is what a scripted worked
    # example needs -- see gkr.examples.gkr_example.
    if interactive is None:
        interactive_input = out.input("\nDo you want this to be interactive? (y/n): ")
        user_input = interactive_input.strip().lower() == 'y'
    else:
        user_input = interactive
    if not user_input and interactive is None:
        out.print("\nAlthough you've selected non-interative mode, responses to a few prompts are still required...")

    user_is_verifier: bool = False
    user_is_prover: bool = False

    if user_input:
        user_selection_prover = out.input("Do you want to act as prover? (y/n): ")
        user_selection_verifier = out.input("Do you want to act as verifier? (y/n): ")
        user_is_prover = user_selection_prover.strip().lower() == 'y'
        user_is_verifier = user_selection_verifier.strip().lower() == 'y'

    if secret_mode is None:
        secret_mode = (user_is_verifier and not user_is_prover) or (
            secrets_to is not None and user_is_prover
        )

    if secret_mode and user_is_prover and secrets_to is None:
        out.print(
            f"\n{RED}You asked to hide prover secrets while playing prover, with nowhere "
            f"to send them.{RESET} The true output values and the cheat advice cannot appear "
            f"on the shared screen, but you need them to play. Pass secrets_to=<path> and "
            f"watch that file with 'gkr watch' in a second terminal, or drop secret_mode."
        )
        return None

    # ---- field and circuit ----
    if ac is None:
        ac = choose_arithmetic_circuit(out=out)
        if ac is None:
            out.print(f"\n{YELLOW}Protocol aborted.{RESET}")
            return None
    else:
        # A supplied circuit is already well-formed -- ArithmeticCircuit raises
        # rather than handing back a broken object -- so only GKR's own
        # requirements need checking, by the same validator the prompt uses.
        try:
            validate_for_gkr(ac)
        except CircuitError as e:
            out.print(f"\n{RED}The supplied circuit cannot be used for GKR{RESET}: {e}.")
            if e.hint:
                out.print(f"\n{e.hint}")
            return None

    F = ac.field
    assert ac.depth is not None  # validate_for_gkr guarantees a fully built circuit
    d: int = ac.depth
    s_list = [_label_bitlength(ac, layer) for layer in range(d + 1)]
    S_list = [len(ac.layers[layer]) for layer in range(d + 1)]

    # ---- views and routes (mirrors sum_check) ----
    # View is what a role may know; a route is where it goes. The shared screen
    # gets the verifier's view when anything is secret and the spectator's view
    # otherwise; a secrets file, if given, gets exactly the PROVER_PRIVATE
    # events -- the presenter's side channel.
    screen_view = VERIFIER_VIEW if secret_mode else SPECTATOR_VIEW
    secrets_channel: Optional[SecretsChannel] = None

    if secrets_to is not None:
        secrets_channel = SecretsChannel(secrets_to)
        renderer = make_routing_renderer([
            (screen_view, make_combined_renderer(out=out, field=F, view=screen_view)),
            (frozenset({Audience.PROVER_PRIVATE}),
             make_combined_renderer(out=secrets_channel, field=F,
                                    view=frozenset({Audience.PROVER_PRIVATE}))),
        ])
        out.print(f"\nProver secrets will be appended to: {secrets_channel.path}")
    else:
        renderer = make_combined_renderer(out=out, field=F, view=screen_view)

    sink = Sink(renderer)

    # ---- initialization ----
    input_items = sorted(ac.W_dict[d].items())
    inputs_str = ", ".join(f"W_{d}({stringify(lbl)}) = {int(v)}" for lbl, v in input_items)
    sink.emit(GkrInitialized(
        audience=Audience.PUBLIC,
        ac=ac,
        depth=d,
        layer_sizes=tuple(S_list),
        label_bitlengths=tuple(s_list),
        inputs_str=inputs_str,
    ))

    true_outputs = {label: int(v) for label, v in ac.W_dict[0].items()}
    output_labels = sorted(true_outputs.keys())
    truth_str = ", ".join(f"W_0({stringify(lbl)}) = {true_outputs[lbl]}" for lbl in output_labels)
    sink.emit(TrueOutputsShown(audience=Audience.NARRATOR, truth_str=truth_str))

    # ---- parties ----
    prover: Union[GkrInteractiveProver, GkrMachineProver]
    if user_is_prover:
        prover = GkrInteractiveProver(ac, sink, secret_mode=bool(secret_mode), out=out)
    else:
        prover = GkrMachineProver(ac, sink, secret_mode=bool(secret_mode),
                                  dishonest_claim=dishonest_claim, out=out)
    verifier = InteractiveVerifier(F, out=out) if user_is_verifier else RandomVerifier(F, out=out)

    result = run_gkr(ac, prover=prover, verifier=verifier, sink=sink, out=out)

    if result.status == "abort_claims":
        return None   # the party printed its own abort message
    if result.status == "abort":
        out.print(f"\n{YELLOW}Protocol aborted.{RESET}")
        return None

    accepted = (result.status == "accept")

    assert result.claims is not None  # every non-abort status carries claims
    claims_str = ", ".join(f"W*_0({stringify(lbl)}) = {result.claims[lbl]}" for lbl in output_labels)
    sink.emit(GkrGroundTruth(
        audience=Audience.GROUND_TRUTH,
        truth_str=truth_str,
        claims_str=claims_str,
        notes=tuple(result.notes),
        accepted=accepted,
        initial_claim_false=result.initial_claim_false,
    ))

    if save_transcript is not None:
        GkrTranscript.from_events(sink.log, field_mod=int(F.mod)).save(save_transcript)

    if secrets_channel is not None:
        secrets_channel.close()

    if hasattr(out, "flush"):
        out.flush()
    return accepted