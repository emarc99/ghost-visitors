"""ghost-visitors: send persona ghosts to haunt a website."""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

from .agent import DEFAULT_GOAL
from .llm import LLM, LLMError
from .personas import GHOSTS, pick


def check_model(llm: LLM) -> str | None:
    """Return a helpful message if the model can't be used, else None."""
    try:
        served = llm.ping()
    except LLMError as err:
        local = "localhost" in llm.base_url or "127.0.0.1" in llm.base_url
        hint = "Start Ollama (it runs in the tray after install) or run `ollama serve`." if local else \
            "Check GHOST_LLM_BASE_URL and GHOST_LLM_API_KEY."
        return f"{err}\n{hint}"
    names = {s.removeprefix("models/") for s in served}
    if served and llm.model not in names and f"{llm.model}:latest" not in names:
        return (f"model '{llm.model}' isn't served at {llm.base_url}. Available: {', '.join(sorted(names)[:8])}\n"
                f"For Ollama: `ollama pull {llm.model}`")
    return None


def print_progress(kind, *args):
    if kind == "ghost_start":
        print(f"\n👻 {args[0].name} drifts in…", flush=True)
    elif kind == "step":
        step = args[1]
        print(f"  {step.n:>2}. [{step.page}] {step.thought}  (fright {step.fright}/10)\n      → {step.result}", flush=True)
    elif kind == "ghost_done":
        visit = args[1]
        print(f"  {visit.name}: {visit.outcome}. {len(visit.hauntings)} proven, {len(visit.whispers)} whispers set aside."
              + (f" Error: {visit.error}" if visit.error else ""), flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ghost-visitors", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    h = sub.add_parser("haunt", help="send ghosts to a URL and write a haunting report")
    h.add_argument("url")
    h.add_argument("--ghosts", help=f"comma-separated, from: {', '.join(GHOSTS)} (default: all)")
    h.add_argument("--goal", default=DEFAULT_GOAL)
    h.add_argument("--max-steps", type=int, default=12)
    h.add_argument("--out", type=Path, default=Path("reports"))
    h.add_argument("--model", help="model name (default: $GHOST_LLM_MODEL or gemma4:e2b)")
    h.add_argument("--base-url", help="OpenAI-compatible endpoint (default: $GHOST_LLM_BASE_URL or local Ollama)")
    h.add_argument("--headed", action="store_true", help="show the browser windows")
    h.add_argument("--open", action="store_true", help="open the report when done")

    w = sub.add_parser("web", help="start the local web UI")
    w.add_argument("--port", type=int, default=8765)

    b = sub.add_parser("bakery", help="serve the Marigold Bakery demo site")
    b.add_argument("--mode", choices=("broken", "fixed"), default="broken")
    b.add_argument("--port", type=int, default=8001)

    sub.add_parser("ghosts", help="list the ghosts")

    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    if args.command == "ghosts":
        for g in GHOSTS.values():
            print(f"{g.id:<8} {g.name}: {g.epitaph}")
        return 0

    if args.command == "bakery":
        from demo_site.app import create_app
        print(f"Marigold Bakery ({args.mode}) on http://127.0.0.1:{args.port}")
        create_app(args.mode).run(port=args.port)
        return 0

    if args.command == "web":
        from .web import create_app
        print(f"Ghost Visitors on http://127.0.0.1:{args.port}")
        create_app().run(port=args.port, threaded=True)
        return 0

    llm = LLM()
    if args.model:
        llm.model = args.model
    if args.base_url:
        llm.base_url = args.base_url
    try:
        ghosts = pick(args.ghosts.split(",") if args.ghosts else None)
    except ValueError as err:
        print(err, file=sys.stderr)
        return 2
    problem = check_model(llm)
    if problem:
        print(problem, file=sys.stderr)
        return 2

    from .run import run_haunting
    print(f"Haunting {args.url} with {', '.join(g.name for g in ghosts)} on {llm.model}")
    run_dir = run_haunting(args.url, ghosts, llm, out_root=args.out, goal=args.goal, max_steps=args.max_steps,
                           headless=not args.headed, on_event=print_progress)
    report = (run_dir / "index.html").resolve()
    print(f"\nReport: {report}")
    if args.open:
        webbrowser.open(report.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
