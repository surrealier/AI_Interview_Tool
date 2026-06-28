from __future__ import annotations


DEFAULT_KOREAN_QUESTIONS = [
    "자기소개를 해주세요.",
    "이 직무에 지원한 이유를 말씀해 주세요.",
    "우리 회사에 관심을 갖게 된 계기는 무엇인가요?",
    "본인의 가장 큰 강점은 무엇인가요?",
    "본인의 약점과 이를 개선하기 위해 노력한 점을 말씀해 주세요.",
    "최근 가장 큰 성취 경험을 설명해 주세요.",
    "실패했던 경험과 그 경험에서 배운 점을 말씀해 주세요.",
    "팀으로 일하면서 갈등을 겪었던 경험이 있나요?",
    "갈등 상황에서 본인은 보통 어떤 방식으로 해결하나요?",
    "빠듯한 일정이나 압박이 있는 상황을 어떻게 관리하나요?",
    "피드백을 받았을 때 어떻게 받아들이고 적용하나요?",
    "새로운 환경에 적응했던 경험을 말씀해 주세요.",
    "본인이 중요하게 생각하는 직업적 가치는 무엇인가요?",
    "리더십을 발휘했던 경험이 있다면 설명해 주세요.",
    "다른 사람을 설득했던 경험을 말씀해 주세요.",
    "업무 우선순위가 충돌할 때 어떻게 판단하나요?",
    "윤리적으로 고민되는 상황을 겪은 적이 있다면 어떻게 대응했나요?",
    "입사 후 1년 동안 어떤 성과를 내고 싶나요?",
    "3년 뒤 본인은 어떤 모습이길 기대하나요?",
    "마지막으로 본인을 채용해야 하는 이유를 말씀해 주세요.",
]


DEFAULT_ENGLISH_QUESTIONS = [
    "Please introduce yourself.",
    "Why are you applying for this role?",
    "What made you interested in our company?",
    "What is your greatest strength?",
    "What is one weakness you are working to improve?",
    "Tell me about a recent achievement you are proud of.",
    "Tell me about a failure and what you learned from it.",
    "Have you experienced conflict while working on a team?",
    "How do you usually resolve conflicts at work?",
    "How do you manage tight deadlines or pressure?",
    "How do you receive and apply feedback?",
    "Tell me about a time you adapted to a new environment.",
    "What professional values are most important to you?",
    "Describe a time when you showed leadership.",
    "Tell me about a time you persuaded someone.",
    "How do you decide when priorities conflict?",
    "How have you handled an ethical dilemma?",
    "What impact would you like to make in your first year here?",
    "Where do you see yourself in three years?",
    "Why should we hire you?",
]


def default_questions_text() -> str:
    korean = [f"{index}. {question}" for index, question in enumerate(DEFAULT_KOREAN_QUESTIONS, start=1)]
    english = [f"{index}. {question}" for index, question in enumerate(DEFAULT_ENGLISH_QUESTIONS, start=1)]
    return "\n".join([*korean, *english])
