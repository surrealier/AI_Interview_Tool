from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from ai_interviewer.config import (
    AI_PROVIDER_AUTO,
    AI_PROVIDER_CLAUDE,
    AI_PROVIDER_OFFLINE,
    AI_PROVIDER_OLLAMA,
    DEFAULT_CLAUDE_MODEL,
    SUPPORTED_AI_PROVIDERS,
    AppConfig,
)
from ai_interviewer.intelligence.llm import anthropic_provider, registry
from ai_interviewer.intelligence.llm.base import (
    LLMFailure,
    LLMReply,
    LLMRequest,
    LLMUnavailable,
    extract_json,
    normalize_question,
)


@pytest.fixture(autouse=True)
def _hermetic_environment(monkeypatch: pytest.MonkeyPatch):
    """Provider availability must come from the test, not the developer's shell.

    Both providers fall back to environment variables when a setting is blank,
    so a machine with OLLAMA or Claude configured would otherwise flip results.
    """
    for name in (
        "AI_INTERVIEW_OLLAMA_MODEL",
        "OLLAMA_HOST",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(anthropic_provider, "_oauth_profile_exists", lambda: False)


# -- shared contract ---------------------------------------------------------


def test_config_and_registry_provider_names_agree() -> None:
    """config.py keeps its own literals so importing it stays cheap; they must
    not drift from the registry that actually resolves providers."""
    assert set(SUPPORTED_AI_PROVIDERS) == set(registry.AI_PROVIDERS)
    assert DEFAULT_CLAUDE_MODEL == anthropic_provider.DEFAULT_MODEL
    assert DEFAULT_CLAUDE_MODEL in anthropic_provider.SUPPORTED_MODELS


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('{"a": 1}', {"a": 1}),
        ('```json\n{"a": 1}\n```', {"a": 1}),
        ('Sure! Here it is:\n{"a": 1}\nHope that helps.', {"a": 1}),
        ("not json at all", None),
        ("", None),
        ("[1, 2, 3]", None),
    ],
)
def test_extract_json_tolerates_wrapped_output(raw: str, expected: Any) -> None:
    assert extract_json(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("What did that cost", "What did that cost?"),
        ("  Q1. What happened?  ", "What happened?"),
        ('"How did you measure it?"', "How did you measure it?"),
        ("2) And then?\nExtra line", "And then?"),
        ("", ""),
    ],
)
def test_normalize_question_produces_one_clean_line(raw: str, expected: str) -> None:
    assert normalize_question(raw) == expected


# -- chain behaviour ---------------------------------------------------------


class _Provider:
    def __init__(self, name: str, *, available=True, error: Exception | None = None, text="ok"):
        self.name = name
        self.model = f"{name}-model"
        self._available = available
        self._error = error
        self._text = text
        self.calls = 0

    def is_available(self) -> bool:
        return self._available

    def unavailable_reason(self) -> str:
        return f"{self.name} is off"

    def complete(self, request: LLMRequest) -> LLMReply:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return LLMReply(text=self._text, provider=self.name, model=self.model)


def _request() -> LLMRequest:
    return LLMRequest(system="s", user="u")


def test_empty_chain_returns_none_so_callers_go_offline() -> None:
    chain = registry.ProviderChain()
    assert chain.enabled is False
    assert chain.complete(_request()) is None
    assert chain.describe() == "offline"


def test_first_healthy_provider_wins() -> None:
    first = _Provider("first")
    second = _Provider("second")
    chain = registry.ProviderChain(providers=[first, second])
    reply = chain.complete(_request())
    assert reply is not None and reply.provider == "first"
    assert second.calls == 0


def test_failing_provider_is_stepped_over() -> None:
    broken = _Provider("broken", error=LLMFailure("boom"))
    good = _Provider("good")
    chain = registry.ProviderChain(providers=[broken, good])
    reply = chain.complete(_request())
    assert reply is not None and reply.provider == "good"
    assert chain.last_error == ""  # cleared by the successful call


def test_unavailable_provider_records_a_reason() -> None:
    chain = registry.ProviderChain(providers=[_Provider("off", available=False)])
    assert chain.complete(_request()) is None
    assert "off is off" in chain.last_error


def test_unexpected_exception_does_not_escape_the_chain() -> None:
    chain = registry.ProviderChain(providers=[_Provider("wild", error=ValueError("unexpected"))])
    assert chain.complete(_request()) is None
    assert "unexpected" in chain.last_error


# -- selection ---------------------------------------------------------------


def test_offline_selection_builds_an_empty_chain() -> None:
    chain = registry.build_chain(registry.AISettings(provider=AI_PROVIDER_OFFLINE))
    assert chain.enabled is False


def test_ollama_needs_a_model_name() -> None:
    without = registry.build_chain(registry.AISettings(provider=AI_PROVIDER_OLLAMA))
    with_model = registry.build_chain(
        registry.AISettings(provider=AI_PROVIDER_OLLAMA, ollama_model="llama3")
    )
    assert without.enabled is False
    assert with_model.enabled is True


