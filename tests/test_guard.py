from ghost_visitors.browser import EvidenceLog
from ghost_visitors.guard import judge, unmentioned


def make_log():
    log = EvidenceLog(("horizontal_scroll", "small_tap_target"))
    log.add("horizontal_scroll", "/", "page is 980px wide on a 375px screen")
    log.add("small_tap_target", "/order", "2 target(s) under 24px")
    return log


def test_backed_complaint_becomes_a_haunting():
    kept, dropped = judge([{"kind": "horizontal_scroll", "text": "I had to scroll sideways.", "evidence": ["e1"]}], make_log())
    assert dropped == []
    assert kept[0]["evidence"] == ["E1"]
    assert kept[0]["measured"][0]["detail"].startswith("page is 980px")


def test_unbacked_claims_become_whispers_with_reasons():
    complaints = [
        {"kind": "small_text", "text": "The words were tiny.", "evidence": []},
        {"kind": "slow_load", "text": "It took forever.", "evidence": ["E9"]},
        {"kind": "small_tap_target", "text": "Buttons were tiny.", "evidence": ["E1"]},
        {"kind": "other", "text": "I didn't like the colours.", "evidence": ["E1"]},
    ]
    kept, dropped = judge(complaints, make_log())
    assert kept == []
    assert [d["why"] for d in dropped] == [
        "cites no measurement",
        "cites E9, which was never measured",
        "cites E1 (horizontal_scroll), which doesn't show small_tap_target",
        "'other' isn't something the browser can measure",
    ]


def test_duplicates_and_junk_are_ignored():
    complaints = [
        {"kind": "horizontal_scroll", "text": "Sideways!", "evidence": ["E1"]},
        {"kind": "horizontal_scroll", "text": "Sideways again!", "evidence": ["E1"]},
        "not a dict",
        {"kind": "horizontal_scroll", "text": "", "evidence": ["E1"]},
    ]
    kept, dropped = judge(complaints, make_log())
    assert len(kept) == 1 and dropped == []
    assert judge("garbage", make_log()) == ([], [])


def test_unmentioned_lists_measured_but_uncited_evidence():
    log = make_log()
    kept, _ = judge([{"kind": "horizontal_scroll", "text": "Sideways.", "evidence": ["E1"]}], log)
    assert [e["id"] for e in unmentioned(kept, log)] == ["E2"]
