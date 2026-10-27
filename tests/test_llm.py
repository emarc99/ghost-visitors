import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from ghost_visitors.llm import LLM, LLMError, parse_json


def test_parse_json_handles_fences_and_chatter():
    assert parse_json('Sure!\n```json\n{"action": "click", "target": 3}\n```') == {"action": "click", "target": 3}
    assert parse_json('{"a": {"b": 1}} trailing') == {"a": {"b": 1}}
    assert parse_json('[1, 2] then {"ok": true}') == {"ok": True}


def test_parse_json_raises_without_object():
    with pytest.raises(LLMError):
        parse_json("I would click the button.")


class FakeServer:
    """An OpenAI-compatible endpoint that replays canned replies and records requests."""

    def __init__(self, replies, reject_json_mode=False):
        self.replies = list(replies)
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append(body)
                if reject_json_mode and "response_format" in body:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"JSON mode is not enabled for this model")
                    return
                payload = {"choices": [{"message": {"content": outer.replies.pop(0)}}],
                           "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode())

            def log_message(self, *args):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/v1"

    def close(self):
        self.httpd.shutdown()


def test_chat_json_folds_system_into_user_and_counts_usage():
    server = FakeServer(['{"action": "done"}'])
    try:
        llm = LLM(base_url=server.url, model="gemma4:e4b", api_key=None)
        assert llm.chat_json("You are a ghost.", "What next?") == {"action": "done"}
        sent = server.requests[0]
        assert [m["role"] for m in sent["messages"]] == ["user"]
        assert sent["messages"][0]["content"].startswith("You are a ghost.")
        assert llm.usage.calls == 1 and llm.usage.prompt_tokens == 10
    finally:
        server.close()


def test_chat_json_retries_once_on_prose():
    server = FakeServer(["I think I'd click it.", '{"action": "click", "target": 2}'])
    try:
        llm = LLM(base_url=server.url, model="m", api_key=None)
        assert llm.chat_json("sys", "user") == {"action": "click", "target": 2}
        assert len(server.requests) == 2
    finally:
        server.close()


def test_falls_back_when_endpoint_rejects_json_mode():
    server = FakeServer(['{"ok": true}'], reject_json_mode=True)
    try:
        llm = LLM(base_url=server.url, model="gemma-3-27b-it", api_key="k")
        assert llm.chat_json("sys", "user") == {"ok": True}
        assert "response_format" not in server.requests[-1]
    finally:
        server.close()
