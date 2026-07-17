"""
The GKR text renderer: one function per event type.

Mirrors gkr.protocol.sumcheck_render. Visibility is a pure audience filter, and
every mathematical symbol is composed through gkr.notation rather than written
literally, so supplying a different Notation retargets the whole renderer.

Note `_GKR_EVENT_TYPES`: this renderer returns False for anything not in that
tuple, so that a combined renderer can fall through to the sum-check one. A new
GKR event missing from the tuple is silently dropped.
"""
from __future__ import annotations

from typing import Callable, FrozenSet

from ..notation import DEFAULT_PALETTE, NOTEBOOK_NOTATION, Notation, Palette
from ..utils.display import (
    SupportsPrint,
    _in_notebook,
    display_aligned,
    print_header,
    stringify,
)
from ..utils.display import (
    display as _ipython_display,
)
from .core import Audience, Event
from .gkr_events import (
    AdviceClosed,
    Alpha0Computed,
    BridgeFailed,
    BridgeVacuous,
    BridgingChecked,
    BridgingIntroduced,
    CarriedClaimWasFalse,
    CaughtImpossible,
    ClaimedOutputsDishonest,
    ClaimsPhaseStarted,
    EndpointAdvice,
    EndpointForged,
    EndpointForgeNote,
    EndpointsSent,
    FinalCheckFailed,
    FoldingStarted,
    FoldLaunderAnnounced,
    FoldLaundered,
    FoldLaunderNote,
    GkrFinalCheck,
    GkrGroundTruth,
    GkrInitialized,
    HonestAfterLaunder,
    InitialLieOdds,
    LaunderedInSumCheck,
    LayerLieNote,
    LayerStarted,
    LayerSumCheckFailed,
    LayerSummandShown,
    MleFormed,
    Note,
    OutputsClaimed,
    QAdvice,
    QDegreeChecked,
    QDegreeViolated,
    QEndpointsChecked,
    QEndpointsMismatched,
    QForged,
    QForgeNote,
    QIntroduced,
    QSent,
    Rho0Announced,
    RhoSamplingStarted,
    SumCheckLaunderNote,
    SumCheckRejected,
    TauSampledAndFolded,
    TrueOutputRevealed,
    TrueOutputsShown,
    VacuousBridge,
)
from .gkr_support import _point_str, _truncate_expr
from .sumcheck_render import make_renderer

_GKR_EVENT_TYPES = (
    GkrInitialized, TrueOutputRevealed, TrueOutputsShown, ClaimsPhaseStarted,
    OutputsClaimed,
    ClaimedOutputsDishonest, MleFormed, RhoSamplingStarted, Rho0Announced,
    Alpha0Computed, InitialLieOdds, LayerStarted, LayerSummandShown,
    LayerLieNote, LayerSumCheckFailed, BridgingIntroduced, SumCheckLaunderNote,
    GkrFinalCheck, FoldingStarted, HonestAfterLaunder, CaughtImpossible,
    VacuousBridge, EndpointAdvice, EndpointForgeNote, AdviceClosed,
    EndpointsSent, BridgingChecked, QIntroduced, QAdvice, QForgeNote, QSent,
    QDegreeChecked, QEndpointsChecked, TauSampledAndFolded,
    FoldLaunderAnnounced, FoldLaunderNote, GkrGroundTruth,
)


