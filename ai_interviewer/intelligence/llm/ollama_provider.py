"""Ollama provider: a local model over localhost HTTP, no cloud egress.

Kept on urllib so the offline install needs no extra package, and pointed at
`/api/chat` so the system prompt is a real system message rather than prose
glued onto the front of the user turn.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any

from ai_interviewer.intelligence.llm.base import (
    PROVIDER_OLLAMA,
    LLMFailure,
    LLMReply,
    LLMRequest,
    LLMUnavailable,
    extract_json,
)


logger = logging.getLogger(__name__)

DEFAULT_HOST = "http://127.0.0.1:11434"
MODEL_ENV_VAR = "AI_INTERVIEW_OLLAMA_MODEL"
HOST_ENV_VAR = "OLLAMA_HOST"


def resolve_model(model: str = "") -> str:
    return (model or os.environ.get(MODEL_ENV_VAR, "")).strip()


def resolve_host(host: str = "") -> str:
    value = (host or os.environ.get(HOST_ENV_VAR, "") or DEFAULT_HOST).strip()
    return value.rstrip("/")


class OllamaProvider:
    name = PROVIDER_OLLAMA

    def __init__(self, model: str = "", host: str = "") -> None:
        self.model = resolve_model(model)
        self.host = resolve_host(host)

    # -- availability -------------------------------------------------------

    def is_available(self) -> bool:
        return bool(self.model)

    def unavailable_reason(self) -> str:
        if not self.model:
            return f"No Ollama model configured (set one in settings or {MODEL_ENV_VAR})"
        return ""

    def installed_models(self, timeout: float = 4.0) -> tuple[str, ...]:
        """Ask the daemon what it has pulled; empty when it is not running."""
        try:
            with urllib.request.urlopen(f"{self.host}/api/tags", timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
            return ()
        models = payload.get("models")
        if not isinstance(models, list):
            return ()
        names = [str(item.get("name", "")).strip() for item in models if isinstance(item, dict)]
        return tuple(name for name in names if name)

    def is_running(self, timeout: float = 3.0) -> bool:
        try:
            with urllib.request.urlopen(f"{self.host}/api/tags", timeout=timeout):
                return True
        except (OSError, urllib.error.URLError):
            return False

    # -- completion ---------------------------------------------------------

    def complete(self, request: LLMRequest) -> LLMReply:
        if not self.model:
            raise LLMUnavailable(self.unavailable_reason())

        body: dict[str, Any] = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            "options": {
                "temperature": 0.3,
                "num_predict": max(256, int(request.max_tokens)),
            },
        }
        if request.schema is not None:
            # Newer daemons constrain decoding to the schema; older ones read
            # it as the plain "json" format flag and still return an object.
            body["format"] = request.schema

        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        http_request = urllib.request.Request(
            f"{self.host}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        started = time.monotonic()
        try:
            with urllib.request.urlopen(http_request, timeout=request.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise LLMFailure(f"Ollama returned HTTP {exc.code} for model {self.model}.") from exc
        except (OSError, urllib.error.URLError) as exc:
            raise LLMUnavailable(f"Could not reach Ollama at {self.host}.") from exc
        except (json.JSONDecodeError, ValueError) as exc:
            raise LLMFailure("Ollama returned a response that was not JSON.") from exc
        latency_ms = int((time.monotonic() - started) * 1000)

        text = _message_text(data)
        if not text:
            raise LLMFailure("Ollama returned an empty response.")

        return LLMReply(
            text=text,
            provider=self.name,
            model=self.model,
            data=extract_json(text) if request.schema is not None else None,
            latency_ms=latency_ms,
        )


def _message_text(payload: dict[str, Any]) -> str:
    message = payload.get("message")
    if isinstance(message, dict):
        content = str(message.get("content", "")).strip()
        if content:
            return content
    # /api/generate shape, in case a proxy rewrites the endpoint.
    return str(payload.get("response", "")).strip()
