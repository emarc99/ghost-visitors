"""A small local web UI: pick a URL and ghosts, watch them haunt, read the report."""

from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template_string, request, send_from_directory, url_for

from .agent import DEFAULT_GOAL
from .cli import check_model
from .llm import LLM
from .personas import GHOSTS, pick
from .report import CSS

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ghost Visitors</title><style>{{ css|safe }}
form label { display:block; margin: 14px 0 6px; font-weight: 600; }
input[type=url], input[type=text], input[type=number] { width:100%; padding:10px 12px; border-radius:10px; border:1px solid var(--line);
  background:#140f26; color:var(--text); font-size:16px; }
.choices { display:grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap:10px; }
.choice { display:flex; gap:10px; align-items:flex-start; border:1px solid var(--line); border-radius:12px; padding:12px; font-weight:400 !important; cursor:pointer; }
.choice input { margin-top: 4px; } .choice small { color: var(--muted); display:block; }
button { margin-top:18px; background: var(--marigold); color:#1a1205; border:0; border-radius:10px; padding:12px 22px; font-size:17px; font-weight:700; cursor:pointer; }
button:focus-visible, input:focus-visible, a:focus-visible { outline: 3px solid #fde68a; outline-offset: 2px; }
.status { padding:10px 14px; border-radius:10px; margin: 12px 0; } .status.ok { background:#064e3b; } .status.bad { background:#4c0519; }
#log { white-space: pre-wrap; font: 14px/1.5 ui-monospace, monospace; background:#0b0716; border:1px solid var(--line); border-radius:12px; padding:14px; min-height: 200px; }
</style></head><body><div class="papel"></div><div class="wrap">{{ body|safe }}</div></body></html>"""

HOME = """
<h1>Ghost Visitors <span>👻</span></h1>
<p class="sub">Persona ghosts, driven by an open-weight model, haunt a website and report what scared them away.</p>
<div class="status {{ 'bad' if problem else 'ok' }}">
  {% if problem %}Model not ready: {{ problem }}{% else %}Model ready: <b>{{ model }}</b> {{ where }}.{% endif %}
</div>
{% if busy %}<div class="status bad">A haunting is already running. <a href="{{ url_for('job', job_id=busy) }}">Watch it</a>.</div>{% endif %}
<form method="post" action="{{ url_for('start') }}">
  <label for="url">Website to haunt</label>
  <input id="url" name="url" type="url" required placeholder="https://" value="{{ default_url }}">
  <fieldset style="border:0;padding:0;margin:0"><legend style="font-weight:600;margin:14px 0 6px">Ghosts</legend>
  <div class="choices">
  {% for g in ghosts %}
    <label class="choice"><input type="checkbox" name="ghosts" value="{{ g.id }}" checked>
      <span><b>{{ g.name }}</b><small>{{ g.epitaph }}</small></span></label>
  {% endfor %}
  </div></fieldset>
  <label for="goal">What they came to do</label>
  <input id="goal" name="goal" type="text" value="{{ goal }}">
  <label for="max_steps">Steps per ghost</label>
  <input id="max_steps" name="max_steps" type="number" min="3" max="30" value="12" style="max-width:120px">
  <button type="submit" {% if problem or busy %}disabled{% endif %}>Begin the haunting</button>
</form>
<h3>Past hauntings</h3>
{% for r in reports %}
  <div class="item"><a href="{{ url_for('report_file', run=r.dir, name='index.html') }}">{{ r.url }}</a>
  <span class="ev">{{ r.started }} · {{ r.model }} · {{ r.rested }} of {{ r.total }} rested · {{ r.proven }} proven hauntings</span></div>
{% else %}<p class="empty">No hauntings yet.</p>{% endfor %}
"""

JOB = """
<h1>Haunting <span>👻</span></h1><p class="sub">{{ url }}</p>
<div id="log">Summoning…</div>
<p id="done" hidden><a id="report" href="#">Read the haunting report →</a></p>
<p><a href="{{ url_for('home') }}">← Back</a></p>
<script>
async function poll() {
  const r = await fetch({{ status_url|tojson }}); const j = await r.json();
  document.getElementById('log').textContent = j.log.join('\\n') || 'Summoning…';
  if (j.report) { const a = document.getElementById('report'); a.href = j.report; document.getElementById('done').hidden = false; return; }
  if (j.error) { document.getElementById('log').textContent += '\\n\\n' + j.error; return; }
  setTimeout(poll, 1500);
}
poll();
</script>
"""


def create_app(reports: Path = Path("reports"), llm_factory=LLM, runner=None) -> Flask:
    app = Flask(__name__)
    reports = reports.resolve()
    jobs: dict[str, dict] = {}
    lock = threading.Lock()
    if runner is None:
        from .run import run_haunting as runner

    def busy() -> str | None:
        return next((jid for jid, j in jobs.items() if not j["finished"]), None)

    def past() -> list[dict]:
        out = []
        for run_json in sorted(reports.glob("*/run.json"), reverse=True)[:20]:
            try:
                run = json.loads(run_json.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            visits = run.get("visits", [])
            out.append({"dir": run_json.parent.name, "url": run.get("url"), "started": run.get("started"),
                        "model": run.get("model"), "total": len(visits),
                        "rested": sum(v.get("outcome") == "succeeded" for v in visits),
                        "proven": sum(len(v.get("hauntings", [])) for v in visits)})
        return out

    @app.get("/")
    def home():
        llm = llm_factory()
        local = "localhost" in llm.base_url or "127.0.0.1" in llm.base_url
        body = render_template_string(HOME, ghosts=GHOSTS.values(), goal=DEFAULT_GOAL, reports=past(),
                                      problem=check_model(llm), model=llm.model, busy=busy(),
                                      where="on this machine" if local else f"at {llm.base_url}",
                                      default_url=request.args.get("url", ""))
        return render_template_string(PAGE, css=CSS, body=body)

    @app.post("/haunt")
    def start():
        url = request.form.get("url", "").strip()
        if not url.startswith(("http://", "https://")):
            abort(400, "URL must start with http:// or https://")
        try:
            ghosts = pick(request.form.getlist("ghosts") or None)
            max_steps = max(3, min(30, int(request.form.get("max_steps", 12))))
        except ValueError as err:
            abort(400, str(err))
        goal = request.form.get("goal", "").strip() or DEFAULT_GOAL
        with lock:
            if busy():
                return redirect(url_for("job", job_id=busy()))
            job_id = uuid.uuid4().hex[:8]
            job = jobs[job_id] = {"url": url, "log": [], "report": None, "error": None, "finished": False}

        def on_event(kind, *args):
            if kind == "ghost_start":
                job["log"].append(f"\n{args[0].name} drifts in…")
            elif kind == "step":
                s = args[1]
                job["log"].append(f"  {s.n}. [{s.page}] {s.thought} (fright {s.fright}/10)\n     → {s.result}")
            elif kind == "ghost_done":
                v = args[1]
                job["log"].append(f"  {v.name}: {v.outcome}, {len(v.hauntings)} proven, {len(v.whispers)} whispers"
                                  + (f" ({v.error})" if v.error else ""))

        def work():
            try:
                run_dir = runner(url, ghosts, llm_factory(), out_root=reports, goal=goal, max_steps=max_steps,
                                 on_event=on_event)
                job["report"] = url_for_report(run_dir.name)
            except Exception as err:  # surface any failure in the UI rather than a dead thread
                job["error"] = f"The séance failed: {err}"
            finally:
                job["finished"] = True

        threading.Thread(target=work, daemon=True).start()
        return redirect(url_for("job", job_id=job_id))

    def url_for_report(run: str) -> str:
        with app.test_request_context():
            return url_for("report_file", run=run, name="index.html")

    @app.get("/jobs/<job_id>")
    def job(job_id):
        if job_id not in jobs:
            abort(404)
        body = render_template_string(JOB, url=jobs[job_id]["url"], status_url=url_for("job_status", job_id=job_id))
        return render_template_string(PAGE, css=CSS, body=body)

    @app.get("/jobs/<job_id>.json")
    def job_status(job_id):
        if job_id not in jobs:
            abort(404)
        j = jobs[job_id]
        return jsonify(log=j["log"], report=j["report"], error=j["error"], finished=j["finished"])

    @app.get("/reports/<run>/<path:name>")
    def report_file(run, name):
        return send_from_directory(reports / Path(run).name, name)

    return app
