"""
Transcript-feature tests.

`sum_check(save_transcript=path)` writes the PUBLIC slice of the event log --
the proof itself: the prover's messages and the verifier's challenges -- as
JSON. These tests validate the structure and cross-check it against the
blessed golden *text* of the same run: the challenges printed in the
narration must be exactly the challenges recorded in the JSON.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "golden"))

from harness import (  # noqa: E402
    SCENARIOS,
    load_golden,
    run_scenario,
)

_BY_NAME = {s.name: s for s in SCENARIOS}


def _transcript_scenario(base_name: str, path: Path, *, commit: bool = False):
    kwargs = "use_commitment=True, " if commit else ""
    code = (
        "from gkr.protocol.sumcheck_session import sum_check\n"
        f"res = sum_check({kwargs}save_transcript=r'{path}')"
    )
    return replace(_BY_NAME[base_name], code=code)


def test_transcript_json_matches_golden_narration(tmp_path: Path) -> None:
    out_path = tmp_path / "proof.json"
    scenario = _transcript_scenario("sumcheck_spectator_honest", out_path)
    stdout, proc = run_scenario(scenario)
    assert proc.returncode == 0, proc.stderr[-2000:]

    data = json.loads(out_path.read_text(encoding="utf-8"))

    # structure: the proof is (claim, per-round message+challenge, final check)
    assert data["field_mod"] == 331
    assert data["num_vars"] == 3
    assert data["claim"] is not None
    assert len(data["rounds"]) == 3
    for rec in data["rounds"]:
        assert set(rec) == {"j", "polynomial", "challenge"}
        assert {"gens", "terms", "expr"} <= set(rec["polynomial"])
    assert data["final"]["terminal_claim"] is not None
    assert data["verdict"] == "accepted"

    # cross-check: challenges in the JSON == challenges printed in the golden
    golden = load_golden("sumcheck_spectator_honest")
    printed = [int(m) for m in re.findall(r"here r_\d+ = (\d+)\.", golden)]
    recorded = [rec["challenge"] for rec in data["rounds"]]
    assert recorded == printed


def test_transcript_records_commitment(tmp_path: Path) -> None:
    out_path = tmp_path / "proof.json"
    scenario = _transcript_scenario("sumcheck_commitment_honest", out_path, commit=True)
    stdout, proc = run_scenario(scenario)
    assert proc.returncode == 0, proc.stderr[-2000:]

    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert "commitment" in data["final"]
    check = data["final"]["commitment_check"]
    assert check["ok"] is True
    assert check["original"] == check["recomputed"] == data["final"]["commitment"]
    assert data["verdict"] == "accepted"


# ----------------------------------------------------------------------------
# GKR transcripts
# ----------------------------------------------------------------------------

def _gkr_transcript_scenario(base_name: str, path: Path):
    code = (
        "from gkr.protocol.gkr_session import gkr\n"
        f"res = gkr(save_transcript=r'{path}')"
    )
    return replace(_BY_NAME[base_name], code=code)


def test_gkr_transcript_json_matches_golden_narration(tmp_path: Path) -> None:
    out_path = tmp_path / "gkr_proof.json"
    scenario = _gkr_transcript_scenario("gkr_spectator_dishonest", out_path)
    stdout, proc = run_scenario(scenario)
    assert proc.returncode == 0, proc.stderr[-2000:]

    data = json.loads(out_path.read_text(encoding="utf-8"))

    # structure: claims, rho_0/alpha_0, one record per layer, verdict
    assert data["field_mod"] == 331
    assert data["depth"] == len(data["layers"]) == 2
    assert data["claims"] and data["alpha_0"] is not None
    first, last = data["layers"]
    # default circuit '(3*2) + (4 + 1)': s_1 = 1 and s_2 = 2, so the two layer
    # transitions run 2*s_1 = 2 and 2*s_2 = 4 sum-check rounds respectively
    assert len(first["polynomials"]) == len(first["challenges"]) == 2
    assert len(last["polynomials"]) == len(last["challenges"]) == 4
    assert {"gamma", "endpoints", "q_star", "tau", "rho_next", "alpha_next"} <= set(first)
    assert "tau" not in last          # the final layer does not fold
    assert data["verdict"] in ("accepted", "rejected")

    # cross-checks against the golden narration of the same run
    golden = load_golden("gkr_spectator_dishonest")
    tau_printed = [int(x) for x in re.findall(r"here \u03c4_\d+ = (\d+)\.", golden)]
    assert tau_printed == [first["tau"]]
    # Every challenge recorded in the proof is announced in the narration --
    # including the last of each layer's sum-check, which GKR used to leave for
    # the reader to reverse-engineer out of the r_y vector.
    printed_r = [int(x) for x in re.findall(r"here r_\d+ = (\d+)\.", golden)]
    assert printed_r == first["challenges"] + last["challenges"]