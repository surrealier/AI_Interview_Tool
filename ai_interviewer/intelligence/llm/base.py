"""Provider-neutral contract for the reasoning calls the interviewer makes.

Three providers implement it — a Claude cloud provider, a local Ollama
provider, and a fully offline heuristic provider — so probing, evaluation, and
reporting are written once and run wherever the user allows.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


PROVIDER_OFFLINE = "offline"
PROVIDER_OLLAMA = "ollama"
PROVIDER_CLAUDE = "claude"

# Purposes exist so a provider can trade depth for latency: a probe is spoken
# back to a waiting candidate, a report is not.
PURPOSE_PROBE = "probe"
PURPOSE_EVALUATION = "evaluation"
PURPOSE_BLUEPRINT = "blueprint"
PURPOSE_REPORT = "report"

EFFORT_LOW = "low"
EFFORT_MEDIUM = "medium"
EFFORT_HIGH = "high"


class LLMUnavailable(RuntimeError):
    """The provider cannot run at all: not installed, not configured, offline."""


class LLMFailure(RuntimeError):
    """The provider ran and failed: transport error, refusal, unusable output."""


@dataclass(frozen=True, slots=True)
class LLMRequest:
    system: str
    user: str
    purpose: str = PURPOSE_PROBE
    max_tokens: int = 1024
    effort: str = EFFORT_MEDIUM
    # A JSON schema turns the call into a structured one; providers that
    # support constrained decoding use it, the rest fall back to parsing.
    schema: dict[str, Any] | None = None
    timeout: float = 45.0


@dataclass(frozen=True, slots=True)
class LLMReply:
    text: str
    provider: str
    model: str = ""
    data: dict[str, Any] | None = None
    latency_ms: int = 0
    note: str = ""

    @property
    def is_offline(self) -> bool:
        return self.provider == PROVIDER_OFFLINE

    def describe(self) -> str:
        if self.model:
            return f"{self.provider}:{self.model}"
        return self.provider


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    model: str

    def is_available(self) -> bool:
        ...

    def complete(self, request: LLMRequest) -> LLMReply:
        ...


@dataclass(slots=True)
class ProviderStatus:
    """What the UI shows about one provider without making a live call."""

    name: str
    available: bool
    model: str = ""
    detail: str = ""
    requires_network: bool = False
    tags: list[str] = field(default_factory=list)


# -- output parsing ----------------------------------------------------------

_FENCED = re.compile(r"```(?:json)?\s*(.+?)```", re.DOTALL | re.IGNORECASE)


def extract_json(text: str) -> dict[str, Any] | None:
    """Pull the first JSON object out of a model response.

    Structured output makes this unnecessary, but the Ollama path and older
    models still wrap JSON in prose or code fences.
    """
    value = (text or "").strip()
    if not value:
        return None

    for candidate in _json_candidates(value):
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _json_candidates(value: str) -> list[str]:
    candidates = [value]
    for match in _FENCED.findall(value):
        candidates.append(match.strip())
    start = value.find("{")
    end = value.rfind("}")
    if start != -1 and end > start:
        candidates.append(value[start : end + 1])
    return candidates


def coerce_score(value: Any, default: int = 0) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return int(round(max(0.0, min(100.0, number))))


def coerce_text(value: Any, limit: int = 400) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def coerce_text_list(value: Any, limit: int = 4, item_limit: int = 240) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, (list, tuple)):
        items = list(value)
    else:
        return []
    result: list[str] = []
    for item in items:
        text = coerce_text(item, item_limit)
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def normalize_question(text: str) -> str:
    """Trim a generated question down to one clean interrogative line."""
    value = (text or "").strip()
    if not value:
        return ""
    value = value.splitlines()[0].strip()
    value = value.strip("`").strip()
    value = value.strip('"').strip("'").strip()
    value = re.sub(r"^(?:Q\d*[.:）)]|\d+[.)])\s*", "", value).strip()
    if not value:
        return ""
    if value[-1] not in ".?!。？！":
        value = f"{value}?"
    return value
