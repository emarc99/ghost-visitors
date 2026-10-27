import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))

from score import markdown, score  # noqa: E402


def visit(ghost, outcome, final_page, evidence, raw):
    return {"ghost": ghost, "outcome": outcome, "final_page": final_page, "steps": [{}] * 3, "seconds": 9.5,
            "evidence": [{"id": f"E{i}", "kind": k, "page": "/", "detail": "d"} for i, k in enumerate(evidence, 1)],
            "raw_complaints": [{"kind": k, "text": "t", "evidence": cites} for k, cites in raw],
            "hauntings": []}


def test_score_rejudges_raw_complaints_and_counts_fake_success(tmp_path):
    broken = [visit("tomas", "gave_up", "/order", ["unnamed_control", "not_keyboard_reachable", "goal_not_completed"],
                    [("not_keyboard_reachable", ["E2 not_keyboard_reachable on /: ..."]), ("slow_load", ["E1"])])]
    fixed = [visit("tomas", "succeeded", "/order", [], [("low_contrast", ["E4"])])]
    for mode, visits in (("broken", broken), ("fixed", fixed)):
        (tmp_path / mode).mkdir()
        (tmp_path / mode / "run.json").write_text(json.dumps({"model": "gemma4:e4b", "visits": visits}))

    s = score(tmp_path)
    assert (s["planted"], s["found_raw"], s["found_guarded"]) == (2, 1, 1)
    assert (s["false_alarms_raw"], s["false_alarms_guarded"]) == (2, 0)
    assert s["unbacked_claims_raw"] == 2
    assert s["fixed_site_complaints_raw"] == 1 and s["fixed_site_complaints_kept"] == 0
    assert s["claimed_success_but_didnt"] == 1
    assert s["rows"][0]["kept"] == ["not_keyboard_reachable"]
    assert "| Planted problems found (of 2) | 1 | 1 |" in markdown(s)