def make_gkr_renderer(
    *,
    out: SupportsPrint,
    field,
    view: FrozenSet[Audience],
    notation: Notation = NOTEBOOK_NOTATION,
    palette: Palette = DEFAULT_PALETTE,
) -> Callable[[Event], bool]:
    """Renderer for GKR events. Returns True iff the event was a GKR event
    (whether displayed or filtered); False lets a combined renderer fall
    through to the sum-check renderer."""
    F = field
    n = notation
    RED, YELLOW, RESET = palette.LIE, palette.ASIDE, palette.RESET

    def render(e: Event) -> bool:
        if not isinstance(e, _GKR_EVENT_TYPES):
            return False
        if e.audience not in view:
            return True

        # ------------------------------------------------------------------
        if isinstance(e, GkrInitialized):
            print_header("Initialization", out=out)
            out.print(f"\nThe arithmetic circuit C is defined over {F} and has depth {e.depth}.")
            out.print("\nLayer sizes: " + ", ".join(f"{n.layer_size(layer)} = {e.layer_sizes[layer]}" for layer in range(e.depth + 1)) + ".")
            out.print("\nGate-label bit-lengths: " + ", ".join(f"{n.label_bits(layer)} = {e.label_bitlengths[layer]}" for layer in range(e.depth + 1)) + ".")
            out.print(f"\n(Layer 0 holds the output gate(s); layer {e.depth} holds the inputs.)")
            if _in_notebook():
                _ipython_display(e.ac.graphviz_circuit_bitstring)
            else:
                out.print(
                    "\n(Running in a terminal: to render the circuit, call the .view() method of "
                    "your ArithmeticCircuit, e.g. ArithmeticCircuit(...).view().)"
                )
            out.print(
                "\nPublic information: the circuit topology -- and hence the wiring predicates "
                f"add_i, mult_i and their multilinear extensions {n.add('i')}, {n.mult('i')}, which V can "
                f"evaluate anywhere -- together with the inputs:\n\n{e.inputs_str}."
            )
            out.print(
                f"\nIn particular, V can compute {n.W(e.depth)} directly. What V does NOT know (and does "
                f"not want to compute) are the interior gate values and the output(s): verifying a "
                f"claim about the output(s), without re-executing C, is the whole point of the protocol."
            )

        elif isinstance(e, TrueOutputsShown):
            out.print(
                f"\n{YELLOW}We display the true output(s) for the reader. In the protocol, V does "
                f"not know these:{RESET}\n\n{e.truth_str}."
            )

        elif isinstance(e, TrueOutputRevealed):
            out.print(f"\nThe true value of W_0({e.label_str}) is {e.value}.")

        elif isinstance(e, ClaimsPhaseStarted):
            print_header("Claimed output(s)", out=out)

        elif isinstance(e, OutputsClaimed):
            out.print(f"\nP claims that the circuit output(s) are:\n\n{e.claims_str}.")

        elif isinstance(e, ClaimedOutputsDishonest):
            out.print(
                f"\n{RED}In this run, P's claimed output(s) are intentionally false, and P will "
                f"try to get away with it.{RESET}"
            )

        elif isinstance(e, MleFormed):
            out.print(
                f"\nV forms the multilinear extension {n.W(0, star=True)} of the claimed outputs (defining the "
                f"claimed-output function to be 0 on the {2**e.s0 - e.num_outputs} unused "
                f"label(s), which is public information)."
                if 2**e.s0 > e.num_outputs else
                f"\nV forms the multilinear extension {n.W(0, star=True)} of the claimed outputs."
            )
            out.print(
                f"\nIf P's claims are correct, then {n.W(0, star=True)} = {n.W(0)} (multilinear "
                f"extensions are unique); otherwise {n.W(0, star=True)} \u2260 {n.W(0)}."
            )

        elif isinstance(e, RhoSamplingStarted):
            out.print(f"\nV samples {n.rho(0)} uniformly at random from F^{e.s0}.")

        elif isinstance(e, Rho0Announced):
            if e.trivial:
                out.print(
                    f"\nHere {n.label_bits(0)} = 0 (a single output gate), so {n.rho(0)} := () and the point-claim is "
                    "simply the output claim itself."
                )
            else:
                out.print(f"\nHere {n.rho(0)} = {_point_str(e.point)}.")

        elif isinstance(e, Alpha0Computed):
            out.print(
                f"\nV computes {n.alpha(0)} := {n.W(0, star=True)}({n.rho(0)}) = {e.alpha}. The claim to be verified "
                f"is now a single point-claim:\n\n{n.W(0)}({n.rho(0)}) = {n.alpha(0)} = {e.alpha}."
            )

        elif isinstance(e, InitialLieOdds):
            if e.s0 == 0:
                out.print(
                    f"\n{YELLOW}Since the claimed output is false and {n.label_bits(0)} = 0, the point-claim is "
                    f"false with certainty: {n.alpha(0)} \u2260 {n.W(0)}({n.rho(0)}).{RESET}"
                )
            else:
                out.print(
                    f"\n{YELLOW}Since the claimed outputs are false, {n.W(0, star=True)} \u2260 {n.W(0)}, and (by "
                    f"Schwartz-Zippel) the event {n.alpha(0)} = {n.W(0)}({n.rho(0)}) -- which would launder "
                    f"the lie immediately -- has probability at most {n.label_bits(0)}/#F = {e.s0}/{e.field_mod} = "
                    f"{e.s0/e.field_mod:.10f}.{RESET}"
                )
                if e.laundered_at_start:
                    out.print(
                        f"\n{YELLOW}Remarkably, that is exactly what happened: {n.rho(0)} landed where "
                        f"{n.W(0, star=True)} and {n.W(0)} agree. The lie has been laundered before the protocol "
                        f"even started, and P can play honestly throughout.{RESET}"
                    )
        else:
            return _render_layer_events(e, out=out, F=F, view=view,
                                        notation=n, palette=palette)
        return True

    return render


