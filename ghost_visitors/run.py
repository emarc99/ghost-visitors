"""Send a set of ghosts to one URL and write the report folder."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Browser, sync_playwright

from .agent import DEFAULT_GOAL, haunt
from .llm import LLM
from .personas import Ghost
from .report import render


def run_haunting(url: str, ghosts: list[Ghost], llm: LLM, out_root: Path = Path("reports"),
                 goal: str = DEFAULT_GOAL, max_steps: int = 12, headless: bool = True, on_event=None,
                 browser: Browser | None = None) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    host = re.sub(r"[^a-z0-9]+", "-", (urlparse(url).netloc or "site").lower()).strip("-")
    run_dir = out_root / f"{stamp}-{host}"
    run_dir.mkdir(parents=True, exist_ok=True)
    emit = on_event or (lambda *args: None)
    started = time.monotonic()
    visits = []

    def send(b: Browser) -> None:
        for ghost in ghosts:
            emit("ghost_start", ghost)
            visit = haunt(b, ghost, url, llm, run_dir, goal=goal, max_steps=max_steps,
                          on_step=lambda g, s: emit("step", g, s))
            data = visit.as_dict()
            data["persona"] = ghost.epitaph
            visits.append(data)
            emit("ghost_done", ghost, visit)

    if browser is not None:
        send(browser)
    else:
        with sync_playwright() as p:
            own = p.chromium.launch(headless=headless)
            try:
                send(own)
            finally:
                own.close()
    run = {"url": url, "goal": goal, "model": llm.model, "base_url": llm.base_url,
           "started": datetime.now().strftime("%Y-%m-%d %H:%M"), "seconds": round(time.monotonic() - started, 1),
           "usage": llm.usage.as_dict(), "visits": visits}
    (run_dir / "run.json").write_text(json.dumps(run, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "index.html").write_text(render(run), encoding="utf-8")
    emit("run_done", run_dir)
    return run_dir
