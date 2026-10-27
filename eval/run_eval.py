"""Send every ghost to the broken and the fixed Marigold Bakery, keep the raw runs, and score them.

Usage: python eval/run_eval.py [--model gemma4:e4b] [--max-steps 12]
Raw runs (run.json per site) land in eval/results/<model>/, screenshots in reports/eval/.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import threading
from pathlib import Path

from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

from demo_site.app import create_app  # noqa: E402
from ghost_visitors.cli import check_model, print_progress  # noqa: E402
from ghost_visitors.llm import LLM  # noqa: E402
from ghost_visitors.personas import pick  # noqa: E402
from ghost_visitors.run import run_haunting  # noqa: E402
from score import markdown, score  # noqa: E402

GOAL = "Order some bread for the Day of the Dead, as you would in real life."


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model")
    parser.add_argument("--base-url")
    parser.add_argument("--max-steps", type=int, default=12)
    args = parser.parse_args()
    llm = LLM()
    llm.model = args.model or llm.model
    llm.base_url = args.base_url or llm.base_url
    problem = check_model(llm)
    if problem:
        print(problem, file=sys.stderr)
        return 2

    results = ROOT / "eval" / "results" / llm.model.replace(":", "-").replace("/", "-")
    for mode in ("broken", "fixed"):
        server = make_server("127.0.0.1", 0, create_app(mode), threaded=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        print(f"\n=== {mode} bakery ===")
        try:
            run_dir = run_haunting(f"http://127.0.0.1:{server.server_port}/", pick(None), llm,
                                   out_root=ROOT / "reports" / "eval", goal=GOAL, max_steps=args.max_steps,
                                   on_event=print_progress)
        finally:
            server.shutdown()
        (results / mode).mkdir(parents=True, exist_ok=True)
        shutil.copy(run_dir / "run.json", results / mode / "run.json")

    summary = score(results)
    (results / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (results / "summary.md").write_text(markdown(summary), encoding="utf-8")
    print("\n" + markdown(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
