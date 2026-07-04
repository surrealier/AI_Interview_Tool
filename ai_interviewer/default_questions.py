from __future__ import annotations

from collections.abc import Mapping


KOREAN_MODE = "Korean"
ENGLISH_MODE = "English"
DEFAULT_QUESTION_SET_NAME = "기본 인성 면접"
INTERVIEW_TYPE_HR = "hr"
INTERVIEW_TYPE_STAR = "star"
INTERVIEW_TYPE_ROLE = "role"
INTERVIEW_TYPE_TECHNICAL = "technical"
INTERVIEW_TYPES = (INTERVIEW_TYPE_HR, INTERVIEW_TYPE_STAR, INTERVIEW_TYPE_ROLE, INTERVIEW_TYPE_TECHNICAL)


QUESTION_SETS: Mapping[str, Mapping[str, list[str]]] = {
    KOREAN_MODE: {
        "기본 인성 면접": [
            "자기소개를 1분 이내로 해주세요.",
            "지원하신 직무에 관심을 갖게 된 계기는 무엇인가요?",
            "우리 회사에 지원한 이유를 구체적으로 말씀해 주세요.",
            "본인의 가장 큰 강점과 실제 사례를 설명해 주세요.",
            "본인의 약점과 이를 개선하기 위해 해온 노력을 말씀해 주세요.",
            "최근 가장 의미 있었던 성취 경험을 설명해 주세요.",
            "실패했던 경험과 그 경험에서 배운 점을 말씀해 주세요.",
            "팀으로 일하면서 갈등을 겪었던 경험이 있나요?",
            "갈등 상황에서 본인은 어떤 방식으로 문제를 해결했나요?",
            "압박감이 큰 상황에서 일정과 품질을 어떻게 관리하나요?",
            "피드백을 받았을 때 어떻게 받아들이고 적용하나요?",
            "새로운 환경에 빠르게 적응했던 경험을 말씀해 주세요.",
            "본인이 중요하게 생각하는 직업적 가치는 무엇인가요?",
            "리더십을 발휘했던 경험을 구체적으로 설명해 주세요.",
            "다른 사람을 설득했던 경험과 결과를 말씀해 주세요.",
            "업무 우선순위가 충돌할 때 어떤 기준으로 판단하나요?",
            "윤리적으로 고민되는 상황을 겪었다면 어떻게 대응했나요?",
            "입사 후 첫 6개월 동안 어떤 성과를 만들고 싶나요?",
            "3년 뒤 본인은 어떤 모습이길 기대하나요?",
            "마지막으로 본인을 채용해야 하는 이유를 말씀해 주세요.",
        ],
        "경험 기반 STAR": [
            "목표가 명확했지만 실행이 어려웠던 상황을 설명해 주세요.",
            "문제를 발견하고 주도적으로 개선했던 경험을 말씀해 주세요.",
            "데이터나 근거를 활용해 의사결정을 바꾼 경험이 있나요?",
            "짧은 기간 안에 새로운 역량을 익혀야 했던 경험을 설명해 주세요.",
            "실패 가능성이 높은 일을 끝까지 추진했던 경험을 말씀해 주세요.",
            "팀원의 반대가 있었지만 설득해서 방향을 맞춘 경험이 있나요?",
            "고객이나 사용자 관점에서 문제를 다시 정의했던 경험을 설명해 주세요.",
            "예상치 못한 장애가 발생했을 때 어떻게 대응했나요?",
            "본인의 실수로 문제가 생겼던 경험과 후속 조치를 말씀해 주세요.",
            "성과가 잘 드러나지 않는 일을 꾸준히 해낸 경험이 있나요?",
            "상충하는 이해관계를 조율했던 경험을 설명해 주세요.",
            "주어진 역할을 넘어 추가로 기여했던 경험을 말씀해 주세요.",
            "피드백 이후 결과가 실제로 좋아졌던 사례가 있나요?",
            "팀의 기준이나 프로세스를 개선했던 경험을 설명해 주세요.",
            "불확실한 상황에서 우선순위를 정했던 경험을 말씀해 주세요.",
            "협업 도구나 문서화를 통해 팀 효율을 높인 경험이 있나요?",
            "책임 소재가 모호한 문제를 맡아 해결했던 경험을 설명해 주세요.",
            "성과를 수치나 근거로 입증할 수 있는 경험을 말씀해 주세요.",
            "가장 어렵게 배운 업무상 교훈은 무엇인가요?",
            "방금 말씀하신 경험을 다시 한다면 무엇을 다르게 하시겠어요?",
        ],
        "직무 적합성": [
            "이 직무의 핵심 역량은 무엇이라고 생각하나요?",
            "현재 보유한 역량 중 이 직무에 가장 직접적으로 연결되는 것은 무엇인가요?",
            "부족한 역량을 보완하기 위해 어떤 계획을 갖고 있나요?",
            "우리 회사의 제품이나 서비스 중 인상 깊었던 점을 말씀해 주세요.",
            "경쟁사와 비교했을 때 우리 회사가 개선해야 할 점은 무엇이라고 보나요?",
            "입사 후 가장 먼저 파악해야 할 업무 정보는 무엇이라고 생각하나요?",
            "혼자 깊게 몰입하는 일과 여러 사람과 조율하는 일 중 어떤 방식에 강한가요?",
            "업무 성과를 측정할 때 어떤 지표를 중요하게 보나요?",
            "전문성을 유지하기 위해 평소 어떤 방식으로 학습하나요?",
            "최근 관심 있게 본 산업 변화나 기술 변화가 있나요?",
            "지원 직무에서 반복 업무와 창의 업무의 균형을 어떻게 보나요?",
            "상사가 모호한 지시를 했을 때 어떻게 명확히 하겠어요?",
            "업무 품질과 속도가 충돌할 때 어떤 기준으로 결정하나요?",
            "본인의 커뮤니케이션 방식은 어떤 편인가요?",
            "협업 과정에서 문서화가 왜 중요하다고 생각하나요?",
            "이 직무에서 본인이 빠르게 성과를 낼 수 있는 이유는 무엇인가요?",
            "업무를 맡았을 때 리스크를 먼저 찾는 편인가요, 실행부터 하는 편인가요?",
            "본인이 선호하는 피드백 방식과 이유를 말씀해 주세요.",
            "입사 후 온보딩 기간에 가장 집중하고 싶은 부분은 무엇인가요?",
            "이 직무를 통해 장기적으로 어떤 전문가가 되고 싶나요?",
        ],
        "기술 면접": [
            "최근 진행한 기술 프로젝트의 목표와 본인의 역할을 설명해 주세요.",
            "해당 프로젝트에서 가장 중요한 기술적 의사결정은 무엇이었나요?",
            "성능 병목을 발견하고 개선했던 경험을 말씀해 주세요.",
            "장애나 버그의 원인을 추적할 때 어떤 순서로 접근하나요?",
            "코드 품질을 유지하기 위해 어떤 기준과 도구를 사용하나요?",
            "테스트를 작성할 때 우선순위를 어떻게 정하나요?",
            "기술 부채를 발견했을 때 어떻게 설득하고 해결하나요?",
            "API나 모듈 인터페이스를 설계할 때 가장 중요하게 보는 점은 무엇인가요?",
            "데이터 모델이나 스키마를 바꿔야 할 때 어떤 리스크를 점검하나요?",
            "보안이나 개인정보 관점에서 개발 중 주의하는 부분은 무엇인가요?",
            "새로운 기술을 도입할 때 어떤 기준으로 검토하나요?",
            "운영 환경에서 재현이 어려운 문제를 어떻게 해결했나요?",
            "로그, 메트릭, 알림을 설계할 때 중요하게 보는 점은 무엇인가요?",
            "동시성이나 비동기 처리 문제를 다뤄본 경험을 설명해 주세요.",
            "대규모 코드베이스에서 변경 범위를 안전하게 줄이는 방법은 무엇인가요?",
            "리뷰에서 의견이 갈릴 때 어떤 기준으로 결론을 내리나요?",
            "사용자 경험과 기술 구현 난이도가 충돌할 때 어떻게 판단하나요?",
            "최근 학습한 기술 중 실제 업무에 적용할 만한 것을 설명해 주세요.",
            "본인의 기술적 강점과 보완해야 할 점을 말씀해 주세요.",
            "지금까지 만든 것 중 기술적으로 가장 자랑스러운 결과물은 무엇인가요?",
        ],
    },
    ENGLISH_MODE: {
        "Core HR Interview": [
            "Please introduce yourself in one minute.",
            "What made you interested in this role?",
            "Why are you applying to our company?",
            "What is your greatest strength, and can you give an example?",
            "What is one weakness you are actively working to improve?",
            "Tell me about a recent achievement that was meaningful to you.",
            "Tell me about a failure and what you learned from it.",
            "Have you experienced conflict while working on a team?",
            "How did you handle that conflict?",
            "How do you manage pressure when deadlines are tight?",
            "How do you receive and apply feedback?",
            "Tell me about a time you adapted quickly to a new environment.",
            "What professional values are most important to you?",
            "Describe a time when you showed leadership.",
            "Tell me about a time you persuaded someone.",
            "How do you decide when priorities conflict?",
            "How have you handled an ethical dilemma?",
            "What impact would you like to make in your first six months?",
            "Where do you see yourself in three years?",
            "Why should we hire you?",
        ],
        "Behavioral STAR": [
            "Tell me about a goal that was clear but difficult to execute.",
            "Describe a time when you identified and solved a problem proactively.",
            "Tell me about a time data or evidence changed your decision.",
            "Describe a time when you had to learn a new skill quickly.",
            "Tell me about a time you pushed through a high-risk task.",
            "Describe a time you aligned a team despite disagreement.",
            "Tell me about a time you redefined a problem from a user or customer perspective.",
            "How did you respond to an unexpected blocker?",
            "Tell me about a mistake you made and how you handled the follow-up.",
            "Describe a time you kept working on something whose impact was not immediately visible.",
            "Tell me about a time you balanced competing stakeholder needs.",
            "Describe a time you contributed beyond your assigned role.",
            "Tell me about a time feedback led to a better result.",
            "Describe a time you improved a team process or standard.",
            "Tell me about a time you prioritized work under uncertainty.",
            "How have you used documentation or tools to improve collaboration?",
            "Tell me about a problem you solved when ownership was unclear.",
            "Describe an achievement you can support with measurable evidence.",
            "What is the hardest professional lesson you have learned?",
            "If you repeated that experience, what would you do differently?",
        ],
        "Role Fit": [
            "What do you think are the core capabilities for this role?",
            "Which of your current skills maps most directly to this role?",
            "What skill gap are you currently working to close?",
            "What stood out to you about our product or service?",
            "Compared with competitors, where do you think we could improve?",
            "What information would you need to learn first after joining?",
            "Do you work better in deep individual work or in cross-functional coordination?",
            "What metrics would you use to judge success in this role?",
            "How do you keep your professional knowledge current?",
            "What industry or technology trend have you been following recently?",
            "How do you think this role balances repetitive execution and creative problem solving?",
            "What would you do if your manager gave you an ambiguous request?",
            "How do you decide when speed and quality conflict?",
            "How would you describe your communication style?",
            "Why is documentation important in collaboration?",
            "Why can you ramp up quickly in this role?",
            "When you receive a task, do you first look for risks or start execution?",
            "What type of feedback helps you perform best?",
            "What would you focus on during your onboarding period?",
            "What kind of professional do you want to become through this role?",
        ],
        "Technical Interview": [
            "Describe a recent technical project and your role in it.",
            "What was the most important technical decision in that project?",
            "Tell me about a time you found and improved a performance bottleneck.",
            "How do you investigate the root cause of a bug or incident?",
            "What standards or tools do you use to maintain code quality?",
            "How do you prioritize what tests to write?",
            "How do you identify and address technical debt?",
            "What matters most when designing an API or module interface?",
            "What risks do you check before changing a data model or schema?",
            "What security or privacy concerns do you consider while building software?",
            "How do you evaluate whether to introduce a new technology?",
            "Tell me about a production issue that was hard to reproduce.",
            "What do you consider when designing logs, metrics, and alerts?",
            "Describe your experience with concurrency or asynchronous processing.",
            "How do you reduce the risk of changes in a large codebase?",
            "How do you resolve disagreements during code review?",
            "How do you balance user experience against implementation complexity?",
            "What recent technology have you learned that could be useful at work?",
            "What are your technical strengths and areas to improve?",
            "What technical work are you most proud of?",
        ],
    },
}


