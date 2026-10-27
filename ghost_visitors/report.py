"""Render a run as one self-contained HTML page (screenshots sit next to it)."""

from __future__ import annotations

from html import escape
from urllib.parse import urlparse

OUTCOMES = {
    "succeeded": ("Rested in peace", "ok"),
    "gave_up": ("Still haunting", "bad"),
    "ran_out_of_steps": ("Lost between worlds", "bad"),
    "error": ("The séance failed", "warn"),
}

CSS = """
:root { --night:#120c22; --panel:#1d1533; --line:#3b2d5c; --text:#ece7f6; --muted:#a99cc7;
        --marigold:#f59e0b; --ok:#34d399; --bad:#fb7185; --warn:#fbbf24; }
* { box-sizing: border-box; }
body { margin:0; background:var(--night); color:var(--text); font:16px/1.55 system-ui, "Segoe UI", sans-serif; }
.wrap { max-width: 980px; margin: 0 auto; padding: 32px 20px 64px; }
.papel { height: 14px; background: repeating-linear-gradient(90deg, #f59e0b 0 28px, #db2777 28px 56px, #7c3aed 56px 84px, #10b981 84px 112px);
         -webkit-mask: radial-gradient(circle 7px at 14px 0, transparent 98%, #000) 0 0/28px 14px; mask: radial-gradient(circle 7px at 14px 0, transparent 98%, #000) 0 0/28px 14px; }
h1 { font-size: 30px; margin: 18px 0 4px; } h1 span { color: var(--marigold); }
.sub { color: var(--muted); margin: 0 0 24px; word-break: break-all; }
.summary { display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:12px; margin-bottom: 28px; }
.tile { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:14px; }
.tile b { display:block; font-size: 18px; } .tile small { color: var(--muted); }
.ghost { background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:22px; margin: 22px 0; }
.ghost header { display:flex; justify-content:space-between; gap:12px; align-items:flex-start; flex-wrap:wrap; }
.ghost h2 { margin:0; font-size: 24px; } .who { color: var(--muted); margin: 2px 0 0; font-style: italic; }
.badge { border-radius:999px; padding:4px 12px; font-weight:600; font-size:14px; white-space:nowrap; }
.badge.ok { background:#064e3b; color:var(--ok); } .badge.bad { background:#4c0519; color:var(--bad); } .badge.warn { background:#451a03; color:var(--warn); }
blockquote { margin: 16px 0; padding: 10px 16px; border-left: 3px solid var(--marigold); color: #f5ecd9; font-size: 17px; }
.stone { margin: 14px auto 6px; max-width: 420px; text-align:center; background: linear-gradient(#4b4560, #2d2840); border-radius: 120px 120px 10px 10px;
         padding: 26px 22px 16px; color:#e9e4f5; font-family: Georgia, serif; box-shadow: 0 8px 0 #0a0714; }
.stone small { display:block; letter-spacing: .2em; color: #b9b1cf; margin-bottom: 6px; }
h3 { margin: 22px 0 8px; font-size: 15px; letter-spacing: .08em; text-transform: uppercase; color: var(--marigold); }
.item { border:1px solid var(--line); border-radius:10px; padding:10px 12px; margin:8px 0; }
.item .why, .item .ev { display:block; color: var(--muted); font-size: 14px; margin-top: 4px; }
.kind { font: 12px ui-monospace, monospace; background:#2a2045; color:#d8ccf5; padding:2px 6px; border-radius:6px; margin-right:6px; }
.whisper { opacity: .75; border-style: dashed; }
table { width:100%; border-collapse: collapse; font-size: 14px; } td, th { border-top:1px solid var(--line); padding:8px 6px; vertical-align: top; text-align:left; }
th { color: var(--muted); font-weight: 500; }
.fright { display:inline-block; height:8px; border-radius:4px; background: linear-gradient(90deg, var(--ok), var(--warn), var(--bad)); }
.shots { display:flex; gap:12px; flex-wrap:wrap; margin-top: 10px; } .shots img { max-height: 260px; border-radius:8px; border:1px solid var(--line); }
a { color: var(--marigold); } footer { color: var(--muted); font-size: 14px; margin-top: 30px; }
.empty { color: var(--muted); font-style: italic; }
"""


def _e(value) -> str:
    return escape(str(value or ""))


def _item(c: dict, whisper: bool = False) -> str:
    extra = (f'<span class="why">Unproven: {_e(c["why"])}</span>' if whisper else
             "".join(f'<span class="ev">{_e(m["id"])} measured on {_e(m["page"])}: {_e(m["detail"])}</span>'
                     for m in c.get("measured", [])))
    return f'<div class="item{" whisper" if whisper else ""}"><span class="kind">{_e(c.get("kind") or "other")}</span>{_e(c["text"])}{extra}</div>'


