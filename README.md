# Ghost Visitors 👻

Persona ghosts, driven by a local open-weight model (Gemma), haunt your website and report what scared them away.

Every site has visitors who quietly leave and never say why: the commuter whose phone shows a page too wide for the screen, the blind visitor whose screen reader announces "edit text, blank", the grandmother who can't read faint grey text even with her glasses on. Ghost Visitors brings them back as ghosts. Each ghost browses your site the way that person really did, decides where to go with Gemma, and writes a haunting report in their own voice.

The rule that keeps it honest: **Gemma speaks, code checks.** A complaint only counts as a *haunting* when it cites something the browser actually measured. Anything else is shown as a *whisper*: kept, but marked unproven.

## The ghosts

| Ghost | Who they were | How they browse | What the browser measures for them |
| --- | --- | --- | --- |
| **Marisol** | Ordered everything on the bus | 375px phone, touch, slow mobile network (300 ms latency, 750 kbps) | Load time over 3 s, pages wider than the screen, tap targets under 24 px |
| **Tomás** | Read the whole web by ear | Keyboard only: Tab, Shift+Tab, Enter, typing. Sees only what a screen reader announces | Controls with no accessible name, clickable things Tab can't reach |
| **Abuela Rosa** | Set the ofrenda every November | Laptop zoomed to 200% | Text under 12 px, text below 4.5:1 contrast |

## How it works

1. **The body.** Playwright opens a browser set up like the ghost's device: viewport, touch, zoom, throttled network, or keyboard only.
2. **Perception.** Each step, code scans the page: controls with their accessible names, the focused element, the visible text, and measurements (load time, page width, target sizes, font sizes, contrast). Tomás never sees controls that Tab can't reach, because for him they don't exist.
3. **Decision.** Gemma reads that perception as the persona and picks one action as JSON: `click`, `fill`, `select`, `scroll`, `back`, or for Tomás `tab`, `shift_tab`, `type`, `enter`, `space`. Then `done`, with `succeeded` or `gave_up`.
4. **Confession.** When the visit ends, Gemma writes a verdict, a tombstone epitaph, and complaints, each citing evidence ids like `E2`.
5. **The guard** (`ghost_visitors/guard.py`) keeps a complaint only if it cites evidence that exists and is of the same kind. The rest become whispers, each with the reason it was set aside.

## Run it

You need Python 3.11+ and [Ollama](https://ollama.com).

```bash
ollama pull gemma4:e2b
python -m venv .venv
.venv/bin/pip install -e .          # Windows: .venv\Scripts\pip install -e .
.venv/bin/playwright install chromium
```

Haunt the demo bakery, which has planted problems:

```bash
ghost-visitors bakery --mode broken &   # http://127.0.0.1:8001
ghost-visitors haunt http://127.0.0.1:8001 --open
```

Or start the web UI and pick a URL and ghosts there:

```bash
ghost-visitors web    # http://127.0.0.1:8765
```

Useful flags: `--ghosts marisol,rosa`, `--goal "Sign up for the newsletter"`, `--max-steps 15`, `--headed` to watch the browsers.

### Other models and endpoints

Any OpenAI-compatible endpoint works. Set these environment variables:

| Variable | Default |
| --- | --- |
| `GHOST_LLM_BASE_URL` | `http://localhost:11434/v1` (Ollama) |
| `GHOST_LLM_MODEL` | `gemma4:e2b` |
| `GHOST_LLM_API_KEY` | unset |

For example, hosted Gemma through Google AI Studio:

```bash
export GHOST_LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
export GHOST_LLM_MODEL=gemma-3-27b-it
export GHOST_LLM_API_KEY=your-key
```

With the default local setup, nothing about the site you test leaves your machine.

## The demo bakery

`demo_site/` is Marigold Bakery, a tiny Día de los Muertos shop. In `broken` mode it ships seven everyday problems: a slow render-blocking script, a fixed 980 px layout, an email field with only placeholder text, 16 px quantity buttons, a "Place order" button that is really a clickable `div`, 11 px body text, and light grey text on white. In `fixed` mode the same pages have none of them, so any complaint there is a false alarm.

## Eval

`python eval/run_eval.py` sends all three ghosts to both bakeries, copies each run's `run.json` into `eval/results/<model>/`, and scores them. `python eval/score.py eval/results/<model>` re-scores the committed runs without a model.

Results are in [`eval/results/`](eval/results/).

## Tests

```bash
pytest
```

The tests run the real browser against both bakeries (no model needed: a scripted stand-in replays decisions) and check that each ghost measures exactly its planted problems on the broken site and nothing on the fixed one.

## Credits

The idea grew out of [Ghost Customers](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/7630733/ghost-customers), my GitLab hackathon project, where scripted personas walk every build in CI. Ghost Visitors is a new project: here an open-weight model drives the browser and can be pointed at any site.

## License

MIT