QUESTION_MODES = (KOREAN_MODE, ENGLISH_MODE)

INTERVIEW_TYPE_LABELS: Mapping[str, Mapping[str, str]] = {
    KOREAN_MODE: {
        INTERVIEW_TYPE_HR: "인성/HR",
        INTERVIEW_TYPE_STAR: "경험 STAR",
        INTERVIEW_TYPE_ROLE: "직무 적합성",
        INTERVIEW_TYPE_TECHNICAL: "기술 면접",
    },
    ENGLISH_MODE: {
        INTERVIEW_TYPE_HR: "HR Interview",
        INTERVIEW_TYPE_STAR: "Behavioral STAR",
        INTERVIEW_TYPE_ROLE: "Role Fit",
        INTERVIEW_TYPE_TECHNICAL: "Technical Interview",
    },
}

INTERVIEW_TYPE_TO_SET: Mapping[str, Mapping[str, str]] = {
    KOREAN_MODE: {
        INTERVIEW_TYPE_HR: "기본 인성 면접",
        INTERVIEW_TYPE_STAR: "경험 기반 STAR",
        INTERVIEW_TYPE_ROLE: "직무 적합성",
        INTERVIEW_TYPE_TECHNICAL: "기술 면접",
    },
    ENGLISH_MODE: {
        INTERVIEW_TYPE_HR: "Core HR Interview",
        INTERVIEW_TYPE_STAR: "Behavioral STAR",
        INTERVIEW_TYPE_ROLE: "Role Fit",
        INTERVIEW_TYPE_TECHNICAL: "Technical Interview",
    },
}


