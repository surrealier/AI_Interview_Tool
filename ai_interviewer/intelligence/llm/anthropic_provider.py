"""Claude provider: the cloud reasoning path, opt-in and off by default.

The `anthropic` SDK is an optional dependency (`requirements-cloud.txt`) so the
offline-first install stays untouched; the import happens inside `complete()`
and a missing package surfaces as `LLMUnavailable`, never as a crash.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ai_interviewer.intelligence.llm.base import (
    EFFORT_HIGH,
    EFFORT_LOW,
    EFFORT_MEDIUM,
    PROVIDER_CLAUDE,
    LLMFailure,
    LLMReply,
    LLMRequest,
    LLMUnavailable,
    extract_json,
)


logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5"
SUPPORTED_MODELS: tuple[str, ...] = (
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-haiku-4-5",
)

# Server-side refusal fallback: if a policy classifier declines the request,
# the API reruns it on a sibling model inside the same call instead of handing
# the candidate an error mid-interview.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# Haiku predates adaptive thinking and the effort control; sending either
# returns a 400, so the request shape is chosen per model family.
_LEGACY_THINKING_PREFIXES = ("claude-haiku-4-5",)

_EFFORTS = (EFFORT_LOW, EFFORT_MEDIUM, EFFORT_HIGH)


def resolve_model(model: str) -> str:
    value = (model or "").strip()
    return value or DEFAULT_MODEL


class AnthropicProvider:
    """One-shot structured completions against the Claude Messages API."""

    name = PROVIDER_CLAUDE

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str = "",
        *,
        use_refusal_fallback: bool = True,
    ) -> None:
        self.model = resolve_model(model)
        self._api_key = (api_key or "").strip()
        self._use_refusal_fallback = use_refusal_fallback
        self._client: Any | None = None
        # Set once the server rejects the beta so later calls skip it.
        self._fallback_rejected = False

    # -- availability -------------------------------------------------------

    @staticmethod
    def sdk_installed() -> bool:
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def has_credentials(self) -> bool:
        if self._api_key:
            return True
        # An unset ANTHROPIC_API_KEY does not mean "no credentials": the SDK
        # also resolves ANTHROPIC_AUTH_TOKEN and an `ant auth login` profile.
        import os

        if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
            return True
        return _oauth_profile_exists()

    def is_available(self) -> bool:
        return self.sdk_installed() and self.has_credentials()

    def unavailable_reason(self) -> str:
        if not self.sdk_installed():
            return "anthropic SDK is not installed (pip install -r requirements-cloud.txt)"
        if not self.has_credentials():
            return "No Claude credentials found (set ANTHROPIC_API_KEY or run: ant auth login)"
        return ""

    # -- completion ---------------------------------------------------------

    def complete(self, request: LLMRequest) -> LLMReply:
        client = self._ensure_client(request.timeout)
        started = time.monotonic()
        try:
            response = self._create(client, request, with_fallback=self._wants_fallback())
        except _FallbackUnsupported:
            self._fallback_rejected = True
            response = self._create(client, request, with_fallback=False)
        latency_ms = int((time.monotonic() - started) * 1000)

        stop_reason = getattr(response, "stop_reason", "")
        if stop_reason == "refusal":
            raise LLMFailure(f"Claude declined the request ({_refusal_category(response)}).")

        text = _first_text_block(response)
        if not text:
            raise LLMFailure("Claude returned no text content.")

        data = extract_json(text) if request.schema is not None else None
        return LLMReply(
            text=text,
            provider=self.name,
            model=str(getattr(response, "model", self.model)),
            data=data,
            latency_ms=latency_ms,
            note="truncated" if stop_reason == "max_tokens" else "",
        )

    def _wants_fallback(self) -> bool:
        return self._use_refusal_fallback and not self._fallback_rejected

    def _create(self, client: Any, request: LLMRequest, *, with_fallback: bool) -> Any:
        payload = self._payload(request)
        try:
            if with_fallback:
                return client.beta.messages.create(
                    betas=[FALLBACK_BETA],
                    fallbacks="default",
                    **payload,
                )
            return client.messages.create(**payload)
        except TypeError as exc:
            # An older SDK that does not know `fallbacks`/`betas` yet.
            if with_fallback:
                logger.info("Claude refusal fallback unsupported by the installed SDK: %s", exc)
                raise _FallbackUnsupported from exc
            raise LLMFailure(f"Claude request was rejected: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 - normalized below
            raise self._translate(exc, with_fallback=with_fallback) from exc

    def _translate(self, exc: Exception, *, with_fallback: bool) -> Exception:
        import anthropic

        if isinstance(exc, anthropic.BadRequestError):
            message = str(getattr(exc, "message", exc))
            if with_fallback and _mentions_fallback(message):
                logger.info("Claude refusal fallback rejected by the API: %s", message)
                return _FallbackUnsupported()
            return LLMFailure(f"Claude rejected the request: {message}")
        if isinstance(exc, anthropic.AuthenticationError):
            return LLMUnavailable("Claude credentials were rejected. Check ANTHROPIC_API_KEY.")
        if isinstance(exc, anthropic.PermissionDeniedError):
            return LLMUnavailable("This Claude key is not allowed to call the Messages API.")
        if isinstance(exc, anthropic.NotFoundError):
            return LLMFailure(f"Unknown Claude model: {self.model}")
        if isinstance(exc, anthropic.RateLimitError):
            return LLMFailure("Claude rate limit reached. Try again in a moment.")
        if isinstance(exc, anthropic.APIStatusError):
            return LLMFailure(f"Claude service error ({exc.status_code}).")
        if isinstance(exc, anthropic.APIConnectionError):
            return LLMUnavailable("Could not reach the Claude API. Check the network connection.")
        return LLMFailure(f"Claude call failed: {exc}")

    def _payload(self, request: LLMRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max(256, int(request.max_tokens)),
            "system": request.system,
            "messages": [{"role": "user", "content": request.user}],
        }
        if self._supports_adaptive_thinking():
            payload["thinking"] = {"type": "adaptive"}
            output_config: dict[str, Any] = {"effort": _effort(request.effort)}
        else:
            output_config = {}
        if request.schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": request.schema}
        if output_config:
            payload["output_config"] = output_config
        return payload

    def _supports_adaptive_thinking(self) -> bool:
        return not self.model.startswith(_LEGACY_THINKING_PREFIXES)

    def _ensure_client(self, timeout: float) -> Any:
        if self._client is not None:
            return self._client
        try:
            import anthropic
        except ImportError as exc:
            raise LLMUnavailable(
                "anthropic SDK is not installed. Run: python -m pip install -r requirements-cloud.txt"
            ) from exc

        kwargs: dict[str, Any] = {"timeout": float(timeout), "max_retries": 1}
        if self._api_key:
            kwargs["api_key"] = self._api_key
        try:
            self._client = anthropic.Anthropic(**kwargs)
        except Exception as exc:  # noqa: BLE001 - surfaced as unavailable
            raise LLMUnavailable(f"Could not create the Claude client: {exc}") from exc
        return self._client


class _FallbackUnsupported(Exception):
    """Internal signal: retry this request without the refusal-fallback beta."""


def _effort(value: str) -> str:
    candidate = (value or "").strip().lower()
    return candidate if candidate in _EFFORTS else EFFORT_MEDIUM


def _first_text_block(response: Any) -> str:
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", "") == "text":
            return str(getattr(block, "text", "")).strip()
    return ""


def _refusal_category(response: Any) -> str:
    details = getattr(response, "stop_details", None)
    category = getattr(details, "category", None) if details is not None else None
    return str(category or "policy")


def _mentions_fallback(message: str) -> bool:
    lowered = message.lower()
    return "fallback" in lowered or "beta" in lowered


def _oauth_profile_exists() -> bool:
    """True when `ant auth login` has stored a profile the SDK can pick up."""
    import os
    from pathlib import Path

    candidates = [Path.home() / ".config" / "anthropic"]
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "anthropic")
    for base in candidates:
        try:
            if base.is_dir() and any(base.iterdir()):
                return True
        except OSError:
            continue
    return False
