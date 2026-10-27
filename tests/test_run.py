import json

from ghost_visitors.llm import Usage
from ghost_visitors.personas import GHOSTS
from ghost_visitors.report import render
from ghost_visitors.run import run_haunting


class OneShotLLM:
    model = "gemma4:e4b"
    base_url = "http://localhost:11434/v1"

    def __init__(self):
        self.usage = Usage()
        self.replies = [
            {"thought": "Too small to read.", "fright": 7, "action": "done", "outcome": "gave_up", "reason": "can't read it"},
            {"verdict": "<script>alert(1)</script> My glasses were no use.", "epitaph": "Here lies grey on white.",
             "complaints": [{"kind": "low_contrast", "text": "The grey text vanished.", "evidence": ["E2"]}]},
        ]

    def chat_json(self, system, user):
        return self.replies.pop(0)


def test_run_writes_report_folder(browser, bakery, tmp_path):
    events = []
    run_dir = run_haunting(bakery["broken"], [GHOSTS["rosa"]], OneShotLLM(), out_root=tmp_path,
                           on_event=lambda kind, *args: events.append(kind), browser=browser)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    page = (run_dir / "index.html").read_text(encoding="utf-8")

    visit = run["visits"][0]
    assert [e["kind"] for e in visit["evidence"]] == ["small_text", "low_contrast", "goal_not_completed"]
    assert [h["kind"] for h in visit["hauntings"]] == ["low_contrast"]
    assert events == ["ghost_start", "ghost_done", "run_done"]
    assert "Still haunting" in page and "on this machine, offline" in page
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page
    assert (run_dir / visit["final_screenshot"]).exists()


def test_render_names_remote_endpoints():
    run = {"url": "https://x", "goal": "g", "model": "gemma-3-27b-it", "started": "now", "seconds": 1,
           "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "usage": {}, "visits": []}
    assert "via generativelanguage.googleapis.com" in render(run)