def question_set_names(language: str) -> tuple[str, ...]:
    return tuple(QUESTION_SETS.get(language, QUESTION_SETS[KOREAN_MODE]).keys())


def default_question_set_name(language: str) -> str:
    return question_set_names(language)[0]


def interview_type_label(language: str, interview_type: str) -> str:
    labels = INTERVIEW_TYPE_LABELS.get(language, INTERVIEW_TYPE_LABELS[KOREAN_MODE])
    return labels.get(interview_type, labels[INTERVIEW_TYPE_HR])


def question_set_for_interview_type(language: str, interview_type: str) -> str:
    mapping = INTERVIEW_TYPE_TO_SET.get(language, INTERVIEW_TYPE_TO_SET[KOREAN_MODE])
    return mapping.get(interview_type, mapping[INTERVIEW_TYPE_HR])


def interview_type_options(language: str) -> tuple[tuple[str, str], ...]:
    return tuple((interview_type, interview_type_label(language, interview_type)) for interview_type in INTERVIEW_TYPES)


def questions_for_set(language: str, set_name: str | None = None) -> list[str]:
    sets = QUESTION_SETS.get(language, QUESTION_SETS[KOREAN_MODE])
    selected_name = set_name if set_name in sets else next(iter(sets))
    return list(sets[selected_name])


def questions_text(language: str, set_name: str | None = None) -> str:
    questions = questions_for_set(language, set_name)
    return "\n".join(f"{index}. {question}" for index, question in enumerate(questions, start=1))


def default_questions_text(language: str = KOREAN_MODE, set_name: str | None = None) -> str:
    return questions_text(language, set_name)