def _visit(v: dict) -> str:
    label, tone = OUTCOMES.get(v["outcome"], OUTCOMES["error"])
    parts = [f'<section class="ghost" id="{_e(v["ghost"])}"><header><div><h2>{_e(v["name"])}</h2>'
             f'<p class="who">{_e(v.get("persona", ""))}</p></div><span class="badge {tone}">{label}</span></header>']
    if v.get("error"):
        parts.append(f'<p class="empty">Error: {_e(v["error"])}</p>')
    if v.get("verdict"):
        parts.append(f"<blockquote>{_e(v['verdict'])}</blockquote>")
    if v.get("epitaph"):
        parts.append(f'<div class="stone"><small>R.I.P.</small>{_e(v["epitaph"])}</div>')
    parts.append("<h3>Hauntings (proven)</h3>")
    parts.append("".join(_item(c) for c in v["hauntings"]) or '<p class="empty">Nothing proven. This ghost rests easy.</p>')
    if v["whispers"]:
        parts.append("<h3>Whispers (Gemma said it, nothing measured backs it)</h3>")
        parts.append("".join(_item(c, whisper=True) for c in v["whispers"]))
    if v["also_measured"]:
        parts.append("<h3>Also measured</h3>")
        parts.append("".join(f'<div class="item"><span class="kind">{_e(m["kind"])}</span>{_e(m["detail"])} '
                             f'<span class="ev">{_e(m["id"])} on {_e(m["page"])}</span></div>' for m in v["also_measured"]))
    rows = "".join(
        f'<tr><td>{s["n"]}</td><td>{_e(s["page"])}</td><td>{_e(s["thought"])}</td>'
        f'<td><span class="fright" style="width:{max(4, s["fright"] * 8)}px" title="fright {s["fright"]}/10"></span></td>'
        f'<td><code>{_e(_action(s["action"]))}</code><br><small>{_e(s["result"])}</small></td>'
        f'<td><a href="{_e(s["screenshot"])}">view</a></td></tr>' for s in v["steps"])
    parts.append(f"<h3>The visit, step by step</h3><table><tr><th>#</th><th>Page</th><th>Thought</th><th>Fright</th>"
                 f"<th>Action</th><th></th></tr>{rows}</table>")
    shots = [s["screenshot"] for s in v["steps"][:1]] + ([v["final_screenshot"]] if v.get("final_screenshot") else [])
    if shots:
        parts.append('<div class="shots">' + "".join(f'<a href="{_e(s)}"><img src="{_e(s)}" alt="{_e(v["name"])} screenshot"></a>'
                                                       for s in shots) + "</div>")
    parts.append(f'<p class="who">Outcome: {_e(v["outcome"])}{" (" + _e(v["reason"]) + ")" if v.get("reason") else ""} · '
                 f'{len(v["steps"])} steps · {v["seconds"]}s</p></section>')
    return "".join(parts)


def _action(a: dict) -> str:
    text = a.get("action", "?")
    if "target" in a:
        text += f" [{a['target']}]"
    if a.get("text"):
        text += f" '{a['text']}'"
    return text


def render(run: dict) -> str:
    visits = run["visits"]
    proven = sum(len(v["hauntings"]) for v in visits)
    whispers = sum(len(v["whispers"]) for v in visits)
    rested = sum(v["outcome"] == "succeeded" for v in visits)
    host = urlparse(run["base_url"]).hostname or ""
    where = "on this machine, offline" if host in ("localhost", "127.0.0.1") else f"via {host}"
    tiles = (f'<div class="tile"><b>{rested} of {len(visits)}</b><small>ghosts got what they came for</small></div>'
             f'<div class="tile"><b>{proven}</b><small>proven hauntings</small></div>'
             f'<div class="tile"><b>{whispers}</b><small>unproven whispers set aside</small></div>'
             f'<div class="tile"><b>{_e(run["model"])}</b><small>ran {where}</small></div>')
    usage = run.get("usage", {})
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Haunting report · {_e(run["url"])}</title><style>{CSS}</style></head><body><div class="papel"></div><div class="wrap">
<h1>Haunting report <span>👻</span></h1><p class="sub">{_e(run["url"])} · {_e(run["started"])}<br>Goal: {_e(run["goal"])}</p>
<div class="summary">{tiles}</div>
{"".join(_visit(v) for v in visits)}
<footer>Ghost Visitors · {_e(run["model"])} {where} · {usage.get("calls", 0)} model calls, {usage.get("prompt_tokens", 0)} prompt + {usage.get("completion_tokens", 0)} completion tokens, {usage.get("seconds", 0)}s of thinking · run took {run["seconds"]}s</footer>
</div></body></html>"""