def _format_note(note: Note, n) -> str:
    """Ground-truth ledger entries, worded and notated here rather than in the
    engine: the engine records *what happened*, the renderer says it."""
    i = note.i
    if isinstance(note, CarriedClaimWasFalse):
        return (f"Layer {i}: the carried claim was false ({n.alpha(i)} = {note.alpha}, "
                f"true value {note.true_value}); P forged round polynomials in the sum-check.")
    if isinstance(note, LaunderedInSumCheck):
        return (f"Layer {i}: a sum-check challenge hit a root of a forged polynomial; "
                f"the lie was laundered ({n.gamma()} = {n.g()}({n.r('x')}, {n.r('y')})).")
    if isinstance(note, SumCheckRejected):
        return f"Layer {i}: V rejected during the sum-check."
    if isinstance(note, FinalCheckFailed):
        return f"Layer {i}: the final check against the public inputs failed."
    if isinstance(note, BridgeVacuous):
        return (f"Layer {i} folding: {n.A()} = {n.M()} = 0 and {n.gamma()} = 0, so the bridging "
                f"equation was vacuous; P claimed the true values and the lie was laundered.")
    if isinstance(note, EndpointForged):
        if note.kept == "x":
            return f"Layer {i} folding: P kept {n.z_x(star=True)} true and forged the other endpoint."
        if note.kept == "y":
            return f"Layer {i} folding: P kept {n.z_y(star=True)} true and forged the other endpoint."
        return f"Layer {i} folding: P forged both endpoints."
    if isinstance(note, BridgeFailed):
        return f"Layer {i} folding: the bridging equation failed."
    if isinstance(note, QForged):
        roots = list(note.roots) if note.roots else "none"
        return (f"Layer {i} folding: P forged {n.q(i + 1, star=True)}; roots of "
                f"{n.q(i + 1, star=True)} - {n.q(i + 1)}: {roots}.")
    if isinstance(note, QDegreeViolated):
        return f"Layer {i} folding: {n.q(i + 1, star=True)} violated the degree bound."
    if isinstance(note, QEndpointsMismatched):
        return (f"Layer {i} folding: {n.q(i + 1, star=True)}'s endpoints did not match "
                f"({n.z_x(star=True)}, {n.z_y(star=True)}).")
    if isinstance(note, FoldLaundered):
        return (f"Layer {i} folding: {n.tau(i + 1)} = {note.tau} hit a root of "
                f"{n.q(i + 1, star=True)} - {n.q(i + 1)}; the carried claim became TRUE.")
    return str(note)   # unreachable for known notes


