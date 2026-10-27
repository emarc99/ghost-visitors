import pytest

from ghost_visitors.browser import Body, EvidenceLog, measure
from ghost_visitors.personas import GHOSTS

EXPECTED_BROKEN = {
    "marisol": {"slow_load", "horizontal_scroll", "small_tap_target"},
    "tomas": {"unnamed_control", "not_keyboard_reachable"},
    "rosa": {"small_text", "low_contrast"},
}


def walk(browser, base, ghost_id):
    body = Body(browser, GHOSTS[ghost_id])
    try:
        for path in ("/", "/order", "/thanks?name=Rosa&qty=1&item=conchas&day=November+1&email=r%40example.com"):
            body.goto(base + path)
            body.observe()
        return {e.kind for e in body.log.items}, body.log
    finally:
        body.close()


@pytest.mark.parametrize("ghost_id", sorted(EXPECTED_BROKEN))
def test_each_ghost_measures_its_planted_problems(browser, bakery, ghost_id):
    kinds, _ = walk(browser, bakery["broken"], ghost_id)
    assert kinds == EXPECTED_BROKEN[ghost_id]


@pytest.mark.parametrize("ghost_id", sorted(EXPECTED_BROKEN))
def test_fixed_bakery_measures_clean(browser, bakery, ghost_id):
    kinds, log = walk(browser, bakery["fixed"], ghost_id)
    assert kinds == set(), [e.detail for e in log.items]


def test_keyboard_ghost_cannot_see_the_clickable_div(browser, bakery):
    body = Body(browser, GHOSTS["tomas"])
    try:
        body.goto(bakery["broken"] + "/order")
        _, _, seen = body.observe()
    finally:
        body.close()
    assert "Place order" in seen  # it's read out as text...
    assert '"Place order"' not in seen  # ...but never announced as a control
    assert "(no name announced)" in seen


def test_keyboard_ghost_hears_focus_and_typing_into_nothing(browser, bakery):
    body = Body(browser, GHOSTS["tomas"])
    try:
        body.goto(bakery["fixed"] + "/order")
        scan, _, seen = body.observe()
        assert "Focus is on: the page itself" in seen
        assert "nothing took the text" in body.act({"action": "type", "text": "Rosa"}, scan)
        for _ in range(3):
            heard = body.act({"action": "tab"}, scan)
        assert heard.endswith('combobox "Bread"')
        body.act({"action": "tab"}, scan)
        assert body.act({"action": "type", "text": "Rosa"}, scan) == "typed 'Rosa' into [4] 'Your name'"
    finally:
        body.close()


def test_keyboard_ghost_can_submit_fixed_form(browser, bakery):
    body = Body(browser, GHOSTS["tomas"])
    try:
        body.goto(bakery["fixed"] + "/order")
        scan, _, _ = body.observe()
        # Tab order: Breads, Order, bread select, name; then email.
        steps = [("tab", None)] * 4 + [("type", "Rosa"), ("tab", None), ("type", "rosa@example.com"), ("enter", None)]
        for kind, text in steps:
            result = body.act({"action": kind, "text": text}, scan)
        assert "/thanks" in result
    finally:
        body.close()


def test_blocked_submit_is_reported_to_the_ghost(browser, bakery):
    body = Body(browser, GHOSTS["rosa"])
    try:
        body.goto(bakery["fixed"] + "/order")
        scan, _, _ = body.observe()
        submit = next(c["id"] for c in scan["controls"] if c["name"] == "Place order")
        result = body.act({"action": "click", "target": submit}, scan)
    finally:
        body.close()
    assert "the form was not sent, the browser points at [4]" in result


def test_measure_reports_each_kind_once_per_page():
    log = EvidenceLog(("horizontal_scroll",))
    scan = {"url": "http://x/order", "scroll_width": 980, "inner_width": 375, "controls": [], "texts": [], "load_ms": 100}
    assert [e.id for e in measure(scan, log)] == ["E1"]
    assert measure(scan, log) == []
    assert log.get("E1").detail == "page is 980px wide on a 375px screen"


def test_links_inside_sentences_are_exempt_from_target_size():
    log = EvidenceLog(("small_tap_target",))
    control = {"id": 1, "role": "link", "name": "terms", "focusable": True, "width": 30, "height": 18,
               "in_sentence": True, "placeholder": ""}
    scan = {"url": "http://x/", "scroll_width": 375, "inner_width": 375, "controls": [control], "texts": [], "load_ms": 1}
    assert measure(scan, log) == []
