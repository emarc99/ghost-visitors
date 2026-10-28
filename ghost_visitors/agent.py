"""The haunting loop: perceive, let Gemma decide as the persona, act, repeat. Then confess."""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Browser, Error as PlaywrightError

from .browser import Body
from .guard import KINDS, judge, unmentioned
from .llm import LLM, LLMError
from .personas import Ghost

DEFAULT_GOAL = "Do what you came here to do: find something you'd want and order it, as you would in real life."

POINTER_ACTIONS = """Actions:
- {"action": "click", "target": <control number>}
- {"action": "fill", "target": <control number>, "text": "<what you type>"}
- {"action": "select", "target": <control number>, "text": "<option to choose>"}
- {"action": "scroll"}
- {"action": "back"}
- {"action": "done", "outcome": "succeeded" or "gave_up", "reason": "<why, in a few words>"}"""

KEYBOARD_ACTIONS = """Actions (keyboard only, like a real screen reader user):
- {"action": "tab"}        move focus to the next control
- {"action": "shift_tab"}  move focus to the previous control
- {"action": "type", "text": "<text>"}  type into the focused control (on a dropdown, type the option)
- {"action": "enter"}      activate the focused link or button, or submit the form
- {"action": "space"}      press the focused button or checkbox
- {"action": "done", "outcome": "succeeded" or "gave_up", "reason": "<why, in a few words>"}
To fill a field: Tab until "Focus is on" shows that field's number, then type.
Enter activates exactly what "Focus is on" names right now, not the control you are heading for."""


ACTION_NAMES = ("click", "fill", "select", "scroll", "back", "tab", "shift_tab", "type", "enter", "space", "done")


@dataclass
class Step:
    n: int
    page: str
    thought: str
    fright: int
    action: dict
    result: str
    screenshot: str


@dataclass
class Visit:
    ghost: str
    name: str
    url: str
    goal: str
    outcome: str = "error"
    reason: str = ""
    final_page: str = ""
    steps: list[Step] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    hauntings: list[dict] = field(default_factory=list)
    whispers: list[dict] = field(default_factory=list)
    also_measured: list[dict] = field(default_factory=list)
    raw_complaints: list = field(default_factory=list)
    raw_report: dict = field(default_factory=dict)
    verdict: str = ""
    epitaph: str = ""
    final_screenshot: str = ""
    seconds: float = 0.0
    error: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def system_prompt(ghost: Ghost, url: str, goal: str) -> str:
    actions = KEYBOARD_ACTIONS if ghost.keyboard_only else POINTER_ACTIONS
    return f"""You are {ghost.name}, a ghost of a real person, visiting a website the way you always did. {ghost.story}
Your voice: {ghost.voice}
You are visiting {url}. Your goal: {goal}

Each turn you see the page as you perceive it. Choose ONE action and reply with only a JSON object:
{{"thought": "<one short sentence, in your voice>", "fright": <0-10, how close you are to leaving>, "action": "...", ...}}
{actions}
When a form asks for details, make up realistic ones (a name, an email like yourname@example.com).
Say done with "succeeded" only when the page confirms your goal is complete. If something truly blocks you, give up."""


def persona_prompt(ghost: Ghost, url: str, goal: str) -> str:
    return (f"You are {ghost.name}, a ghost of a real person. {ghost.story}\nYour voice: {ghost.voice}\n"
            f"You just visited {url}. Your goal was: {goal}")


def step_prompt(history: list[str], seen: str, n: int, max_steps: int) -> str:
    done = "\n".join(history[-6:]) or "nothing yet"
    return f"Step {n} of {max_steps}.\nWhat you did so far:\n{done}\n\nWhat you perceive now:\n{seen}\n\nYour next action, as JSON only:"


def report_prompt(visit: Visit, evidence: list[dict]) -> str:
    journey = "\n".join(f"{s.n}. {s.thought} -> {s.result}" for s in visit.steps) or "(no steps)"
    measured = "\n".join(f"{e['id']} {e['kind']} on {e['page']}: {e['detail']}" for e in evidence) or "(nothing measured)"
    return f"""Your visit is over. Outcome: {visit.outcome} ({visit.reason}).
Your journey:
{journey}

What the browser measured while you were there:
{measured}

Write your haunting report as a JSON object:
{{"verdict": "<one or two sentences, in your voice, about how the visit went>",
  "epitaph": "<one short, spooky-funny line for your tombstone about this website>",
  "complaints": [{{"kind": "<one of: {', '.join(KINDS)}>", "text": "<one or two sentences in your voice>", "evidence": ["<ids like E1>"]}}]}}
Each complaint must cite the evidence ids it rests on. Only complain about things that actually troubled you."""


