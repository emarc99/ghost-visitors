"""A small client for any OpenAI-compatible chat endpoint.

Defaults to Ollama on this machine, so nothing leaves it. Point GHOST_LLM_BASE_URL at
another server (Google AI Studio's OpenAI endpoint, a vLLM box, LM Studio) to swap.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "gemma4:e4b"


class LLMError(RuntimeError):
    pass


def parse_json(text: str) -> dict:
    """Pull the first JSON object out of a model reply, tolerating code fences and chatter."""
    start = text.find("{")
    while start != -1:
        try:
            value, _ = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError:
            start = text.find("{", start + 1)
            continue
        if isinstance(value, dict):
            return value
        start = text.find("{", start + 1)
    raise LLMError(f"no JSON object in reply: {text[:200]!r}")


@dataclass
class Usage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0

    def as_dict(self) -> dict:
        return {"calls": self.calls, "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens, "seconds": round(self.seconds, 1)}


@dataclass
class LLM:
    base_url: str = field(default_factory=lambda: os.environ.get("GHOST_LLM_BASE_URL", DEFAULT_BASE_URL))
    model: str = field(default_factory=lambda: os.environ.get("GHOST_LLM_MODEL", DEFAULT_MODEL))
    api_key: str | None = field(default_factory=lambda: os.environ.get("GHOST_LLM_API_KEY"))
    timeout: float = 600
    temperature: float = 0.2
    usage: Usage = field(default_factory=Usage)
    _json_mode: bool = True

    def chat_json(self, system: str, user: str) -> dict:
        # Gemma has no system role; its chat template folds instructions into the first user turn.
        messages = [{"role": "user", "content": f"{system.strip()}\n\n{user.strip()}"}]
        text = self._complete(messages)
        try:
            return parse_json(text)
        except LLMError:
            messages += [{"role": "assistant", "content": text},
                         {"role": "user", "content": "Reply again with only the JSON object."}]
            return parse_json(self._complete(messages))

    def _complete(self, messages: list[dict]) -> str:
        body = {"model": self.model, "messages": messages, "temperature": self.temperature}
        if self._json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            reply = self._post(body)
        except LLMError as err:
            if self._json_mode and "400" in str(err):
                self._json_mode = False
                body.pop("response_format")
                reply = self._post(body)
            else:
                raise
        try:
            return reply["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as err:
            raise LLMError(f"unexpected reply shape: {str(reply)[:200]}") from err

    def _post(self, body: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(f"{self.base_url.rstrip('/')}/chat/completions",
                                     data=json.dumps(body).encode(), headers=headers, method="POST")
        started = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                reply = json.load(resp)
        except urllib.error.HTTPError as err:
            raise LLMError(f"HTTP {err.code}: {err.read().decode(errors='replace')[:300]}") from err
        except urllib.error.URLError as err:
            raise LLMError(f"can't reach {self.base_url}: {err.reason}") from err
        usage = reply.get("usage") or {}
        self.usage.calls += 1
        self.usage.prompt_tokens += usage.get("prompt_tokens", 0)
        self.usage.completion_tokens += usage.get("completion_tokens", 0)
        self.usage.seconds += time.monotonic() - started
        return reply
