import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from ghost_visitors.cli import check_model, main
from ghost_visitors.llm import LLM


def serve_models(ids):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"data": [{"id": i} for i in ids]}).encode())

        def log_message(self, *args):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_port}/v1"


def test_check_model_explains_unreachable_local_ollama():
    message = check_model(LLM(base_url="http://127.0.0.1:9/v1", model="gemma4:e4b", api_key=None))
    assert "can't reach" in message and "ollama serve" in message


def test_check_model_suggests_pull_for_missing_model():
    httpd, url = serve_models(["llama3:latest"])
    try:
        message = check_model(LLM(base_url=url, model="gemma4:e4b", api_key=None))
        assert "ollama pull gemma4:e4b" in message
        assert check_model(LLM(base_url=url, model="llama3", api_key=None)) is None
    finally:
        httpd.shutdown()


def test_check_model_accepts_ai_studio_style_ids():
    httpd, url = serve_models(["models/gemma-3-27b-it"])
    try:
        assert check_model(LLM(base_url=url, model="gemma-3-27b-it", api_key="k")) is None
    finally:
        httpd.shutdown()


def test_ghosts_command_lists_everyone(capsys):
    assert main(["ghosts"]) == 0
    out = capsys.readouterr().out
    assert "marisol" in out and "tomas" in out and "rosa" in out


def fake_run(tmp_path, hauntings):
    run = {"url": "http://bakery", "goal": "buy bread", "model": "gemma4:e2b", "visits": [{
        "name": "Abuela Rosa", "outcome": "succeeded", "verdict": "Too faint for my eyes.", "whispers": [{}],
        "hauntings": hauntings}]}
    (tmp_path / "run.json").write_text(json.dumps(run), encoding="utf-8")
    (tmp_path / "index.html").write_text("", encoding="utf-8")
    return lambda *args, **kwargs: tmp_path


def test_fail_on_haunting_exits_3_and_writes_summary(tmp_path, monkeypatch):
    haunting = {"kind": "small_text", "text": "Tiny letters.",
                "measured": [{"id": "E1", "page": "/", "detail": "4 text(s) under 12px"}]}
    monkeypatch.setattr("ghost_visitors.cli.check_model", lambda llm: None)
    monkeypatch.setattr("ghost_visitors.run.run_haunting", fake_run(tmp_path, [haunting]))
    summary = tmp_path / "summary.md"
    assert main(["haunt", "http://bakery", "--ghosts", "rosa", "--fail-on-haunting", "--summary", str(summary)]) == 3
    text = summary.read_text(encoding="utf-8")
    assert "### Abuela Rosa: Rested in peace" in text
    assert "- **small_text**: Tiny letters. _(E1 on /: 4 text(s) under 12px)_" in text
    assert "1 unproven whisper(s) set aside" in text


def test_fail_on_haunting_passes_a_clean_site(tmp_path, monkeypatch):
    monkeypatch.setattr("ghost_visitors.cli.check_model", lambda llm: None)
    monkeypatch.setattr("ghost_visitors.run.run_haunting", fake_run(tmp_path, []))
    assert main(["haunt", "http://bakery", "--ghosts", "rosa", "--fail-on-haunting"]) == 0


def test_unknown_ghost_is_rejected(capsys):
    assert main(["haunt", "http://example.com", "--ghosts", "casper"]) == 2
    assert "unknown ghost(s): casper" in capsys.readouterr().err
