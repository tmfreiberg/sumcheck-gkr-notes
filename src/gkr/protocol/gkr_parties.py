"""
GKR parties.

Role-dependent narration is emitted by the party that owns it: the interactive
prover emits PROVER_PRIVATE advice blocks and DECEIVED announcements; the
machine prover emits NARRATOR asides. The engine computes every cheat
*suggestion* -- so the omniscient bookkeeping and the ground-truth ledger stay
in one place -- and hands them to the party, which decides what to actually
send.

Inner sum-check provers: each layer's sum-check reuses the top-level prover
machinery with two overrides. The claim is preset (alpha_i: no prompt, no
announcement, no RNG draw), and the lying state is initialised from the bridging
truth rather than from a scenario choice.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple, Union

from sympy import Poly, Symbol

from ..prompts import parse_poly
from ..utils.display import RED, RESET, YELLOW, TerminalOutput, stringify
from ..utils.display import out as default_out
from .core import Audience, Sink
from .gkr_events import (
    AdviceClosed,
    EndpointAdvice,
    EndpointForgeNote,
    FoldLaunderAnnounced,
    FoldLaunderNote,
    QAdvice,
    QForgeNote,
    TrueOutputRevealed,
)
from .gkr_support import _machine_claimed_outputs
from .sumcheck_parties import Cancelled, InteractiveProver, MachineProver

# ----------------------------------------------------------------------------
# Prompt helpers
# ----------------------------------------------------------------------------

def _prompt_endpoint_pair(
    *,
    field,
    suggestion,
    i: int,
    out: TerminalOutput,
    max_attempts: int = 3,
):
    """Let a user-prover accept the suggested (z*_x, z*_y) with 'y', type their own pair, or cancel."""
    prompt = (
        "\nEnter 'y' to send the suggested pair, type your own as 'z*_x, z*_y' "
        "(two integers), or type 'cancel' to abort: "
    )
    for attempt in range(1, max_attempts + 1):
        raw = out.input(prompt).strip()
        if raw.lower() == "cancel":
            return None
        if raw.lower() == "y":
            return suggestion
        parts = [s for s in raw.replace(",", " ").split() if s]
        try:
            if len(parts) != 2:
                raise ValueError("expected exactly two integers")
            zx = field.convert(int(parts[0]))
            zy = field.convert(int(parts[1]))
            return zx, zy
        except Exception as e:
            out.print(f"\nCould not parse the pair: {e}")
            if attempt < max_attempts:
                out.print(f"Try again ({attempt}/{max_attempts}).")
    return None


def _prompt_q_polynomial(
    *,
    field,
    suggestion: Poly,
    t: Symbol,
    i: int,
    out: TerminalOutput,
    max_attempts: int = 3,
) -> Optional[Poly]:
    """Let a user-prover accept the suggested q* with 'y', type their own polynomial in t, or cancel."""
    prompt = (
        f"\nEnter 'y' to send the suggested polynomial, type your own q*_{i + 1}(t), "
        f"or type 'cancel' to abort: "
    )
    for attempt in range(1, max_attempts + 1):
        raw = out.input(prompt).strip()
        if raw.lower() == "cancel":
            return None
        if raw.lower() == "y":
            return suggestion
        try:
            return parse_poly(raw, field=field, gens=[t], preferred_order=None, strict=True)
        except Exception as e:
            out.print(f"\nCould not parse polynomial: {e}")
            if attempt < max_attempts:
                out.print(f"Try again ({attempt}/{max_attempts}).")
    return None


# ----------------------------------------------------------------------------
# Inner sum-check provers (preset claim; silent sum_value)
# ----------------------------------------------------------------------------

class InnerMachineProver(MachineProver):
    def __init__(self, g: Poly, claim, sink: Sink, *, lying: bool):
        super().__init__(g, true_sum=claim, sink=sink, dishonest_claim=False)
        self.carried_claim = claim
        self.lying = lying

    def sum_value(self, ctx):
        return self.carried_claim


class InnerInteractiveProver(InteractiveProver):
    def __init__(self, g: Poly, claim, sink: Sink, *, secret_mode: bool,
                 out: TerminalOutput, lying: bool):
        super().__init__(g, true_sum=claim, sink=sink, secret_mode=secret_mode, out=out)
        self.carried_claim = claim
        self.lying = lying

    def sum_value(self, ctx):
        return self.carried_claim


# ----------------------------------------------------------------------------
# Contexts handed to GKR provers by the engine
# ----------------------------------------------------------------------------

class EndpointContext:
    def __init__(self, *, i, zx_suggestion, zy_suggestion, kept,
                 z_x_true, z_y_true, gamma, A, M):
        self.i = i
        self.zx_suggestion = zx_suggestion
        self.zy_suggestion = zy_suggestion
        self.kept = kept
        self.z_x_true = z_x_true
        self.z_y_true = z_y_true
        self.gamma = gamma
        self.A = A
        self.M = M


class QContext:
    def __init__(self, *, i, s_next, field_mod, q_true, z_x_true, z_y_true,
                 suggestion, roots, t):
        self.i = i
        self.s_next = s_next
        self.field_mod = field_mod
        self.q_true = q_true
        self.z_x_true = z_x_true
        self.z_y_true = z_y_true
        self.suggestion = suggestion
        self.roots = roots
        self.t = t


# ----------------------------------------------------------------------------
# GKR provers
# ----------------------------------------------------------------------------

class GkrMachineProver:
    """Machine prover: claims (optionally with one corrupted output), then
    forced-cheat play. Its private facts surface as NARRATOR notes -- the
    reader sees them; the verifier does not."""

    def __init__(self, ac, sink: Sink, *, secret_mode: bool,
                 dishonest_claim: Optional[bool] = None,
                 out: TerminalOutput = default_out):
        """`dishonest_claim=None` asks; True/False settles it without a prompt,
        which is what a scripted worked example needs."""
        self.ac = ac
        self.F = ac.field
        self.sink = sink
        self.secret_mode = secret_mode
        self.dishonest_claim = dishonest_claim
        self.out = out

    def claim_outputs(self, ctx) -> Union[Dict[Tuple[int, ...], int], Cancelled]:
        import random
        if self.dishonest_claim is not None:
            return _machine_claimed_outputs(self.ac, self.dishonest_claim)
        dishonesty_selection = self.out.input(
            "\nChoose a, b, or c: About the claimed circuit output(s), the prover will be "
            "(a) honest. "
            "(b) honest with probability 1/2. "
            "(c) dishonest.",
            hidden=self.secret_mode,
        ).strip().lower()
        if dishonesty_selection == "a":
            dishonest_claim = False
        elif dishonesty_selection == "b":
            dishonest_claim = bool(random.randint(0, 1))
        else:  # c or anything other than a or b
            dishonest_claim = True
        return _machine_claimed_outputs(self.ac, dishonest_claim)

    def inner_prover(self, g_poly: Poly, claim, *, lying: bool):
        return InnerMachineProver(g_poly, claim, self.sink, lying=lying)

    def endpoints(self, ctx: EndpointContext):
        self.sink.emit(EndpointForgeNote(
            audience=Audience.NARRATOR, i=ctx.i, kept=ctx.kept,
        ))
        return ctx.zx_suggestion, ctx.zy_suggestion

    def q_polynomial(self, ctx: QContext):
        self.sink.emit(QForgeNote(
            audience=Audience.NARRATOR, i=ctx.i,
            roots=tuple(int(z) for z in ctx.roots),
            s_next=int(ctx.s_next), field_mod=int(ctx.field_mod),
        ))
        return ctx.suggestion

    def notify_fold_laundered(self, i: int, tau: int) -> None:
        self.sink.emit(FoldLaunderNote(
            audience=Audience.NARRATOR, i=i, tau=int(tau),
        ))


class GkrInteractiveProver:
    """Human prover: enters claimed outputs; when forced to forge, is walked
    through the reasoning inside INVISIBLE-TO-VERIFIER blocks and can accept
    each suggestion with 'y', type their own, or cancel."""

    def __init__(self, ac, sink: Sink, *, secret_mode: bool,
                 out: TerminalOutput = default_out):
        self.ac = ac
        self.F = ac.field
        self.sink = sink
        self.secret_mode = secret_mode
        self.out = out

    def claim_outputs(self, ctx) -> Union[Dict[Tuple[int, ...], int], Cancelled]:
        F = self.F
        true_outputs = {label: int(v) for label, v in self.ac.W_dict[0].items()}
        output_labels = sorted(true_outputs.keys())
        claims: Dict[Tuple[int, ...], int] = {}
        for lbl in output_labels:
            true_v = true_outputs[lbl]
            # The true value is prover-private, and you are the prover: you need
            # it to decide whether to lie. It travels as an event rather than in
            # the prompt so that a routed run (secrets_to=...) sends it to the
            # private channel while the shared screen shows a neutral prompt.
            self.sink.emit(TrueOutputRevealed(
                audience=Audience.PROVER_PRIVATE,
                label_str=stringify(lbl),
                value=int(true_v),
            ))
            prompt = f"\nAs prover, enter your claim for output gate W_0({stringify(lbl)}): "
            value: Optional[int] = None
            for attempt in range(1, 4):
                raw = self.out.input(prompt, hidden=bool(self.secret_mode)).strip()
                if raw.lower() == "cancel":
                    self.out.print(f"\n{YELLOW}Protocol aborted.{RESET}")
                    return Cancelled()
                try:
                    value = int(F.convert(int(raw)))
                    break
                except Exception:
                    self.out.print(f"\nInvalid integer. Try again ({attempt}/3).")
            if value is None:
                self.out.print(f"\n{YELLOW}Aborting: invalid claimed output.{RESET}")
                return Cancelled()
            claims[lbl] = value
        return claims

    def inner_prover(self, g_poly: Poly, claim, *, lying: bool):
        return InnerInteractiveProver(
            g_poly, claim, self.sink,
            secret_mode=bool(self.secret_mode), out=self.out, lying=lying,
        )

    def endpoints(self, ctx: EndpointContext):
        self.sink.emit(EndpointAdvice(
            audience=Audience.PROVER_PRIVATE,
            i=ctx.i,
            z_x_true=int(ctx.z_x_true),
            z_y_true=int(ctx.z_y_true),
            gamma=int(ctx.gamma),
            A=int(ctx.A),
            M=int(ctx.M),
            kept=ctx.kept,
            zx_suggestion=int(ctx.zx_suggestion),
            zy_suggestion=int(ctx.zy_suggestion),
        ))
        pair = _prompt_endpoint_pair(
            field=self.F, suggestion=(ctx.zx_suggestion, ctx.zy_suggestion),
            i=ctx.i, out=self.out,
        )
        self.sink.emit(AdviceClosed(audience=Audience.PROVER_PRIVATE))
        if pair is None:
            self.out.print(f"\n{RED}Input cancelled or invalid too many times. Aborting this run.{RESET}")
            return Cancelled()
        return pair

    def q_polynomial(self, ctx: QContext):
        self.sink.emit(QAdvice(
            audience=Audience.PROVER_PRIVATE,
            i=ctx.i,
            s_next=ctx.s_next,
            field_mod=ctx.field_mod,
            q_true=ctx.q_true,
            z_x_true=int(ctx.z_x_true),
            z_y_true=int(ctx.z_y_true),
            suggestion=ctx.suggestion,
            roots=tuple(int(z) for z in ctx.roots),
        ))
        q_star = _prompt_q_polynomial(
            field=self.F, suggestion=ctx.suggestion, t=ctx.t, i=ctx.i, out=self.out,
        )
        self.sink.emit(AdviceClosed(audience=Audience.PROVER_PRIVATE))
        if q_star is None:
            self.out.print(f"\n{RED}Input cancelled or invalid too many times. Aborting this run.{RESET}")
            return Cancelled()
        return q_star

    def notify_fold_laundered(self, i: int, tau: int) -> None:
        self.sink.emit(FoldLaunderAnnounced(
            audience=Audience.PROVER_PRIVATE, i=i,
        ))