def _render_layer_events(e: Event, *, out, F, view, notation, palette) -> bool:
    n = notation
    RED, GREEN, YELLOW, RESET = palette.LIE, palette.TRUTH, palette.ASIDE, palette.RESET

    if isinstance(e, LayerStarted):
        print_header(f"GKR layer {e.i} \u2192 {e.i + 1}: sum-check", level=1, out=out)
        xy_ = stringify(list(e.x_names) + list(e.y_names))
        x_ = stringify(list(e.x_names))
        y_ = stringify(list(e.y_names))
        out.print(
            f"\nAt the start of this layer, V holds {n.rho(e.i)} = {_point_str(e.rho_i)} and the "
            f"carried claim {n.alpha(e.i)} = {e.alpha_i} (the claim being that "
            f"{n.W(e.i)}({n.rho(e.i)}) = {n.alpha(e.i)})."
        )
        out.print(
            f"\nBy Thaler's identity,\n\n{n.W(e.i)}({n.rho(e.i)}) = sum {n.g()}({xy_}) over "
            f"({xy_}) in {{0,1}}^{e.m},\n\nwhere\n\ng({xy_}) := "
            f"{n.add(e.i)}({n.rho(e.i)}, {x_}, {y_})\u00b7[{n.W(e.i + 1)}({x_}) + {n.W(e.i + 1)}({y_})] "
            f"+ {n.mult(e.i)}({n.rho(e.i)}, {x_}, {y_})\u00b7[{n.W(e.i + 1)}({x_})\u00b7{n.W(e.i + 1)}({y_})]."
        )
        out.print(
            f"\nV can evaluate {n.add(e.i)} and {n.mult(e.i)} anywhere (the wiring is public), "
            f"but NOT {n.W(e.i + 1)}, so V cannot evaluate g pointwise. So we run the sum-check "
            f"protocol on g, with claimed sum H* := {n.alpha(e.i)} = {e.alpha_i}, deferring "
            f"the evaluation of g."
        )
        out.print(
            f"\nFor soundness, V relies on degree bounds per variable (this is public "
            f"information): {[2] * e.m}. (Each variable has degree \u2264 1 in the wiring "
            f"MLE and \u2264 1 in {n.W(e.i + 1)}, hence degree \u2264 2 in g.)"
        )

    elif isinstance(e, LayerSummandShown):
        xy_ = stringify(list(e.x_names) + list(e.y_names))
        out.print(
            f"\n{YELLOW}We display g for the reader. In the protocol, V cannot compute g "
            f"(it involves {n.W(e.i + 1)}):{RESET}\n\ng({xy_}) = {_truncate_expr(e.g_poly)}."
        )

    elif isinstance(e, LayerLieNote):
        out.print(
            f"\n{RED}The carried claim is false: in fact {n.W(e.i)}({n.rho(e.i)}) = "
            f"{e.w_true} \u2260 {e.alpha_i} = {n.alpha(e.i)}. To survive this "
            f"sum-check, P is forced to forge round polynomials.{RESET}"
        )

    elif isinstance(e, LayerSumCheckFailed):
        out.print(f"\n{RED}Protocol failed during the layer {e.i} sum-check.{RESET}")

    elif isinstance(e, BridgingIntroduced):
        out.print(
            f"\nUnlike in the standalone sum-check protocol, V does not now evaluate "
            f"g({n.r('x')}, {n.r('y')}): g involves {n.W(e.i + 1)}, which V does not know. The transcript's "
            f"terminal claim is\n\n{n.gamma()} := {n.g(e.m - 1, star=True)}({n.r(e.m - 1)}) = {e.gamma},\n\nthe claim "
            f"being that {n.gamma()} = g({n.r('x')}, {n.r('y')}), where {n.r('x')} = {_point_str(e.r_x)} and {n.r('y')} = {_point_str(e.r_y)}."
        )
        out.print(
            "\nV computes the (public) wiring values at this point:\n"
        )
        display_aligned(
            f"A = {n.add(e.i)}({n.rho(e.i)}, {n.r('x')}, {n.r('y')}) = {e.A}",
            f"M = {n.mult(e.i)}({n.rho(e.i)}, {n.r('x')}, {n.r('y')}) = {e.M}",
            out=out,
        )
        out.print(
            f"\nUnpacking the definition of g, the claim {n.gamma()} = g({n.r('x')}, {n.r('y')}) says exactly that\n\n"
            f"{n.gamma()} = A\u00b7[{n.W(e.i + 1)}({n.r('x')}) + {n.W(e.i + 1)}({n.r('y')})] "
            f"+ {n.M()}\u00b7[{n.W(e.i + 1)}({n.r('x')})\u00b7{n.W(e.i + 1)}({n.r('y')})]   (the 'bridging equation')."
        )

    elif isinstance(e, SumCheckLaunderNote):
        out.print(
            f"\n{YELLOW}During this sum-check, a verifier challenge hit a root of a forged "
            f"polynomial: the terminal claim {n.gamma()} now equals the true value g({n.r('x')}, {n.r('y')}). "
            f"The lie has been laundered, and P can proceed honestly.{RESET}"
        )

    elif isinstance(e, GkrFinalCheck):
        print_header("Final check", level=2, out=out)
        out.print(
            f"\nLayer {e.depth} is the input layer. The inputs are public, so V can compute "
            f"{n.W(e.depth)} -- and hence both endpoint values -- directly, with no help from P:\n"
        )
        display_aligned(
            f"{n.z_x()} = {n.W(e.depth)}({n.r('x')}) = {e.z_x}",
            f"{n.z_y()} = {n.W(e.depth)}({n.r('y')}) = {e.z_y}",
            out=out,
        )
        out.print(
            f"\n{YELLOW}Nothing is left for P to forge: both endpoints are V's own, and there is "
            f"no fold after the input layer. This last check spends no randomness -- a lie that "
            f"survived to here is caught with certainty.{RESET}"
        )
        out.print(f"\nV checks the bridging equation {n.gamma()} = A\u00b7({n.z_x()} + {n.z_y()}) + M\u00b7z_x\u00b7z_y:\n")
        display_aligned(
            f"{n.gamma()} = {e.gamma}",
            f"A\u00b7({n.z_x()} + {n.z_y()}) + M\u00b7z_x\u00b7z_y = {e.rhs}",
            out=out,
        )
        if e.accepted:
            out.print(
                f"\nP passes the final verification, and V {GREEN}ACCEPTS{RESET} P's claimed output(s)."
            )
            if e.initial_claim_false:
                out.print(
                    f"\n{RED}P HAS DECEIVED V: THE CLAIMED OUTPUT(S) ARE IN FACT FALSE.{RESET}"
                )
                out.print(
                    f"\n{YELLOW}P GOT LUCKY:{RESET} at some point a random verifier challenge "
                    f"happened to land where a forged object agreed with the true one. The "
                    f"Ground truth section below tallies exactly how likely that was."
                )
        else:
            out.print(
                f"\nP fails the final verification, and V {RED}REJECTS{RESET} P's claimed output(s)."
            )
            out.print(
                f"\n{YELLOW}Interpretation: P can often keep each layer locally consistent, "
                f"but the final evaluation against the public inputs ties the entire transcript "
                f"to the true circuit and typically catches a lie.\n{RESET}"
            )

    elif isinstance(e, FoldingStarted):
        print_header(f"Layer {e.i} folding", level=1, out=out)
        out.print(
            f"\nV cannot check the bridging equation alone: it involves {n.W(e.i + 1)}({n.r('x')}) and "
            f"{n.W(e.i + 1)}({n.r('y')}), which V cannot compute. So P supplies claimed values\n\n"
            f"{n.z_x(star=True)} (the claim: {n.z_x(star=True)} = {n.W(e.i + 1)}({n.r('x')}))   and   {n.z_y(star=True)} (the claim: {n.z_y(star=True)} = {n.W(e.i + 1)}({n.r('y')}))."
        )

    elif isinstance(e, HonestAfterLaunder):
        out.print(
            f"\n{YELLOW}Since the lie has been laundered, the TRUE values now satisfy the "
            f"bridging equation: P sends them and plays honestly from here.{RESET}"
        )

    elif isinstance(e, CaughtImpossible):
        out.print(
            f"\n{RED}No pair ({n.z_x(star=True)}, {n.z_y(star=True)}) can satisfy the bridging equation: A = M = 0 "
            f"at this point while {n.gamma()} \u2260 0. P is caught, no matter what P sends.{RESET}"
        )

    elif isinstance(e, VacuousBridge):
        out.print(
            f"\n{YELLOW}Here A = M = 0 and {n.gamma()} = 0, so the bridging equation is "
            f"vacuous: P can claim the TRUE values, and the lie is laundered.{RESET}"
        )

    elif isinstance(e, EndpointAdvice):
        out.print(f"\n{RED}=== START INVISIBLE TO VERIFIER ==={RESET}")
        out.print(
            f"\nIn fact,\n\n{GREEN}{n.W(e.i + 1)}({n.r('x')}) = {e.z_x_true}   and   "
            f"{n.W(e.i + 1)}({n.r('y')}) = {e.z_y_true}{RESET},"
        )
        out.print(
            f"\nbut these true values do NOT satisfy the bridging equation (your {n.gamma()} is "
            "a surviving lie), so you must lie about at least one endpoint."
        )
        out.print(
            "\nWhatever pair you send must satisfy\n\n"
            f"{e.gamma} = {e.A}\u00b7({n.z_x(star=True)} + {n.z_y(star=True)}) + {e.M}\u00b7{n.z_x(star=True)}\u00b7{n.z_y(star=True)}."
        )
        if e.kept == "x":
            out.print(
                f"\nFor example, keep {n.z_x(star=True)} = {n.W(e.i + 1)}({n.r('x')}) = {e.zx_suggestion} (true) and "
                f"take {RED}{n.z_y(star=True)} = {e.zy_suggestion}{RESET}. Lying about only one endpoint "
                f"will plant t = 0 as a root of {n.q(e.i + 1, star=True)} - {n.q(e.i + 1)} at the next step "
                f"for free."
            )
        elif e.kept == "y":
            out.print(
                f"\nFor example, keep {n.z_y(star=True)} = {n.W(e.i + 1)}({n.r('y')}) = {e.zy_suggestion} (true) and "
                f"take {RED}{n.z_x(star=True)} = {e.zx_suggestion}{RESET}. Lying about only one endpoint "
                f"will plant t = 1 as a root of {n.q(e.i + 1, star=True)} - {n.q(e.i + 1)} at the next step "
                f"for free."
            )
        else:
            out.print(
                f"\nFor example, take {RED}({n.z_x(star=True)}, {n.z_y(star=True)}) = ({e.zx_suggestion}, {e.zy_suggestion}){RESET}."
            )

    elif isinstance(e, EndpointForgeNote):
        if e.kept == "x":
            forged = f"keeps {n.z_x(star=True)} true and forges {n.z_y(star=True)}"
        elif e.kept == "y":
            forged = f"keeps {n.z_y(star=True)} true and forges {n.z_x(star=True)}"
        else:
            forged = "forges both endpoints"
        out.print(
            f"\n{RED}The true endpoint values fail the bridging equation ({n.gamma()} is a "
            f"surviving lie), so P {forged}, choosing a pair consistent with {n.gamma()}.{RESET}"
        )

    elif isinstance(e, AdviceClosed):
        out.print(f"\n{RED}=== END INVISIBLE TO VERIFIER ==={RESET}")

    elif isinstance(e, EndpointsSent):
        out.print(f"\nP sends {n.z_x(star=True)} = {e.zx_star} and {n.z_y(star=True)} = {e.zy_star}.")

    elif isinstance(e, BridgingChecked):
        out.print(f"\nV checks the bridging equation {n.gamma()} = {n.A()}\u00b7({n.z_x(star=True)} + {n.z_y(star=True)}) + {n.M()}\u00b7{n.z_x(star=True)}\u00b7{n.z_y(star=True)}:\n")
        display_aligned(
            f"{n.gamma()} = {e.gamma}",
            f"{n.A()}\u00b7({n.z_x(star=True)} + {n.z_y(star=True)}) + {n.M()}\u00b7{n.z_x(star=True)}\u00b7{n.z_y(star=True)} = {e.rhs}",
            out=out,
        )
        if not e.passed:
            out.print(f"\nV {RED}REJECTS{RESET} (bridging equation failed). The protocol terminates.")
        else:
            out.print("\nV sees that P's claims so far are consistent.")
            out.print(
                f"\n{YELLOW}Note: this check spends none of V's randomness. A and M are public "
                f"and already fixed, so a P whose {n.gamma()} is false can always solve the bridging "
                f"equation for forged endpoints (unless A = M = 0, when a false {n.gamma()} is caught "
                f"outright). Consistency here is not evidence of honesty; the soundness budget lives "
                f"entirely in the random challenges ({n.rho(0)}, the round challenges, and "
                f"each fold challenge).{RESET}"
            )

    elif isinstance(e, QIntroduced):
        out.print(
            f"\nWe now hold TWO claims about {n.W(e.i + 1)} (at {n.r('x')} and at {n.r('y')}). To avoid the "
            "number of claims doubling at every layer, V folds them into ONE, as follows."
        )
        out.print(
            f"\nLet {n.ell()}(t) := (1 - t)\u00b7r_x + t\u00b7r_y (the line through {n.r('x')} = {n.ell()}(0) and "
            f"{n.r('y')} = {n.ell()}(1)), and let {n.q(e.i + 1)}(t) := {n.W(e.i + 1)}({n.ell()}(t)), a univariate "
            f"polynomial of degree \u2264 {n.label_bits(e.i + 1)} = {e.s_next}."
        )
        out.print(
            f"\nP supplies a polynomial {n.q(e.i + 1, star=True)} (the claim: {n.q(e.i + 1, star=True)} = {n.q(e.i + 1)}). "
            f"V checks that\n\n(a) deg({n.q(e.i + 1, star=True)}) \u2264 {e.s_next}, and "
            f"(b) {n.q(e.i + 1, star=True)}(0) = {n.z_x(star=True)} and {n.q(e.i + 1, star=True)}(1) = {n.z_y(star=True)}."
        )

    elif isinstance(e, QAdvice):
        out.print(f"\n{RED}=== START INVISIBLE TO VERIFIER ==={RESET}")
        out.print(f"\nIn fact,\n\n{GREEN}{n.q(e.i + 1)}(t) = {e.q_true.as_expr()}{RESET},")
        out.print(
            f"\nbut {n.q(e.i + 1)}(0) = {e.z_x_true} and {n.q(e.i + 1)}(1) = {e.z_y_true}: the "
            f"true restriction does not match your claimed endpoints, so you must forge "
            f"{n.q(e.i + 1, star=True)} to pass check (b)."
        )
        out.print(
            f"\nAfter checks (a) and (b), V will sample {n.tau(e.i + 1)} uniformly at random "
            f"from {F} and carry the single claim\n\n{n.alpha(e.i + 1)} := {n.q(e.i + 1, star=True)}({n.tau(e.i + 1)}) "
            f"= {n.W(e.i + 1)}({n.ell()}({n.tau(e.i + 1)}))  (a claim about the point "
            f"{n.rho(e.i + 1)} := {n.ell()}({n.tau(e.i + 1)}))."
        )
        out.print(
            f"\nIf {n.tau(e.i + 1)} is a root of {n.q(e.i + 1, star=True)} - {n.q(e.i + 1)}, the carried claim will "
            f"be TRUE, and you can play honestly for the rest of the protocol."
        )
        out.print(
            f"\nAs you don't know what {n.tau(e.i + 1)} will be, the best you can do is choose "
            f"{n.q(e.i + 1, star=True)} satisfying (a) and (b) such that {n.q(e.i + 1, star=True)} - {n.q(e.i + 1)} has as many "
            f"roots as possible in {F} (there can be at most deg({n.q(e.i + 1, star=True)} - {n.q(e.i + 1)}) "
            f"\u2264 {e.s_next})."
        )
        if e.roots:
            print_roots = ", ".join(f"{YELLOW}{z}{RESET}" for z in e.roots)
            out.print(
                f"\nFor example, if\n\n{RED}{n.q(e.i + 1, star=True)}(t) = {e.suggestion.as_expr()}{RESET},"
                f"\n\nthen (a) and (b) hold, and the roots (in {F}) of "
                f"{n.q(e.i + 1, star=True)} - {n.q(e.i + 1)} are: {print_roots}."
            )
            out.print(
                f"\nThe probability of V sampling one of these roots as {n.tau(e.i + 1)} is "
                f"{len(e.roots)}/{e.field_mod} = {len(e.roots)/e.field_mod:.10f}."
            )
            out.print(
                f"\nIn general, by Schwartz-Zippel, this probability cannot exceed "
                f"{n.label_bits(e.i + 1)}/#F = {e.s_next}/{e.field_mod} = {e.s_next/e.field_mod:.10f}."
            )
        else:
            out.print(
                f"\nFor example, if\n\n{RED}{n.q(e.i + 1, star=True)}(t) = {e.suggestion.as_expr()}{RESET},"
                f"\n\nthen (a) and (b) hold, but {n.q(e.i + 1, star=True)} - {n.q(e.i + 1)} has no roots in {F}."
            )

    elif isinstance(e, QForgeNote):
        print_roots = ", ".join(f"{YELLOW}{z}{RESET}" for z in e.roots) if e.roots else "(none)"
        out.print(
            f"\n{RED}P forges {n.q(e.i + 1, star=True)} to match the claimed endpoints{RESET}, planting "
            f"as many agreement points with the true {n.q(e.i + 1)} as the degree bound allows; "
            f"the roots of {n.q(e.i + 1, star=True)} - {n.q(e.i + 1)} are: {print_roots}."
        )
        if e.field_mod:
            if e.roots:
                out.print(
                    f"\nThe probability of V sampling one of these roots as {n.tau(e.i + 1)} is "
                    f"{len(e.roots)}/{e.field_mod} = {len(e.roots)/e.field_mod:.10f}."
                )
            out.print(
                f"\nIn general, by Schwartz-Zippel, this probability cannot exceed "
                f"{n.label_bits(e.i + 1)}/#F = {e.s_next}/{e.field_mod} = {e.s_next/e.field_mod:.10f}."
            )

    elif isinstance(e, QSent):
        out.print(f"\nP claims that {n.q(e.i + 1)}({n.t()}) = {n.q(e.i + 1, star=True)}({n.t()}), where\n\n{n.q(e.i + 1, star=True)}({n.t()}) = {e.q_star.as_expr()}.")

    elif isinstance(e, QDegreeChecked):
        if not e.passed:
            out.print(f"\nV finds that deg({n.q(e.i + 1, star=True)}) = {e.degree} > {n.label_bits(e.i + 1)} = {e.s_next}.")
            out.print(f"\nV {RED}REJECTS{RESET} (degree bound violated). The protocol terminates.")
        else:
            out.print(f"\nV checks the degree bound: deg({n.q(e.i + 1, star=True)}) = {e.degree} \u2264 {n.label_bits(e.i + 1)} = {e.s_next}.")

    elif isinstance(e, QEndpointsChecked):
        out.print("\nV checks the endpoints:\n")
        display_aligned(
            f"{n.q(e.i + 1, star=True)}(0) = {e.q0}  (should be {n.z_x(star=True)} = {e.zx_star})",
            f"{n.q(e.i + 1, star=True)}(1) = {e.q1}  (should be {n.z_y(star=True)} = {e.zy_star})",
            out=out,
        )
        if not e.passed:
            out.print(f"\nV {RED}REJECTS{RESET} (endpoint check failed). The protocol terminates.")
        else:
            out.print("\nV sees that P's claims so far are consistent.")

    elif isinstance(e, TauSampledAndFolded):
        out.print(f"\nV samples an element uniformly at random from {F}; here {n.tau(e.i + 1)} = {e.tau}.")
        out.print(
            f"\nV sets {n.rho(e.i + 1)} := {n.ell()}({n.tau(e.i + 1)}) = {_point_str(e.rho_next)} and carries the "
            f"single claim\n\n{n.alpha(e.i + 1)} := {n.q(e.i + 1, star=True)}({n.tau(e.i + 1)}) = {e.alpha_next}\n\n(the "
            f"claim being that {n.alpha(e.i + 1)} = {n.W(e.i + 1)}({n.rho(e.i + 1)})). The protocol proceeds "
            f"to the next layer."
        )

    elif isinstance(e, FoldLaunderAnnounced):
        out.print(f"\n{RED}=== START INVISIBLE TO VERIFIER ==={RESET}")
        out.print(
            f"\n{RED}YOU HAVE SUCCESSFULLY DECEIVED THE VERIFIER: "
            f"{n.q(e.i + 1, star=True)}({n.tau(e.i + 1)}) = {n.q(e.i + 1)}({n.tau(e.i + 1)}), i.e. the carried claim "
            f"{n.alpha(e.i + 1)} = {n.W(e.i + 1)}({n.rho(e.i + 1)}) is TRUE.{RESET}"
        )
        out.print(f"\n{RED}From now on, honest play suffices.{RESET}")
        out.print(f"\n{RED}=== END INVISIBLE TO VERIFIER ==={RESET}")

    elif isinstance(e, FoldLaunderNote):
        out.print(
            f"\n{YELLOW}{n.tau(e.i + 1)} = {e.tau} hit a root of {n.q(e.i + 1, star=True)} - {n.q(e.i + 1)}: "
            f"the carried claim is now TRUE. The lie has been laundered, and P can proceed "
            f"honestly.{RESET}"
        )

    elif isinstance(e, GkrGroundTruth):
        print_header("Ground truth", level=1, out=out)
        out.print(f"\nTrue circuit output(s):\n\n{e.truth_str}.")
        out.print(f"\nProver claimed:\n\n{e.claims_str}.")
        if e.notes:
            out.print("")
            for note in e.notes:
                out.print(f"{YELLOW}{_format_note(note, n)}{RESET}")
        if e.s_list and e.field_mod:
            s_vals = list(e.s_list)
            p_mod = e.field_mod
            s0, rest, mids = s_vals[0], s_vals[1:], s_vals[1:-1]
            total = s0 + 4 * sum(rest) + sum(mids)
            rounds_str = " + ".join(str(x) for x in rest)
            folds_str = " + ".join(str(x) for x in mids) if mids else "0"
            out.print(
                f"\nSoundness accounting. P is exposed to V's randomness in exactly three places: "
                f"the draw of {n.rho(0)}, each sum-check round challenge, and each fold challenge. "
                f"Union-bounding those exposures (see the notes), a dishonest P's chance of "
                f"acceptance over this circuit and field is at most\n"
            )
            if total < p_mod:
                out.print(
                    f"({s0} + 4\u00b7({rounds_str}) + ({folds_str}))/{p_mod} "
                    f"= {total}/{p_mod} = {total/p_mod:.10f}"
                )
            else:
                out.print(
                    f"({s0} + 4\u00b7({rounds_str}) + ({folds_str}))/{p_mod} "
                    f"= {total}/{p_mod} -- which exceeds 1: over a field this small the "
                    f"bound is vacuous, and deceiving V is not merely possible but likely. "
                    f"This is exactly why GKR wants a large field."
                )
            out.print(
                f"\n(the three terms in that order: the draw of {n.rho(0)}, two chances per round "
                f"across every sum-check, and one fold per intermediate layer)."
            )
            out.print(
                "\nThe bridging equations and the final check spend no randomness at all: a "
                "consistent liar passes them for free, and the whole budget above is what stands "
                "between V and a false claim."
            )
        if e.accepted:
            out.print(f"\nOutcome: V {GREEN}ACCEPTED{RESET}.")
            if not e.initial_claim_false:
                out.print(f"\n{GREEN}This was a TRUE POSITIVE{RESET}: the claimed output(s) were correct.")
            else:
                out.print(f"\n{RED}This was a FALSE POSITIVE{RESET}: V accepted false claimed output(s) (P got lucky).")
        else:
            out.print(f"\nOutcome: V {RED}REJECTED{RESET}.")
            if not e.initial_claim_false:
                out.print(f"{YELLOW}\nThis was a FALSE NEGATIVE{RESET}: rejection happened despite correct claimed output(s) (should be rare unless the transcript was made inconsistent).")
            else:
                out.print(f"{GREEN}\nThis was a TRUE NEGATIVE{RESET}: V rejected false claimed output(s).")
        out.print("")

    return True


def make_combined_renderer(
    *,
    out: SupportsPrint,
    field,
    view: FrozenSet[Audience],
    notation: Notation = NOTEBOOK_NOTATION,
    palette: Palette = DEFAULT_PALETTE,
) -> Callable[[Event], None]:
    """GKR events first; everything else falls through to the sum-check
    renderer (used by each layer's inner sum-check)."""
    gkr_render = make_gkr_renderer(out=out, field=field, view=view,
                                   notation=notation, palette=palette)
    base_render = make_renderer(out=out, field=field, view=view,
                                notation=notation, palette=palette)

    def render(event: Event) -> None:
        if gkr_render(event):
            return None
        base_render(event)

    return render