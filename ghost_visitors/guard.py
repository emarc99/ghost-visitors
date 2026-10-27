"""Gemma speaks, code checks.

A complaint only becomes a "haunting" when it cites evidence the browser actually measured,
of the same kind. Everything else is kept as a "whisper": shown, but marked unproven.
"""

from __future__ import annotations

import re

from .browser import EvidenceLog

KINDS = (
    "slow_load",
    "horizontal_scroll",
    "small_tap_target",
    "unnamed_control",
    "not_keyboard_reachable",
    "small_text",
    "low_contrast",
    "goal_not_completed",
)


def cited_ids(cited) -> list[str]:
    """Small models often quote the whole evidence line ("E1 slow_load on /: ...") instead of "E1"."""
    ids = []
    for item in cited if isinstance(cited, list) else [cited]:
        text = str(item).strip().upper()
        ids.extend(re.findall(r"\bE\d+\b", text) or ([text] if text else []))
    return list(dict.fromkeys(ids))


def judge(complaints: list, log: EvidenceLog) -> tuple[list[dict], list[dict]]:
    kept, dropped, seen_kinds = [], [], set()
    for raw in complaints if isinstance(complaints, list) else []:
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("kind", "")).strip().lower()
        text = str(raw.get("text", "")).strip()
        ids = cited_ids(raw.get("evidence") or [])
        complaint = {"kind": kind, "text": text, "evidence": ids}
        if not text:
            continue
        if not ids:
            dropped.append({**complaint, "why": "cites no measurement"})
            continue
        missing = [i for i in ids if log.get(i) is None]
        if missing:
            dropped.append({**complaint, "why": f"cites {', '.join(missing)}, which was never measured"})
            continue
        if kind not in KINDS:
            dropped.append({**complaint, "why": f"'{kind or 'other'}' isn't something the browser can measure"})
            continue
        matching = [log.get(i) for i in ids if log.get(i).kind == kind]
        if not matching:
            shown = ", ".join(f"{i} ({log.get(i).kind})" for i in ids)
            dropped.append({**complaint, "why": f"cites {shown}, which doesn't show {kind}"})
            continue
        if kind in seen_kinds:
            continue
        seen_kinds.add(kind)
        kept.append({**complaint, "evidence": [e.id for e in matching],
                     "measured": [e.as_dict() for e in matching]})
    return kept, dropped


def unmentioned(kept: list[dict], log: EvidenceLog) -> list[dict]:
    cited = {i for c in kept for i in c["evidence"]}
    return [e.as_dict() for e in log.items if e.id not in cited]
