"""Follow-up questions — the single-shot entry point.

The adaptive engine lives in `intelligence.probing`; this module stays as the
narrow, stable call used by scripts and the manual "ask a follow-up" button:
one question in, one question out, no session state required.
"""

from __future__ import annotations

from ai_interviewer.intelligence.llm.registry import AISettings, ProviderChain, build_chain, normalize_provider
from ai_interviewer.intelligence.probing import follow_up_for_answer


def generate_follow_up_question(
    original_question: str,
    transcript: str,
    language: str,
    provider: str = "Auto",
    ollama_model: str = "",
    ollama_host: str = "",
    *,
    competency_key: str = "",
    depth: int = 1,
    chain: ProviderChain | None = None,
) -> str:
    """Return one follow-up question for an answer.

    With no provider configured this is fully offline and deterministic: the
    gap the answer left open decides which question comes back.
    """
    resolved = chain if chain is not None else build_chain(
        AISettings(
            provider=normalize_provider(provider),
            ollama_model=ollama_model,
            ollama_host=ollama_host,
        )
    )
    probe = follow_up_for_answer(
        original_question,
        transcript,
        language,
        chain=resolved,
        competency_key=competency_key,
        depth=depth,
    )
    return probe.question
