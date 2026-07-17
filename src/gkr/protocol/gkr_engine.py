"""
The GKR engine: the layer-by-layer protocol loop.

The engine is deliberately OMNISCIENT: it holds the circuit, computes true gate
values, wiring values and cheat suggestions, and keeps the ground-truth ledger.
That is a concentration of knowledge, not a leak of it -- what a given role may
*see* is the audience tag on each event, and role-dependent narration (advice
blocks versus narrator asides) is emitted by the party that owns it, never by
the control flow. Splitting the omniscient narrator from a V-knowledge-only
core, as the sum-check engine already does, is future work.

Each layer's inner sum-check is a plain `run_sum_check` call with a
`DeferredToCaller` oracle: the terminal claim gamma comes back untested, and the
bridging equation here is what judges its truth. That seam is why the engine
needs no "should I show the final check?" or "should I return the value?"
flags -- the caller's oracle answers both.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from sympy import Poly, symbols

from ..ac import ArithmeticCircuit, replace_symbols_in_polynomial
from ..utils.display import TerminalOutput
from ..utils.display import out as default_out
from .core import Audience, Sink
from .gkr_cheats import dishonest_folding_values, dishonest_q_polynomial
from .gkr_events import (
    Alpha0Computed,
    BridgeFailed,
    BridgeVacuous,
    BridgingChecked,
    BridgingIntroduced,
    CarriedClaimWasFalse,
    CaughtImpossible,
    ClaimedOutputsDishonest,
    ClaimsPhaseStarted,
    EndpointForged,
    EndpointsSent,
    FinalCheckFailed,
    FoldingStarted,
    FoldLaundered,
    GkrFinalCheck,
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
    QDegreeChecked,
    QDegreeViolated,
    QEndpointsChecked,
    QEndpointsMismatched,
    QForged,
    QIntroduced,
    QSent,
    Rho0Announced,
    RhoSamplingStarted,
    SumCheckLaunderNote,
    SumCheckRejected,
    TauSampledAndFolded,
    VacuousBridge,
)
from .gkr_parties import EndpointContext, QContext
from .gkr_support import (
    _claimed_output_mle,
    _eval_tilde,
    _label_bitlength,
    normalize_to_x_vars,
)
from .sumcheck_engine import Aborted, DeferredToCaller, Rejected, TerminalValue, run_sum_check
from .sumcheck_parties import Cancelled


@dataclass
class GkrRunResult:
    status: str                                  # "accept" | "reject" | "abort" | "abort_claims"
    claims: Optional[Dict[Tuple[int, ...], int]] = None
    initial_claim_false: bool = False
    notes: Tuple[Note, ...] = ()


def run_gkr(
    ac: ArithmeticCircuit,
    *,
    prover,
    verifier,
    sink: Sink,
    out: TerminalOutput = default_out,
) -> GkrRunResult:
    F = ac.field
    p = int(F.mod)
    assert ac.depth is not None  # validate_for_gkr guarantees a fully built circuit
    d: int = ac.depth
    s0 = _label_bitlength(ac, 0)

    true_outputs = {label: int(v) for label, v in ac.W_dict[0].items()}
    output_labels = sorted(true_outputs.keys())

    notes: List[Note] = []

    # ---- the prover's claimed output(s) --------------------------------------
    sink.emit(ClaimsPhaseStarted(audience=Audience.PUBLIC))

    claims = prover.claim_outputs(None)
    if isinstance(claims, Cancelled):
        return GkrRunResult(status="abort_claims")

    initial_claim_false = (claims != true_outputs)
    from ..utils.display import stringify
    claims_str = ", ".join(f"W*_0({stringify(lbl)}) = {claims[lbl]}" for lbl in output_labels)
    sink.emit(OutputsClaimed(audience=Audience.PUBLIC, claims_str=claims_str))
    if initial_claim_false:
        sink.emit(ClaimedOutputsDishonest(audience=Audience.NARRATOR))

    # ---- reduce to a single point-claim about W-tilde_0 ----------------------
    sink.emit(MleFormed(audience=Audience.PUBLIC, s0=s0, num_outputs=len(output_labels)))

    W0_star_tilde = _claimed_output_mle(ac, claims)

    if s0 == 0:
        rho_0: Tuple = ()
        sink.emit(Rho0Announced(audience=Audience.PUBLIC, point=(), trivial=True))
    else:
        sink.emit(RhoSamplingStarted(audience=Audience.PUBLIC, s0=s0))
        coords = []
        for j in range(s0):
            c = verifier.gkr_rho_coordinate(j)
            if isinstance(c, Cancelled):
                return GkrRunResult(status="abort", claims=claims,
                                    initial_claim_false=initial_claim_false, notes=tuple(notes))
            coords.append(F.convert(int(c)))
        rho_0 = tuple(coords)
        sink.emit(Rho0Announced(audience=Audience.PUBLIC,
                                point=tuple(int(c) for c in rho_0), trivial=False))

    alpha = _eval_tilde(W0_star_tilde, rho_0, F) if s0 > 0 else F.convert(claims[()])
    sink.emit(Alpha0Computed(audience=Audience.PUBLIC, alpha=int(alpha)))

    w_0_true = _eval_tilde(ac.tilde_W[0], rho_0, F)
    if initial_claim_false:
        sink.emit(InitialLieOdds(
            audience=Audience.NARRATOR,
            s0=s0, field_mod=p,
            laundered_at_start=bool(alpha == w_0_true),
        ))

    # ---- the layer-by-layer protocol -----------------------------------------
    rho = rho_0
    for i in range(d):
        status, rho, alpha = _layer_transition(
            ac, i=i, rho_i=rho, alpha_i=alpha,
            final_layer=(i == d - 1),
            initial_claim_false=initial_claim_false,
            prover=prover, verifier=verifier, sink=sink, out=out, notes=notes,
        )
        if status == "abort":
            return GkrRunResult(status="abort", claims=claims,
                                initial_claim_false=initial_claim_false, notes=tuple(notes))
        if status in ("accept", "reject"):
            return GkrRunResult(status=status, claims=claims,
                                initial_claim_false=initial_claim_false, notes=tuple(notes))
        # status == "continue"

    # Should not happen (the loop always ends in accept/reject/abort), but be safe.
    return GkrRunResult(status="reject", claims=claims,
                        initial_claim_false=initial_claim_false, notes=tuple(notes))


def _layer_transition(
    ac: ArithmeticCircuit,
    *,
    i: int,
    rho_i: Tuple,
    alpha_i,
    final_layer: bool,
    initial_claim_false: bool,
    prover,
    verifier,
    sink: Sink,
    out: TerminalOutput,
    notes: List[Note],
) -> Tuple[str, Tuple, object]:
    """One layer: the sum-check over Thaler's identity, then folding (or the
    final check against the public inputs). Returns (status, rho_next, alpha_next)."""
    F = ac.field
    p = int(F.mod)
    assert ac.depth is not None  # run_gkr validated the circuit before calling
    d: int = ac.depth
    s_i = _label_bitlength(ac, i)
    s_next = _label_bitlength(ac, i + 1)
    m = 2 * s_next

    # ---- build the Thaler-identity summand g(x, y) ---------
    add_i = replace_symbols_in_polynomial(ac.tilde_add[i], v=s_i, w=s_next)
    mult_i = replace_symbols_in_polynomial(ac.tilde_mult[i], v=s_i, w=s_next)

    z_syms = list(symbols(f"z_:{s_i}"))
    x_syms = list(symbols(f"x_:{s_next}"))
    y_syms = list(symbols(f"y_:{s_next}"))

    z_subs = {z_syms[j]: int(rho_i[j]) for j in range(s_i)}
    add_xy = Poly(add_i.as_expr().subs(z_subs), *(x_syms + y_syms), domain=F)
    mult_xy = Poly(mult_i.as_expr().subs(z_subs), *(x_syms + y_syms), domain=F)

    W_next = normalize_to_x_vars(ac.tilde_W[i + 1], s_next)
    Wx_expr = W_next.as_expr().subs({W_next.gens[j]: x_syms[j] for j in range(s_next)})
    Wy_expr = W_next.as_expr().subs({W_next.gens[j]: y_syms[j] for j in range(s_next)})

    g_expr = add_xy.as_expr() * (Wx_expr + Wy_expr) + mult_xy.as_expr() * (Wx_expr * Wy_expr)
    g_poly = Poly(g_expr, *(x_syms + y_syms), domain=F)

    # ---- truth and the carried claim ------------------------------------------
    alpha_i = F.convert(int(alpha_i))
    w_i_true = _eval_tilde(ac.tilde_W[i], rho_i, F)
    lie_active = bool(alpha_i != w_i_true)

    # ---- preamble ---------------------------------------------------------------
    sink.emit(LayerStarted(
        audience=Audience.PUBLIC,
        i=i,
        rho_i=tuple(int(c) for c in rho_i),
        alpha_i=int(alpha_i),
        m=m,
        s_next=s_next,
        x_names=tuple(str(s) for s in x_syms),
        y_names=tuple(str(s) for s in y_syms),
    ))
    sink.emit(LayerSummandShown(
        audience=Audience.NARRATOR,
        i=i, g_poly=g_poly,
        x_names=tuple(str(s) for s in x_syms),
        y_names=tuple(str(s) for s in y_syms),
    ))
    if lie_active:
        sink.emit(LayerLieNote(
            audience=Audience.NARRATOR,
            i=i, w_true=int(w_i_true), alpha_i=int(alpha_i),
        ))

    # ---- the sum-check itself -----------------------------------------------------
    degree_bounds = [2] * m
    inner = prover.inner_prover(g_poly, alpha_i, lying=lie_active)
    scr = run_sum_check(
        field=F,
        gens=g_poly.gens,
        degree_bounds=degree_bounds,
        prover=inner,
        verifier=verifier,
        oracle=DeferredToCaller(),
        sink=sink,
        out=out,
    )
    if isinstance(scr.verdict, Aborted):
        return "abort", (), 0
    if isinstance(scr.verdict, Rejected):
        sink.emit(LayerSumCheckFailed(audience=Audience.PUBLIC, i=i))
        notes.append(SumCheckRejected(i=i))
        return "reject", (), 0
    assert isinstance(scr.verdict, TerminalValue)
    gamma_F = F.convert(int(scr.verdict.value))

    r = list(scr.challenges)
    r_x = tuple(r[:s_next])
    r_y = tuple(r[s_next:])

    # Public wiring values at (rho_i, r_x, r_y)
    xy_subs = {x_syms[j]: int(r_x[j]) for j in range(s_next)}
    xy_subs.update({y_syms[j]: int(r_y[j]) for j in range(s_next)})
    A_val = F.convert(add_xy.eval(xy_subs))
    M_val = F.convert(mult_xy.eval(xy_subs))

    # True endpoint values (omniscient bookkeeping)
    z_x_true = _eval_tilde(ac.tilde_W[i + 1], r_x, F)
    z_y_true = _eval_tilde(ac.tilde_W[i + 1], r_y, F)

    true_bridge = F.convert(A_val * (z_x_true + z_y_true) + M_val * z_x_true * z_y_true)
    transcript_consistent_with_truth = bool(gamma_F == true_bridge)

    laundered_in_sumcheck = lie_active and transcript_consistent_with_truth
    # Order matters: state the lie before the laundering of it.
    if lie_active:
        notes.append(CarriedClaimWasFalse(i=i, alpha=int(alpha_i), true_value=int(w_i_true)))
    if laundered_in_sumcheck:
        notes.append(LaunderedInSumCheck(i=i))

    # ---- post-sum-check narration ---------------------------------------------------
    sink.emit(BridgingIntroduced(
        audience=Audience.PUBLIC,
        i=i, m=m, gamma=int(gamma_F),
        r_x=tuple(int(c) for c in r_x),
        r_y=tuple(int(c) for c in r_y),
        A=int(A_val), M=int(M_val),
    ))
    if laundered_in_sumcheck:
        sink.emit(SumCheckLaunderNote(audience=Audience.NARRATOR, i=i))

    # ----------------------------------------------------------------------------
    # FINAL LAYER: no folding -- V checks the bridging equation directly
    # ----------------------------------------------------------------------------
    if final_layer:
        rhs = F.convert(A_val * (z_x_true + z_y_true) + M_val * z_x_true * z_y_true)
        accepted = bool(gamma_F == rhs)
        sink.emit(GkrFinalCheck(
            audience=Audience.PUBLIC,
            i=i, depth=d,
            z_x=int(z_x_true), z_y=int(z_y_true),
            gamma=int(gamma_F), rhs=int(rhs),
            accepted=accepted,
            initial_claim_false=initial_claim_false,
        ))
        if accepted:
            return "accept", (), 0
        notes.append(FinalCheckFailed(i=i))
        return "reject", (), 0

    # ----------------------------------------------------------------------------
    # MIDDLE LAYER: bridging + folding
    # ----------------------------------------------------------------------------
    sink.emit(FoldingStarted(audience=Audience.PUBLIC, i=i))

    prover_must_cheat = not transcript_consistent_with_truth

    t = symbols("t")
    line_subs = {
        W_next.gens[j]: ((1 - t) * int(r_x[j]) + t * int(r_y[j]))
        for j in range(s_next)
    }
    q = Poly(W_next.as_expr().subs(line_subs), t, domain=F)

    kept: Optional[str] = None
    caught_impossible = False

    if not prover_must_cheat:
        zx_star, zy_star = z_x_true, z_y_true
        if lie_active and laundered_in_sumcheck:
            sink.emit(HonestAfterLaunder(audience=Audience.NARRATOR, i=i))
    else:
        suggestion = dishonest_folding_values(
            field=F, A=A_val, M=M_val, gamma=gamma_F,
            z_x_true=z_x_true, z_y_true=z_y_true,
        )
        if suggestion is None:
            caught_impossible = True
            sink.emit(CaughtImpossible(audience=Audience.NARRATOR, i=i))
            zx_star, zy_star = z_x_true, z_y_true
        else:
            zx_s, zy_s, kept = suggestion
            if kept == "both":
                zx_star, zy_star = zx_s, zy_s
                notes.append(BridgeVacuous(i=i))
                sink.emit(VacuousBridge(audience=Audience.NARRATOR, i=i))
            else:
                pair = prover.endpoints(EndpointContext(
                    i=i, zx_suggestion=zx_s, zy_suggestion=zy_s, kept=kept,
                    z_x_true=z_x_true, z_y_true=z_y_true,
                    gamma=gamma_F, A=A_val, M=M_val,
                ))
                if isinstance(pair, Cancelled):
                    return "abort", (), 0
                zx_star, zy_star = pair
            if kept in ("x", "y") and not caught_impossible:
                notes.append(EndpointForged(i=i, kept=kept))
            elif kept is None and not caught_impossible:
                notes.append(EndpointForged(i=i, kept=None))

    # ---- V's bridging check -----------------------------------------------------------
    sink.emit(EndpointsSent(audience=Audience.PUBLIC, i=i,
                            zx_star=int(zx_star), zy_star=int(zy_star)))
    rhs = F.convert(A_val * (zx_star + zy_star) + M_val * zx_star * zy_star)
    bridging_ok = bool(gamma_F == rhs)
    sink.emit(BridgingChecked(audience=Audience.PUBLIC, i=i,
                              gamma=int(gamma_F), rhs=int(rhs), passed=bridging_ok))
    if not bridging_ok:
        notes.append(BridgeFailed(i=i))
        return "reject", (), 0

    # ---- the restriction q*_{i+1} along the line ----------------------------------------
    sink.emit(QIntroduced(audience=Audience.PUBLIC, i=i, s_next=s_next))

    forged_q = prover_must_cheat and not caught_impossible and kept != "both"

    if not forged_q:
        q_star = q
        roots_of_diff: List[int] = []
    else:
        q_star_suggestion, roots_of_diff = dishonest_q_polynomial(
            q_true=q, zx_star=zx_star, zy_star=zy_star,
            deg_bound=s_next, field=F, t=t,
        )
        q_star = prover.q_polynomial(QContext(
            i=i, s_next=s_next, field_mod=p,
            q_true=q, z_x_true=z_x_true, z_y_true=z_y_true,
            suggestion=q_star_suggestion, roots=roots_of_diff, t=t,
        ))
        if isinstance(q_star, Cancelled):
            return "abort", (), 0
        notes.append(QForged(i=i, roots=tuple(int(z) for z in roots_of_diff)))

    # ---- V's checks on q* ----------------------------------------------------------------
    sink.emit(QSent(audience=Audience.PUBLIC, i=i, q_star=q_star))

    q_deg = q_star.degree()
    degree_ok = not (isinstance(q_deg, int) and q_deg > s_next)
    sink.emit(QDegreeChecked(audience=Audience.PUBLIC, i=i,
                             degree=q_deg, s_next=s_next, passed=degree_ok))
    if not degree_ok:
        notes.append(QDegreeViolated(i=i))
        return "reject", (), 0

    q_star_0 = F.convert(q_star.eval({t: 0}))
    q_star_1 = F.convert(q_star.eval({t: 1}))
    endpoints_ok = not (q_star_0 != F.convert(zx_star) or q_star_1 != F.convert(zy_star))
    sink.emit(QEndpointsChecked(
        audience=Audience.PUBLIC, i=i,
        q0=int(q_star_0), q1=int(q_star_1),
        zx_star=int(zx_star), zy_star=int(zy_star),
        passed=endpoints_ok,
    ))
    if not endpoints_ok:
        notes.append(QEndpointsMismatched(i=i))
        return "reject", (), 0

    # ---- fold: sample tau, define rho_{i+1}, carry alpha_{i+1} ------------------------------
    tau = verifier.gkr_tau(i)
    if isinstance(tau, Cancelled):
        return "abort", (), 0
    tau_F = F.convert(int(tau))

    rho_next = tuple(
        F.convert((1 - int(tau_F)) * int(r_x[j]) + int(tau_F) * int(r_y[j]))
        for j in range(s_next)
    )
    alpha_next = F.convert(q_star.eval({t: int(tau_F)}))

    sink.emit(TauSampledAndFolded(
        audience=Audience.PUBLIC, i=i, tau=int(tau_F),
        rho_next=tuple(int(c) for c in rho_next),
        alpha_next=int(alpha_next),
    ))

    # Omniscient bookkeeping: did the fold launder the lie?
    w_next_true = _eval_tilde(ac.tilde_W[i + 1], rho_next, F)
    if forged_q and alpha_next == w_next_true:
        notes.append(FoldLaundered(i=i, tau=int(tau_F)))
        prover.notify_fold_laundered(i, int(tau_F))

    return "continue", rho_next, alpha_next