def test_cloud_is_never_in_the_chain_without_consent() -> None:
    chain = registry.build_chain(
        registry.AISettings(provider=AI_PROVIDER_CLAUDE, claude_api_key="sk-test", allow_cloud=False)
    )
    assert chain.enabled is False
    assert any("cloud analysis is turned off" in note for note in chain.skipped)


def test_auto_puts_the_local_model_before_the_cloud(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(anthropic_provider.AnthropicProvider, "sdk_installed", staticmethod(lambda: True))
    chain = registry.build_chain(
        registry.AISettings(
            provider=AI_PROVIDER_AUTO,
            ollama_model="llama3",
            claude_api_key="sk-test",
            allow_cloud=True,
        )
    )
    assert [provider.name for provider in chain.providers] == ["ollama", "claude"]


def test_settings_come_from_the_config(tmp_path) -> None:
    config = AppConfig(
        config_path=tmp_path / "config.json",
        ai_provider=AI_PROVIDER_CLAUDE,
        enable_cloud_ai=True,
        ollama_model="llama3",
        ai_effort="high",
    )
    settings = registry.AISettings.from_config(config, "sk-test")
    assert settings.provider == AI_PROVIDER_CLAUDE
    assert settings.allow_cloud is True
    assert settings.effort == "high"
    assert settings.claude_api_key == "sk-test"
    assert settings.uses_cloud() is True


def test_legacy_provider_value_is_normalized() -> None:
    assert registry.normalize_provider("ollama") == AI_PROVIDER_OLLAMA
    assert registry.normalize_provider("Rules") == AI_PROVIDER_OFFLINE
    assert registry.normalize_provider(None) == AI_PROVIDER_OFFLINE


def test_provider_statuses_always_list_offline_as_available() -> None:
    statuses = registry.provider_statuses(registry.AISettings())
    by_name = {status.name: status for status in statuses}
    assert by_name[AI_PROVIDER_OFFLINE].available is True
    assert by_name[AI_PROVIDER_CLAUDE].requires_network is True
    assert by_name[AI_PROVIDER_CLAUDE].available is False


# -- Claude request shape ----------------------------------------------------


class _FakeAnthropicModule(types.ModuleType):
    """Minimal stand-in for the SDK, recording the request payload."""

    def __init__(self) -> None:
        super().__init__("anthropic")
        module = self

        class APIError(Exception):
            pass

        class BadRequestError(APIError):
            def __init__(self, message: str = "bad request"):
                super().__init__(message)
                self.message = message

        class AuthenticationError(APIError):
            pass

        class PermissionDeniedError(APIError):
            pass

        class NotFoundError(APIError):
            pass

        class RateLimitError(APIError):
            pass

        class APIStatusError(APIError):
            def __init__(self, message: str = "status", status_code: int = 500):
                super().__init__(message)
                self.message = message
                self.status_code = status_code

        class APIConnectionError(APIError):
            pass

        class _Block:
            def __init__(self, text: str):
                self.type = "text"
                self.text = text

        class _Response:
            def __init__(self, text: str, stop_reason: str = "end_turn", model: str = "claude-opus-5"):
                self.content = [_Block(text)]
                self.stop_reason = stop_reason
                self.stop_details = None
                self.model = model

        class _Messages:
            def __init__(self, beta: bool):
                self._beta = beta

            def create(self, **kwargs):
                if self._beta:
                    module.beta_calls.append(kwargs)
                    if module.beta_mode == "typeerror":
                        raise TypeError("unexpected keyword argument 'fallbacks'")
                    if module.beta_mode == "badrequest":
                        raise BadRequestError("fallbacks is not supported")
                else:
                    module.calls.append(kwargs)
                if module.raise_next is not None:
                    error = module.raise_next
                    module.raise_next = None
                    raise error
                return _Response(module.reply_text, module.stop_reason)

        class _Beta:
            def __init__(self):
                self.messages = _Messages(beta=True)

        class Anthropic:
            def __init__(self, **kwargs):
                module.client_kwargs.append(kwargs)
                self.messages = _Messages(beta=False)
                self.beta = _Beta()

        self.calls: list[dict] = []
        self.beta_calls: list[dict] = []
        self.client_kwargs: list[dict] = []
        self.reply_text = '{"question": "And the number?", "gap": "no_metric", "rationale": "why"}'
        self.stop_reason = "end_turn"
        self.beta_mode = "ok"
        self.raise_next: Exception | None = None

        self.Anthropic = Anthropic
        self.APIError = APIError
        self.BadRequestError = BadRequestError
        self.AuthenticationError = AuthenticationError
        self.PermissionDeniedError = PermissionDeniedError
        self.NotFoundError = NotFoundError
        self.RateLimitError = RateLimitError
        self.APIStatusError = APIStatusError
        self.APIConnectionError = APIConnectionError
        self._Response = _Response


@pytest.fixture()
def fake_anthropic(monkeypatch: pytest.MonkeyPatch) -> _FakeAnthropicModule:
    module = _FakeAnthropicModule()
    monkeypatch.setitem(sys.modules, "anthropic", module)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    return module


def _claude_request(schema: dict | None = None) -> LLMRequest:
    return LLMRequest(
        system="You are an assessor.",
        user="Score this.",
        max_tokens=1200,
        effort="high",
        schema=schema,
    )


def test_claude_request_carries_model_thinking_effort_and_schema(fake_anthropic) -> None:
    schema = {"type": "object", "properties": {"question": {"type": "string"}}}
    provider = anthropic_provider.AnthropicProvider()
    reply = provider.complete(_claude_request(schema))

    payload = fake_anthropic.beta_calls[0]
    assert payload["model"] == DEFAULT_CLAUDE_MODEL
    assert payload["max_tokens"] == 1200
    assert payload["system"] == "You are an assessor."
    assert payload["messages"] == [{"role": "user", "content": "Score this."}]
    assert payload["thinking"] == {"type": "adaptive"}
    assert payload["output_config"]["effort"] == "high"
    assert payload["output_config"]["format"] == {"type": "json_schema", "schema": schema}
    assert reply.data == {"question": "And the number?", "gap": "no_metric", "rationale": "why"}
    assert reply.provider == "claude"


def test_refusal_fallback_is_requested_by_default(fake_anthropic) -> None:
    anthropic_provider.AnthropicProvider().complete(_claude_request())
    payload = fake_anthropic.beta_calls[0]
    assert payload["betas"] == [anthropic_provider.FALLBACK_BETA]
    assert payload["fallbacks"] == "default"
    assert not fake_anthropic.calls  # the beta endpoint served it


def test_an_sdk_without_fallbacks_is_retried_plainly(fake_anthropic) -> None:
    fake_anthropic.beta_mode = "typeerror"
    reply = anthropic_provider.AnthropicProvider().complete(_claude_request())
    assert reply.text
    assert fake_anthropic.calls, "should retry on the non-beta endpoint"
    assert "fallbacks" not in fake_anthropic.calls[0]


def test_a_server_rejecting_the_beta_is_retried_plainly(fake_anthropic) -> None:
    fake_anthropic.beta_mode = "badrequest"
    provider = anthropic_provider.AnthropicProvider()
    assert provider.complete(_claude_request()).text
    # And the rejection is remembered, so the next call skips the beta.
    provider.complete(_claude_request())
    assert len(fake_anthropic.beta_calls) == 1


def test_effort_is_omitted_for_models_without_it(fake_anthropic) -> None:
    provider = anthropic_provider.AnthropicProvider("claude-haiku-4-5")
    provider.complete(_claude_request())
    payload = fake_anthropic.beta_calls[0]
    assert "thinking" not in payload
    assert "effort" not in payload.get("output_config", {})


def test_a_refusal_is_reported_not_returned_as_content(fake_anthropic) -> None:
    fake_anthropic.stop_reason = "refusal"
    with pytest.raises(LLMFailure, match="declined"):
        anthropic_provider.AnthropicProvider().complete(_claude_request())


def test_auth_failure_is_unavailable_not_a_transient_failure(fake_anthropic) -> None:
    fake_anthropic.raise_next = fake_anthropic.AuthenticationError("nope")
    with pytest.raises(LLMUnavailable):
        anthropic_provider.AnthropicProvider().complete(_claude_request())


def test_connection_failure_is_unavailable(fake_anthropic) -> None:
    fake_anthropic.raise_next = fake_anthropic.APIConnectionError("offline")
    with pytest.raises(LLMUnavailable):
        anthropic_provider.AnthropicProvider().complete(_claude_request())


def test_rate_limit_is_a_retryable_failure(fake_anthropic) -> None:
    fake_anthropic.raise_next = fake_anthropic.RateLimitError("slow down")
    with pytest.raises(LLMFailure, match="rate limit"):
        anthropic_provider.AnthropicProvider().complete(_claude_request())


def test_empty_content_is_a_failure(fake_anthropic) -> None:
    fake_anthropic.reply_text = "   "
    with pytest.raises(LLMFailure, match="no text"):
        anthropic_provider.AnthropicProvider().complete(_claude_request())


def test_missing_sdk_is_reported_as_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "anthropic", None)
    provider = anthropic_provider.AnthropicProvider(api_key="sk-test")
    with pytest.raises(LLMUnavailable, match="not installed"):
        provider.complete(_claude_request())


def test_explicit_key_is_passed_to_the_client(fake_anthropic) -> None:
    anthropic_provider.AnthropicProvider(api_key="sk-explicit").complete(_claude_request())
    assert fake_anthropic.client_kwargs[0]["api_key"] == "sk-explicit"


def test_model_name_is_never_blank() -> None:
    assert anthropic_provider.AnthropicProvider("").model == DEFAULT_CLAUDE_MODEL
    assert anthropic_provider.resolve_model("  ") == DEFAULT_CLAUDE_MODEL
