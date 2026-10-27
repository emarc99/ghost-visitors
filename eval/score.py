"""Score eval runs from their run.json files alone, so anyone can re-check the numbers without a model.

The guard is re-run on the saved raw complaints and evidence, so a guard change can be
re-scored against old runs without calling the model again.

Usage: python eval/score.py eval/results/<model>/<run>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ghost_visitors.browser import Evidence, EvidenceLog  # noqa: E402
from ghost_visitors.guard import KINDS, judge  # noqa: E402

PLANTED = {
    "marisol": {"slow_load", "horizontal_scroll", "small_tap_target"},
    "tomas": {"unnamed_control", "not_keyboard_reachable"},
    "rosa": {"small_text", "low_contrast"},
}


def kinds(complaints) -> set[str]:
    return {str(c.get("kind", "")).strip().lower() for c in complaints if isinstance(c, dict) and c.get("text")}


def rejudge(visit: dict) -> list[dict]:
    log = EvidenceLog(KINDS, [Evidence(e["id"], e["kind"], e["page"], e["detail"]) for e in visit["evidence"]])
    return judge(visit["raw_complaints"], log)[0]


def score(results: Path) -> dict:
    rows = []
    for mode in ("broken", "fixed"):
        run = json.loads((results / mode / "run.json").read_text(encoding="utf-8"))
        for v in run["visits"]:
            planted = PLANTED[v["ghost"]] if mode == "broken" else set()
            measured = {e["kind"] for e in v["evidence"]}
            hauntings = rejudge(v)
            raw, kept = kinds(v["raw_complaints"]), kinds(hauntings)
            rows.append({
                "mode": mode, "ghost": v["ghost"], "outcome": v["outcome"],
                "reached_thanks": v.get("final_page") == "/thanks",
                "claimed_success": v["outcome"] == "succeeded",
                "planted": sorted(planted),
                "found_raw": sorted(raw & planted), "found_guarded": sorted(kept & planted),
                "false_raw": sorted(raw - planted - {"goal_not_completed"}),
                "false_guarded": sorted(kept - planted - {"goal_not_completed"}),
                "unbacked_raw": sorted(raw - measured),
                "complaints_raw": len([c for c in v["raw_complaints"] if isinstance(c, dict)]),
                "complaints_kept": len(hauntings), "kept": [h["kind"] for h in hauntings],
                "steps": len(v["steps"]), "seconds": v["seconds"],
                "error": v.get("error", ""),
            })
    total_planted = sum(len(r["planted"]) for r in rows)
    summary = {
        "model": run["model"],
        "planted": total_planted,
        "found_raw": sum(len(r["found_raw"]) for r in rows),
        "found_guarded": sum(len(r["found_guarded"]) for r in rows),
        "false_alarms_raw": sum(len(r["false_raw"]) for r in rows),
        "false_alarms_guarded": sum(len(r["false_guarded"]) for r in rows),
        "unbacked_claims_raw": sum(len(r["unbacked_raw"]) for r in rows),
        "fixed_site_complaints_raw": sum(r["complaints_raw"] for r in rows if r["mode"] == "fixed"),
        "fixed_site_complaints_kept": sum(r["complaints_kept"] for r in rows if r["mode"] == "fixed"),
        "claimed_success_but_didnt": sum(r["claimed_success"] and not r["reached_thanks"] for r in rows),
        "rows": rows,
    }
    return summary


def markdown(s: dict) -> str:
    lines = [f"# Eval: {s['model']}", "",
             "| | Gemma alone | Gemma + guard |", "| --- | --- | --- |",
             f"| Planted problems found (of {s['planted']}) | {s['found_raw']} | {s['found_guarded']} |",
             f"| False alarms (kinds not planted) | {s['false_alarms_raw']} | {s['false_alarms_guarded']} |",
             f"| Claims with no matching measurement | {s['unbacked_claims_raw']} | 0 by construction |",
             f"| Complaints about the fixed site | {s['fixed_site_complaints_raw']} | {s['fixed_site_complaints_kept']} |",
             "", f"Ghosts that said they succeeded but never reached the confirmation page: {s['claimed_success_but_didnt']}",
             "", "| Site | Ghost | Outcome | Reached /thanks | Found (alone) | Found (guard) | False (alone) | Steps | Seconds |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in s["rows"]:
        lines.append(f"| {r['mode']} | {r['ghost']} | {r['outcome']} | {'yes' if r['reached_thanks'] else 'no'} | "
                     f"{', '.join(r['found_raw']) or '-'} | {', '.join(r['found_guarded']) or '-'} | "
                     f"{', '.join(r['false_raw']) or '-'} | {r['steps']} | {r['seconds']} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    folder = Path(sys.argv[1])
    result = score(folder)
    (folder / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (folder / "summary.md").write_text(markdown(result), encoding="utf-8")
    print(markdown(result))
