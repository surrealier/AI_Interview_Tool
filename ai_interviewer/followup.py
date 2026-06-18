from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def generate_follow_up_question(original_question: str, transcript: str, language: str) -> str:
    answer = transcript.strip()
    if not answer:
        return _empty_answer_question(language)

    ollama_question = _generate_with_ollama(original_question, answer, language)
    if ollama_question:
        return ollama_question

    if language == "Korean":
        return _generate_korean_follow_up(original_question, answer)
    return _generate_english_follow_up(original_question, answer)


def _generate_with_ollama(original_question: str, answer: str, language: str) -> str:
    model = os.environ.get("AI_INTERVIEW_OLLAMA_MODEL", "").strip()
    if not model:
        return ""

    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    response_language = "Korean" if language == "Korean" else "English"
    prompt = (
        f"You are a professional interviewer. Generate exactly one concise follow-up question in {response_language}.\n"
        f"Original question: {original_question}\n"
        f"Candidate answer: {answer}\n"
        "The follow-up should ask for evidence, reasoning, tradeoffs, impact, or a concrete example."
    )
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{host}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return ""

    question = str(data.get("response", "")).strip().splitlines()[0].strip()
    return _normalize_question(question)


def _generate_korean_follow_up(original_question: str, answer: str) -> str:
    combined = f"{original_question} {answer}"
    if _contains_any(combined, ("갈등", "협업", "팀", "동료", "상사")):
        return "그 상황에서 상대방의 입장을 어떻게 확인했고, 최종적으로 어떤 합의를 만들었나요?"
    if _contains_any(combined, ("강점", "장점", "역량")):
        return "그 강점이 실제 업무 상황에서 성과로 이어졌던 사례를 하나 설명해 주시겠어요?"
    if _contains_any(combined, ("실패", "어려", "문제", "위기", "리스크")):
        return "그 경험에서 다시 같은 상황을 만난다면 어떤 판단이나 행동을 다르게 하시겠어요?"
    if _contains_any(combined, ("성과", "성취", "프로젝트", "개선", "결과")):
        return "말씀하신 성과에서 본인이 직접 기여한 부분과 결과를 수치나 근거로 설명해 주시겠어요?"
    if _contains_any(combined, ("지원", "직무", "회사", "입사")):
        return "그 관심이 실제 업무 역량이나 준비 과정으로 이어진 구체적인 사례가 있나요?"
    if len(answer) < 80:
        return "방금 답변하신 내용을 실제 경험을 중심으로 조금 더 구체적으로 설명해 주시겠어요?"
    return "말씀하신 경험에서 가장 어려웠던 지점과 그때의 판단 기준을 구체적으로 설명해 주시겠어요?"


def _generate_english_follow_up(original_question: str, answer: str) -> str:
    combined = f"{original_question} {answer}".lower()
    if _contains_any(combined, ("conflict", "team", "collaboration", "manager", "coworker")):
        return "How did you understand the other person's perspective, and what agreement did you reach?"
    if _contains_any(combined, ("strength", "skill", "capability")):
        return "Can you give one example where that strength led to a measurable outcome?"
    if _contains_any(combined, ("failure", "difficult", "problem", "risk", "challenge")):
        return "If you faced the same situation again, what would you do differently?"
    if _contains_any(combined, ("impact", "result", "project", "improve", "achievement")):
        return "What was your direct contribution, and how did you measure the result?"
    if _contains_any(combined, ("apply", "role", "company", "position")):
        return "How has that interest translated into concrete preparation for this role?"
    if len(answer) < 120:
        return "Could you expand on that with a specific example from your experience?"
    return "What was the hardest part of that experience, and what guided your decision?"


def _empty_answer_question(language: str) -> str:
    if language == "Korean":
        return "답변 내용을 먼저 녹음하거나 입력한 뒤, 그 내용에 대해 더 구체적으로 질문드리겠습니다."
    return "Please record or enter an answer first, and I will ask a more specific follow-up."


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _normalize_question(text: str) -> str:
    value = text.strip().strip('"').strip("'").strip()
    if not value:
        return ""
    if value[-1] not in ".?!؟。？！":
        value = f"{value}?"
    return value
