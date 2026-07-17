"""
The interactive sum-check session: prompts, parties, and the epilogue.

Everything the user sees before the Initialization header (mode prompts,
polynomial entry, scenario prompts) happens here; the protocol itself then runs
through `gkr.protocol.sumcheck_engine.run_sum_check` with the chosen parties,
and the ground-truth epilogue is emitted as a GROUND_TRUTH event.

RNG discipline: the golden transcripts pin a run byte for byte, so the sequence
of `random.*` calls is part of the contract. It is: [scenario coin(s) for option
(b)], then [the dishonest-H* draw loop], then [one challenge draw per round].
The scenario coins fire at the prompts below; the H* draws live in
MachineProver.sum_value, before any challenge is drawn; challenges are drawn by
the verifier party, one per round. No other code consumes randomness.

Known quirk: with a *user* prover in commitment mode, the session-level
`dishonest_opening` flag stays False regardless of what the user opens with, so
the ground-truth block can report "opened the correct polynomial" after a
dishonest interactive opening. The renderer now reads the opening's honesty
from the log (OpeningRevealed.dishonest) instead, but this flag remains.
"""
from __future__ import annotations

import random
from itertools import product
from pathlib import Path
from typing import Optional, Union

from sympy import isprime

from ..prompts import choose_polynomial
from ..utils.display import RED, RESET, YELLOW, TerminalOutput, stringify
from ..utils.display import out as default_out
from .commitment import poly_commitment_sha256
from .core import SPECTATOR_VIEW, VERIFIER_VIEW, Audience, Sink, make_routing_renderer
from .secrets import SecretsChannel
from .sumcheck_engine import (
    Aborted,
    Accepted,
    PolynomialOracle,
    run_sum_check,
)
from .sumcheck_events import GroundTruthRevealed, OpeningRevealed, ProtocolInitialized, Transcript
from .sumcheck_parties import (
    InteractiveProver,
    InteractiveVerifier,
    MachineProver,
    RandomVerifier,
)
from .sumcheck_render import make_renderer


