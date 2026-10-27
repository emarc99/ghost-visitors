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


def test_unknown_ghost_is_rejected(capsys):
    assert main(["haunt", "http://example.com", "--ghosts", "casper"]) == 2
    assert "unknown ghost(s): casper" in capsys.readouterr().err
