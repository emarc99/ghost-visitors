from ghost_visitors.agent import haunt, normalize, unwrap
from ghost_visitors.llm import Usage
from ghost_visitors.personas import GHOSTS


class ScriptedLLM:
    """Stands in for Gemma: replays decisions in order, then a report."""

    def __init__(self, decisions, report):
        self.replies = list(decisions) + [report]
        self.prompts = []
        self.usage = Usage()

    def chat_json(self, system, user):
        self.prompts.append(user)
        return self.replies.pop(0)


def test_normalize_coerces_targets_and_case():
    assert normalize({"thought": "hm", "action": "Click", "target": "[4]"}) == {"action": "click", "target": 4}


def test_normalize_accepts_shapes_small_models_produce():
    assert normalize({"thought": "hm", "fright": 1, "action": {"action": "click", "target": 3}}) == {"action": "click", "target": 3}
    assert normalize({"action": "click [7]"}) == {"action": "click", "target": 7}
    assert normalize({"fill": "4", "text": "Rosa", "action": ""}) == {"action": "fill", "target": 4, "text": "Rosa"}
    assert normalize({"scroll": True}) == {"action": "scroll"}
    assert normalize({"action": {"action": "fill", "target": "5", "text": "Rosa", "thought": "x"}}) == \
        {"action": "fill", "target": 5, "text": "Rosa"}


def test_unwrap_finds_nested_report():
    nested = {"haunting_report": {"verdict": "v", "complaints": []}}
    assert unwrap(nested, ("complaints", "verdict")) == {"verdict": "v", "complaints": []}
    assert unwrap({"verdict": "v"}, ("verdict",)) == {"verdict": "v"}
    assert unwrap({"other": 1}, ("verdict",)) == {"other": 1}


def test_keyboard_ghost_blocked_by_clickable_div(browser, bakery, tmp_path):
    decisions = [{"thought": "Tab along.", "fright": 2, "action": "tab"}] * 9 + [
        {"thought": "There is no button.", "fright": 9, "action": "done", "outcome": "gave_up",
         "reason": "no way to place the order"}]
    report = {"verdict": "I could not order.", "epitaph": "Here lies an order nobody could submit.",
              "complaints": [
                  {"kind": "not_keyboard_reachable", "text": "Place order never got focus.", "evidence": ["E2"]},
                  {"kind": "slow_load", "text": "It was slow, too.", "evidence": []}]}
    llm = ScriptedLLM(decisions, report)
    visit = haunt(browser, GHOSTS["tomas"], bakery["broken"] + "/order", llm, tmp_path, max_steps=12)

    assert visit.outcome == "gave_up" and visit.error == ""
    assert [e["kind"] for e in visit.evidence] == ["unnamed_control", "not_keyboard_reachable", "goal_not_completed"]
    assert [h["kind"] for h in visit.hauntings] == ["not_keyboard_reachable"]
    assert visit.whispers[0]["why"] == "cites no measurement"
    assert [e["kind"] for e in visit.also_measured] == ["unnamed_control", "goal_not_completed"]
    assert (tmp_path / "tomas-01.png").exists() and (tmp_path / visit.final_screenshot).exists()
    assert "Focus is on" in llm.prompts[0]
    assert llm.prompts[0].startswith("Step 1 of 24.")


def test_pointer_ghost_completes_fixed_order(browser, bakery, tmp_path):
    decisions = [
        {"thought": "Name first.", "fright": 0, "action": "fill", "target": 4, "text": "Marisol"},
        {"thought": "Email.", "fright": 0, "action": "fill", "target": 5, "text": "marisol@example.com"},
        {"thought": "Order!", "fright": 0, "action": "click", "target": 10},
        {"thought": "Done.", "fright": 0, "action": "done", "outcome": "succeeded", "reason": "order confirmed"},
    ]
    report = {"verdict": "Easy.", "epitaph": "Rest in bread.", "complaints": []}
    visit = haunt(browser, GHOSTS["rosa"], bakery["fixed"] + "/order", ScriptedLLM(decisions, report), tmp_path)

    assert visit.outcome == "succeeded"
    assert visit.final_page == "/thanks"
    assert visit.evidence == [] and visit.hauntings == []