def sum_check(
    out: TerminalOutput = default_out,
    *,
    use_commitment: bool = False,
    secret_mode: Optional[bool] = None,
    secrets_to: Optional[Union[str, Path]] = None,
    save_transcript: Optional[Union[str, Path]] = None,
) -> Optional[bool]:
    """Interactive sum-check session. Returns True (V accepted), False
    (V rejected), or None (aborted / invalid input).

    If `save_transcript` is given, the PUBLIC slice of the event log -- the
    proof itself: P's messages and V's challenges -- is written there as JSON.

    `secrets_to` is presentation mode: you play prover at a shared screen, the
    audience plays verifier, and everything prover-private (the true H, the
    mid-run cheat advice) is appended to that file instead of the screen. Watch
    it on a second device with `tail -f` (or `Get-Content -Wait`). Implies
    secret_mode unless overridden. Playing prover with secret_mode but WITHOUT
    a secrets file is refused: your entitlements and the audience's screen
    would be fighting over one output -- which is the contradiction this
    parameter exists to resolve.
    """
    # Start fresh so the first header doesn't appear mid-page
    if hasattr(out, "flush"):
        out.flush()

    # Prompt user for interactive mode
    interactive_input = out.input("\nDo you want this to be interactive? (y/n): ")
    user_input = interactive_input.strip().lower() == 'y'
    if not user_input:
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
            f"to send them.{RESET} The true H and the cheat advice cannot appear on the "
            f"shared screen, but you need them to play. Pass secrets_to=<path> and watch "
            f"that file on a second device (tail -f), or drop secret_mode."
        )
        return None

    # Get the polynomial from the user
    g = choose_polynomial(secret_mode_for_poly=secret_mode, out=out)
    if g is None:
        return None

    if not isprime(g.domain.mod):
        out.print("Sorry, we can only handle prime fields at present.")
        return None

    commit_hash = poly_commitment_sha256(g) if use_commitment else None

    dishonest_claim: bool = False
    dishonest_opening: bool = False

    if use_commitment:
        if not user_is_prover:
            opening_selection = out.input(
                "\nChoose a, b, or c: About the opened polynomial g, the prover will be "
                "(a) honest. "
                "(b) honest with probability 1/2. "
                "(c) dishonest.",
                hidden=secret_mode,
            ).strip().lower()

            if opening_selection == "a":
                dishonest_opening = False
            elif opening_selection == "b":
                dishonest_opening = bool(random.randint(0, 1))
            else:  # c or anything other than a or b
                dishonest_opening = True
        else:
            # Prover will decide later at opening time.
            dishonest_opening = False  # irrelevant for prover-driven opening
            out.print(
                "\nAt the end, the prover will choose what to open with."
                )

    if not user_is_prover:
        dishonesty_selection = out.input(
            "\nChoose a, b, or c: About the value of H (the sum of g over the Boolean hypercube), the prover will be "
            "(a) honest. "
            "(b) honest with probability 1/2. "
            "(c) dishonest.",
            hidden=secret_mode,
            ).strip().lower()

        if dishonesty_selection == "a":
            dishonest_claim = False
        elif dishonesty_selection == "b":
            dishonest_claim = bool(random.randint(0, 1))
        else:  # c or anything other than a or b
            dishonest_claim = True

    X = g.gens
    v = len(X)
    F = g.domain

    # The true sum over the Boolean hypercube
    H = F(sum(
        g.eval({X[k]: b_k for k, b_k in enumerate(b)})
        for b in product([F(0), F(1)], repeat=v)
    ))

    # ---- views and routes ----------------------------------------------------
    # View selects what a role may know; a route selects where it goes. The
    # shared screen gets the verifier's view when anything is secret, and the
    # spectator's view otherwise. A secrets file, if given, gets exactly the
    # PROVER_PRIVATE events -- the presenter's side channel.
    screen_view = VERIFIER_VIEW if secret_mode else SPECTATOR_VIEW
    secrets_channel: Optional[SecretsChannel] = None

    if secrets_to is not None:
        secrets_channel = SecretsChannel(secrets_to)
        renderer = make_routing_renderer([
            (screen_view, make_renderer(out=out, field=F, view=screen_view)),
            (frozenset({Audience.PROVER_PRIVATE}),
             make_renderer(out=secrets_channel, field=F,
                           view=frozenset({Audience.PROVER_PRIVATE}))),
        ])
        out.print(f"\nProver secrets will be appended to: {secrets_channel.path}")
    else:
        renderer = make_renderer(out=out, field=F, view=screen_view)

    sink = Sink(renderer)
    degree_bounds = [int(g.degree(gen)) for gen in X]

    sink.emit(ProtocolInitialized(
        audience=Audience.PUBLIC,
        g=g,
        degree_bounds=tuple(degree_bounds),
        num_vars=v,
        use_commitment=use_commitment,
        commit_hash=commit_hash,
    ))

    # ---- parties -------------------------------------------------------------
    prover: Union[InteractiveProver, MachineProver]
    if user_is_prover:
        prover = InteractiveProver(g, H, sink, secret_mode=bool(secret_mode), out=out)
    else:
        prover = MachineProver(
            g, H, sink,
            dishonest_claim=dishonest_claim,
            dishonest_opening=dishonest_opening,
        )
    verifier = InteractiveVerifier(F, out=out) if user_is_verifier else RandomVerifier(F, out=out)
    oracle = PolynomialOracle(g, use_commitment=use_commitment, commit_hash=commit_hash)

    result = run_sum_check(
        field=F,
        gens=X,
        degree_bounds=degree_bounds,
        prover=prover,
        verifier=verifier,
        oracle=oracle,
        sink=sink,
        out=out,
    )

    if isinstance(result.verdict, Aborted):
        if result.verdict.stage == "claim":
            out.print(f"\n{YELLOW}Aborting: invalid H* input.{RESET}")
        else:
            out.print(f"\n{YELLOW}Protocol aborted.{RESET}")
        return None

    accepted = isinstance(result.verdict, Accepted)

    # What was actually opened, read off the event log rather than from a flag
    # decided before the run. (This reports the session-level flag,
    # which is never set for a user prover -- so an interactive dishonest
    # opening was reported in Ground truth as "opened the correct polynomial".)
    ground_truth_opening = any(
        isinstance(e, OpeningRevealed) and e.dishonest for e in sink.log
    )

    sink.emit(GroundTruthRevealed(
        audience=Audience.GROUND_TRUTH,
        g=g,
        gens_str=stringify(X),
        num_vars=v,
        true_sum=int(H),
        claimed_sum=int(F.convert(result.claim)),
        accepted=accepted,
        use_commitment=use_commitment,
        dishonest_opening=ground_truth_opening,
    ))

    if save_transcript is not None:
        Transcript.from_events(sink.log, field_mod=int(F.mod)).save(save_transcript)

    if secrets_channel is not None:
        secrets_channel.close()

    if hasattr(out, "flush"):
        out.flush()
    return accepted