def unwrap(reply: dict, keys: tuple[str, ...]) -> dict:
    """Small models often nest the answer ({"report": {...}}); find the dict that has the keys we asked for."""
    queue = [reply]
    while queue:
        current = queue.pop(0)
        if any(k in current for k in keys):
            return current
        queue.extend(v for v in current.values() if isinstance(v, dict))
    return reply


def normalize(decision: dict) -> dict:
    action = {k: v for k, v in decision.items() if k not in ("thought", "fright")}
    inner = action.get("action")
    if isinstance(inner, dict):
        action = {**{k: v for k, v in action.items() if k != "action"}, **inner}
    kind = str(action.get("action", "")).strip().lower()
    if not kind:
        named = next((k for k in ACTION_NAMES if k in action), None)
        if named:
            value = action.pop(named)
            kind = named
            if isinstance(value, (int, str)) and str(value).strip("[] ").isdigit():
                action.setdefault("target", value)
    match = re.fullmatch(r"([a-z_]+)\s*\[?(\d+)\]?", kind)
    if match and "target" not in action:
        kind, action["target"] = match.group(1), match.group(2)
    action["action"] = kind
    action.pop("thought", None)
    action.pop("fright", None)
    if "target" in action:
        try:
            action["target"] = int(str(action["target"]).strip("[] "))
        except ValueError:
            pass
    return action


def describe_action(action: dict) -> str:
    kind = action.get("action", "?")
    if "target" in action:
        kind += f" [{action['target']}]"
    if action.get("text"):
        kind += f" '{action['text']}'"
    return kind


def haunt(browser: Browser, ghost: Ghost, url: str, llm: LLM, out_dir: Path,
          goal: str = DEFAULT_GOAL, max_steps: int = 12, on_step=None) -> Visit:
    visit = Visit(ghost=ghost.id, name=ghost.name, url=url, goal=goal)
    started = time.monotonic()
    body = Body(browser, ghost)
    system = system_prompt(ghost, url, goal)
    history: list[str] = []
    try:
        body.goto(url)
        for n in range(1, max_steps + 1):
            scan, _, seen = body.observe()
            shot = f"{ghost.id}-{n:02d}.png"
            body.screenshot(str(out_dir / shot))
            decision = llm.chat_json(system, step_prompt(history, seen, n, max_steps))
            action = normalize(decision)
            flat = {**(decision["action"] if isinstance(decision.get("action"), dict) else {}), **decision}
            thought = str(flat.get("thought", "")).strip()
            fright = _clamp(flat.get("fright"))
            page = urlparse(scan["url"]).path or "/"
            if action["action"] == "done":
                visit.outcome = "succeeded" if str(action.get("outcome", "")).lower() == "succeeded" else "gave_up"
                visit.reason = str(action.get("reason", "")).strip()
                visit.steps.append(Step(n, page, thought, fright, action, "left the site", shot))
                break
            result = body.act(action, scan)
            history.append(f"{n}. {describe_action(action)} -> {result}")
            visit.steps.append(Step(n, page, thought, fright, action, result, shot))
            if on_step:
                on_step(ghost, visit.steps[-1])
        else:
            visit.outcome, visit.reason = "ran_out_of_steps", f"still wandering after {max_steps} steps"
        body.observe()
        visit.final_page = urlparse(body.page.url).path or "/"
        visit.final_screenshot = f"{ghost.id}-final.png"
        body.screenshot(str(out_dir / visit.final_screenshot))
        if visit.outcome != "succeeded":
            body.log.add("goal_not_completed", visit.final_page,
                         f"left after {len(visit.steps)} step(s) on {visit.final_page}: {visit.reason or visit.outcome}")
        evidence = [e.as_dict() for e in body.log.items]
        visit.raw_report = llm.chat_json(persona_prompt(ghost, url, goal), report_prompt(visit, evidence))
        report = unwrap(visit.raw_report, ("complaints", "verdict", "epitaph"))
        visit.raw_complaints = report.get("complaints") or []
        visit.verdict = str(report.get("verdict", "")).strip()
        visit.epitaph = str(report.get("epitaph", "")).strip()
        visit.hauntings, visit.whispers = judge(visit.raw_complaints, body.log)
        visit.also_measured = unmentioned(visit.hauntings, body.log)
        visit.evidence = evidence
    except (LLMError, PlaywrightError) as err:
        visit.outcome, visit.error = "error", str(err).splitlines()[0][:300]
        visit.evidence = [e.as_dict() for e in body.log.items]
    finally:
        body.close()
        visit.seconds = round(time.monotonic() - started, 1)
    return visit


def _clamp(value) -> int:
    try:
        return max(0, min(10, int(value)))
    except (TypeError, ValueError):
        return 0
