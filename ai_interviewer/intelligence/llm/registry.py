"""Provider selection and the fallback chain.

Ordering is a privacy decision, not a quality one: a local Ollama model is
tried before the cloud, and the cloud is only ever in the chain when the user
has explicitly turned it on. When no provider is available the chain is empty
and every analyzer falls back to its offline implementation, which is the
default install.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from ai_interviewer.intelligence.llm import anthropic_provider, ollama_provider
from ai_interviewer.intelligence.llm.base import (
    EFFORT_MEDIUM,
    PROVIDER_OFFLINE,
    LLMFailure,
    LLMProvider,
    LLMReply,
    LLMRequest,
    LLMUnavailable,
    ProviderStatus,
)


logger = logging.getLogger(__name__)

# Config-level names (what the user picks); the module-level PROVIDER_* ids in
# base.py are the wire names one implementation reports about itself.
AI_AUTO = "Auto"
AI_OFFLINE = "Offline"
AI_OLLAMA = "Ollama"
AI_CLAUDE = "Claude"

AI_PROVIDERS: tuple[str, ...] = (AI_OFFLINE, AI_AUTO, AI_OLLAMA, AI_CLAUDE)
DEFAULT_AI_PROVIDER = AI_OFFLINE

CLOUD_PROVIDERS: frozenset[str] = frozenset({AI_CLAUDE})


@dataclass(slots=True)
class AISettings:
    """Everything provider selection needs, lifted out of AppConfig.

    Keeping this separate means the intelligence layer can be exercised
    without a config file, and AppConfig stays the only thing that knows about
    disk layout.
    """

    provider: str = DEFAULT_AI_PROVIDER
    claude_model: str = anthropic_provider.DEFAULT_MODEL
    claude_api_key: str = ""
    ollama_model: str = ""
    ollama_host: str = ""
    effort: str = EFFORT_MEDIUM
    allow_cloud: bool = False

    @classmethod
    def from_config(cls, config: Any, api_key: str = "") -> "AISettings":
        return cls(
            provider=normalize_provider(getattr(config, "ai_provider", DEFAULT_AI_PROVIDER)),
            claude_model=anthropic_provider.resolve_model(getattr(config, "claude_model", "")),
            claude_api_key=api_key,
            ollama_model=str(getattr(config, "ollama_model", "") or ""),
            ollama_host=str(getattr(config, "ollama_host", "") or ""),
            effort=str(getattr(config, "ai_effort", EFFORT_MEDIUM) or EFFORT_MEDIUM),
            allow_cloud=bool(getattr(config, "enable_cloud_ai", False)),
        )

    def uses_cloud(self) -> bool:
        return self.allow_cloud and self.provider in (CLOUD_PROVIDERS | {AI_AUTO})


def normalize_provider(value: Any) -> str:
    candidate = str(value or "").strip()
    for name in AI_PROVIDERS:
        if candidate.lower() == name.lower():
            return name
    # Legacy configs stored the follow-up provider here ("Auto"/"Ollama").
    return DEFAULT_AI_PROVIDER


@dataclass(slots=True)
class ProviderChain:
    """Ordered providers plus the reason each unavailable one was skipped."""

    providers: list[LLMProvider] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    last_error: str = ""
    last_provider: str = ""

    @property
    def enabled(self) -> bool:
        return bool(self.providers)

    def describe(self) -> str:
        if not self.providers:
            return PROVIDER_OFFLINE
        return " → ".join(f"{item.name}:{item.model}" if item.model else item.name for item in self.providers)

    def complete(self, request: LLMRequest) -> LLMReply | None:
        """Return the first usable reply, or None to mean "use the offline path".

        A provider that is unavailable or fails is stepped over. `last_error`
        describes why the *call* failed, so it is cleared as soon as some
        provider answers; every skip is also appended to `skipped`, which keeps
        the detail for diagnostics either way.
        """
        self.last_error = ""
        for provider in self.providers:
            try:
                if not provider.is_available():
                    self._skip(provider, getattr(provider, "unavailable_reason", lambda: "not available")())
                    continue
                reply = provider.complete(request)
            except LLMUnavailable as exc:
                logger.info("Provider %s unavailable: %s", provider.name, exc)
                self._skip(provider, str(exc))
                continue
            except LLMFailure as exc:
                logger.warning("Provider %s failed: %s", provider.name, exc)
                self._skip(provider, str(exc))
                continue
            except Exception as exc:  # noqa: BLE001 - never break an interview
                logger.exception("Provider %s raised unexpectedly", provider.name)
                self._skip(provider, str(exc))
                continue
            self.last_provider = reply.describe()
            self.last_error = ""
            return reply
        return None

    def _skip(self, provider: LLMProvider, reason: str) -> None:
        self.skipped.append(f"{provider.name}: {reason}")
        self.last_error = reason


def build_chain(settings: AISettings) -> ProviderChain:
    chain = ProviderChain()
    provider = normalize_provider(settings.provider)

    if provider == AI_OFFLINE:
        return chain

    if provider in (AI_AUTO, AI_OLLAMA):
        local = ollama_provider.OllamaProvider(settings.ollama_model, settings.ollama_host)
        if local.is_available():
            chain.providers.append(local)
        else:
            chain.skipped.append(f"{local.name}: {local.unavailable_reason()}")

    if provider in (AI_AUTO, AI_CLAUDE):
        if not settings.allow_cloud:
            chain.skipped.append("claude: cloud analysis is turned off")
        else:
            cloud = anthropic_provider.AnthropicProvider(
                settings.claude_model,
                settings.claude_api_key,
            )
            if cloud.is_available():
                chain.providers.append(cloud)
            else:
                chain.skipped.append(f"{cloud.name}: {cloud.unavailable_reason()}")

    return chain


def provider_statuses(settings: AISettings) -> list[ProviderStatus]:
    """Non-calling availability snapshot for the settings UI and diagnostics."""
    local = ollama_provider.OllamaProvider(settings.ollama_model, settings.ollama_host)
    cloud = anthropic_provider.AnthropicProvider(settings.claude_model, settings.claude_api_key)
    return [
        ProviderStatus(
            name=AI_OFFLINE,
            available=True,
            model="rule-based",
            detail="Always available. No data leaves this machine.",
            tags=["offline"],
        ),
        ProviderStatus(
            name=AI_OLLAMA,
            available=local.is_available(),
            model=local.model,
            detail=local.unavailable_reason() or f"Local daemon at {local.host}",
            tags=["local"],
        ),
        ProviderStatus(
            name=AI_CLAUDE,
            available=settings.allow_cloud and cloud.is_available(),
            model=cloud.model,
            detail=(
                "Cloud analysis is turned off"
                if not settings.allow_cloud
                else (cloud.unavailable_reason() or "Ready")
            ),
            requires_network=True,
            tags=["cloud"],
        ),
    ]


def chain_for_config(config: Any, api_key: str = "") -> ProviderChain:
    return build_chain(AISettings.from_config(config, api_key))


def sequence_of(providers: Sequence[LLMProvider]) -> ProviderChain:
    """Build a chain from explicit providers; used by tests and diagnostics."""
    return ProviderChain(providers=list(providers))
