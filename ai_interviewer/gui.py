from __future__ import annotations

import csv
import os
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ai_interviewer.config import (
    AppConfig,
    DEFAULT_MODEL_ID,
    LARGE_MODEL_ID,
    QWEN_BACKEND,
    SUPPORTED_TTS_BACKENDS,
    WINDOWS_SAPI_BACKEND,
)
from ai_interviewer.engine import InterviewEngine
from ai_interviewer.followup import generate_follow_up_question
from ai_interviewer.question_parser import detect_language, parse_questions
from ai_interviewer.stt import MicrophoneRecorder, STTError, WhisperTranscriber
from ai_interviewer.tts.qwen_provider import QwenTTSProvider
from ai_interviewer.video_player import InterviewerVideoPlayer


DEFAULT_QUESTIONS = """1. 자기소개를 해주세요.
2. 이 직무에 지원한 이유를 말씀해 주세요.
3. 우리 회사에 관심을 갖게 된 계기는 무엇인가요?
4. 본인의 가장 큰 강점은 무엇인가요?
5. 본인의 약점과 이를 개선하기 위해 노력한 점을 말씀해 주세요.
6. 최근 가장 큰 성취 경험을 설명해 주세요.
7. 실패했던 경험과 그 경험에서 배운 점을 말씀해 주세요.
8. 팀으로 일하면서 갈등을 겪었던 경험이 있나요?
9. 갈등 상황에서 본인은 보통 어떤 방식으로 해결하나요?
10. 빠듯한 일정이나 압박이 있는 상황을 어떻게 관리하나요?
11. 피드백을 받았을 때 어떻게 받아들이고 적용하나요?
12. 새로운 환경에 적응했던 경험을 말씀해 주세요.
13. 본인이 중요하게 생각하는 직업적 가치는 무엇인가요?
14. 리더십을 발휘했던 경험이 있다면 설명해 주세요.
15. 다른 사람을 설득했던 경험을 말씀해 주세요.
16. 업무 우선순위가 충돌할 때 어떻게 판단하나요?
17. 윤리적으로 고민되는 상황을 겪은 적이 있다면 어떻게 대응했나요?
18. 입사 후 1년 동안 어떤 성과를 내고 싶나요?
19. 3년 뒤 본인은 어떤 모습이길 기대하나요?
20. 마지막으로 본인을 채용해야 하는 이유를 말씀해 주세요.
1. Please introduce yourself.
2. Why are you applying for this role?
3. What made you interested in our company?
4. What is your greatest strength?
5. What is one weakness you are working to improve?
6. Tell me about a recent achievement you are proud of.
7. Tell me about a failure and what you learned from it.
8. Have you experienced conflict while working on a team?
9. How do you usually resolve conflicts at work?
10. How do you manage tight deadlines or pressure?
11. How do you receive and apply feedback?
12. Tell me about a time you adapted to a new environment.
13. What professional values are most important to you?
14. Describe a time when you showed leadership.
15. Tell me about a time you persuaded someone.
16. How do you decide when priorities conflict?
17. How have you handled an ethical dilemma?
18. What impact would you like to make in your first year here?
19. Where do you see yourself in three years?
20. Why should we hire you?"""


class InterviewApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AI Interviewer")
        self.geometry("1280x860")
        self.minsize(1120, 760)

        self.config_model = AppConfig()
        self.config_model.ensure_directories()
        self.config_model.model_id = self.config_model.preferred_model_id()
        self.engine: InterviewEngine | None = None
        self.provider: QwenTTSProvider | None = None
        self.preload_provider: QwenTTSProvider | None = None
        self.recorder = MicrophoneRecorder()
        self.transcriber = WhisperTranscriber(self.config_model)
        self.recording = False
        self.recording_path: Path | None = None
        self.preload_running = False
        self.tts_token = 0
        self.tts_running = False

        self._build_variables()
        self._build_ui()
        self._set_session_controls(False)
        self.after(500, self._preload_tts_model)
        self.after(250, self._update_timers)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_variables(self) -> None:
        self.tts_backend_var = tk.StringVar(value=QWEN_BACKEND)
        self.model_var = tk.StringVar(value=self.config_model.model_id)
        self.model_root_var = tk.StringVar(value=str(self.config_model.model_root))
        self.video_path_var = tk.StringVar(value=str(self.config_model.video_path))
        self.stt_model_var = tk.StringVar(value=self.config_model.stt_model_size)
        self.language_var = tk.StringVar(value="Auto")
        self.korean_speaker_var = tk.StringVar(value="Sohee")
        self.english_speaker_var = tk.StringVar(value="Ryan")
        self.status_var = tk.StringVar(value="질문을 입력하거나 파일을 불러오세요.")
        self.progress_var = tk.StringVar(value="0 / 0")
        self.answer_timer_var = tk.StringVar(value="00:00")
        self.total_timer_var = tk.StringVar(value="00:00")
        self.current_question_var = tk.StringVar(value="세션이 시작되지 않았습니다.")

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        root = ttk.Frame(self, padding=12)
        root.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=3)
        root.columnconfigure(1, weight=2)
        root.rowconfigure(1, weight=1)

        header = ttk.Frame(root)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        header.columnconfigure(1, weight=1)
        ttk.Label(header, text="AI 면접관", font=("Segoe UI", 18, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, textvariable=self.status_var).grid(row=0, column=1, sticky="e")

        input_frame = ttk.LabelFrame(root, text="질문 목록", padding=10)
        input_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        input_frame.columnconfigure(0, weight=1)
        input_frame.rowconfigure(0, weight=1)

        self.question_text = tk.Text(input_frame, wrap="word", undo=True, height=20)
        self.question_text.grid(row=0, column=0, sticky="nsew")
        text_scroll = ttk.Scrollbar(input_frame, orient="vertical", command=self.question_text.yview)
        text_scroll.grid(row=0, column=1, sticky="ns")
        self.question_text.configure(yscrollcommand=text_scroll.set)
        self.question_text.insert("1.0", DEFAULT_QUESTIONS)

        input_buttons = ttk.Frame(input_frame)
        input_buttons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(input_buttons, text="파일 불러오기", command=self._load_questions_file).pack(side="left")
        ttk.Button(input_buttons, text="세션 시작", command=self._start_session).pack(side="left", padx=6)

        settings = ttk.LabelFrame(root, text="TTS 설정", padding=10)
        settings.grid(row=2, column=0, sticky="ew", padx=(0, 8), pady=(8, 0))
        settings.columnconfigure(1, weight=1)
        ttk.Label(settings, text="TTS 엔진").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            settings,
            textvariable=self.tts_backend_var,
            values=SUPPORTED_TTS_BACKENDS,
            state="readonly",
        ).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Label(settings, text="모델").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(
            settings,
            textvariable=self.model_var,
            values=(DEFAULT_MODEL_ID, LARGE_MODEL_ID),
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", padx=6, pady=(6, 0))
        ttk.Label(settings, text="모델 폴더").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(settings, textvariable=self.model_root_var).grid(row=2, column=1, sticky="ew", padx=6, pady=(6, 0))
        ttk.Button(settings, text="찾기", command=self._choose_model_root).grid(row=2, column=2, pady=(6, 0))
        ttk.Label(settings, text="언어").grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(
            settings,
            textvariable=self.language_var,
            values=("Auto", "Korean", "English"),
            state="readonly",
            width=12,
        ).grid(row=3, column=1, sticky="w", padx=6, pady=(6, 0))
        ttk.Label(settings, text="한국어 화자").grid(row=4, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(settings, textvariable=self.korean_speaker_var, width=16).grid(
            row=4, column=1, sticky="w", padx=6, pady=(6, 0)
        )
        ttk.Label(settings, text="영어 화자").grid(row=5, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(settings, textvariable=self.english_speaker_var, width=16).grid(
            row=5, column=1, sticky="w", padx=6, pady=(6, 0)
        )
        ttk.Label(settings, text="영상 파일").grid(row=6, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(settings, textvariable=self.video_path_var).grid(row=6, column=1, sticky="ew", padx=6, pady=(6, 0))
        ttk.Button(settings, text="찾기", command=self._choose_video_file).grid(row=6, column=2, pady=(6, 0))
        ttk.Label(settings, text="STT 모델").grid(row=7, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(
            settings,
            textvariable=self.stt_model_var,
            values=("tiny", "base", "small", "medium", "large-v3"),
            state="readonly",
            width=12,
        ).grid(row=7, column=1, sticky="w", padx=6, pady=(6, 0))

        session_frame = ttk.LabelFrame(root, text="면접 진행", padding=10)
        session_frame.grid(row=1, column=1, rowspan=2, sticky="nsew")
        session_frame.columnconfigure(0, weight=1)
        session_frame.rowconfigure(3, weight=1)

        video_box = ttk.LabelFrame(session_frame, text="면접관 영상", padding=8)
        video_box.grid(row=0, column=0, sticky="ew")
        video_box.columnconfigure(0, weight=1)
        self.video_player = InterviewerVideoPlayer(video_box, width=420, height=236)
        self.video_player.widget.grid(row=0, column=0, sticky="ew")
        self.video_player.set_video_path(self.config_model.video_path)

        info = ttk.Frame(session_frame)
        info.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        info.columnconfigure(1, weight=1)
        ttk.Label(info, text="진행").grid(row=0, column=0, sticky="w")
        ttk.Label(info, textvariable=self.progress_var, font=("Segoe UI", 12, "bold")).grid(
            row=0, column=1, sticky="e"
        )
        ttk.Label(info, text="답변 시간").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Label(info, textvariable=self.answer_timer_var, font=("Consolas", 14, "bold")).grid(
            row=1, column=1, sticky="e", pady=(6, 0)
        )
        ttk.Label(info, text="전체 시간").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Label(info, textvariable=self.total_timer_var, font=("Consolas", 14, "bold")).grid(
            row=2, column=1, sticky="e", pady=(6, 0)
        )

        question_box = ttk.LabelFrame(session_frame, text="현재 질문", padding=10)
        question_box.grid(row=2, column=0, sticky="ew", pady=10)
        question_box.columnconfigure(0, weight=1)
        ttk.Label(
            question_box,
            textvariable=self.current_question_var,
            wraplength=360,
            justify="left",
            font=("Segoe UI", 13),
        ).grid(row=0, column=0, sticky="ew")

        detail_tabs = ttk.Notebook(session_frame)
        detail_tabs.grid(row=3, column=0, sticky="nsew")
        memo_box = ttk.Frame(detail_tabs, padding=8)
        transcript_box = ttk.Frame(detail_tabs, padding=8)
        followup_box = ttk.Frame(detail_tabs, padding=8)
        for box in (memo_box, transcript_box, followup_box):
            box.columnconfigure(0, weight=1)
            box.rowconfigure(0, weight=1)
        self.memo_text = tk.Text(memo_box, wrap="word", height=8)
        self.memo_text.grid(row=0, column=0, sticky="nsew")
        self.transcript_text = tk.Text(transcript_box, wrap="word", height=8)
        self.transcript_text.grid(row=0, column=0, sticky="nsew")
        self.followup_text = tk.Text(followup_box, wrap="word", height=8)
        self.followup_text.grid(row=0, column=0, sticky="nsew")
        detail_tabs.add(memo_box, text="메모")
        detail_tabs.add(transcript_box, text="답변 STT")
        detail_tabs.add(followup_box, text="꼬리질문")

        controls = ttk.Frame(session_frame)
        controls.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        for index in range(4):
            controls.columnconfigure(index, weight=1)

        self.prev_button = ttk.Button(controls, text="이전", command=self._previous_question)
        self.next_button = ttk.Button(controls, text="다음", command=self._next_question)
        self.repeat_button = ttk.Button(controls, text="다시 듣기", command=lambda: self._speak_current(repeat=True))
        self.stop_button = ttk.Button(controls, text="TTS 중지", command=self._stop_tts)
        self.restart_button = ttk.Button(controls, text="다시하기", command=self._restart_session)
        self.open_folder_button = ttk.Button(controls, text="저장 폴더", command=self._open_session_folder)
        self.sound_test_button = ttk.Button(controls, text="소리 테스트", command=self._test_system_sound)
        self.diagnostics_button = ttk.Button(controls, text="TTS 진단", command=self._diagnose_tts)
        self.record_button = ttk.Button(controls, text="녹음 시작", command=self._start_recording)
        self.stop_record_button = ttk.Button(controls, text="녹음 중지 + STT", command=self._stop_recording_and_transcribe)
        self.followup_button = ttk.Button(controls, text="꼬리질문 생성", command=self._generate_follow_up)
        self.followup_speak_button = ttk.Button(controls, text="꼬리질문 듣기", command=self._speak_follow_up)

        self.prev_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.next_button.grid(row=0, column=1, sticky="ew", padx=4)
        self.repeat_button.grid(row=0, column=2, sticky="ew", padx=4)
        self.stop_button.grid(row=0, column=3, sticky="ew", padx=(4, 0))
        self.restart_button.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0), padx=(0, 4))
        self.open_folder_button.grid(row=1, column=2, columnspan=2, sticky="ew", pady=(6, 0), padx=(4, 0))
        self.sound_test_button.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0), padx=(0, 4))
        self.diagnostics_button.grid(row=2, column=2, columnspan=2, sticky="ew", pady=(6, 0), padx=(4, 0))
        self.record_button.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0), padx=(0, 4))
        self.stop_record_button.grid(row=3, column=2, columnspan=2, sticky="ew", pady=(6, 0), padx=(4, 0))
        self.followup_button.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0), padx=(0, 4))
        self.followup_speak_button.grid(row=4, column=2, columnspan=2, sticky="ew", pady=(6, 0), padx=(4, 0))

    def _set_session_controls(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in (
            self.prev_button,
            self.next_button,
            self.repeat_button,
            self.stop_button,
            self.restart_button,
            self.open_folder_button,
            self.record_button,
            self.followup_button,
            self.followup_speak_button,
        ):
            button.configure(state=state)
        self.stop_record_button.configure(state="normal" if self.recording else "disabled")
        self.sound_test_button.configure(state="normal")
        self.diagnostics_button.configure(state="normal")

    def _load_questions_file(self) -> None:
        path = filedialog.askopenfilename(
            title="질문 파일 선택",
            filetypes=(("Text or CSV", "*.txt *.csv"), ("All files", "*.*")),
        )
        if not path:
            return
        content = self._read_question_file(Path(path))
        self.question_text.delete("1.0", "end")
        self.question_text.insert("1.0", content)
        self.status_var.set(f"파일을 불러왔습니다: {Path(path).name}")

    def _read_question_file(self, path: Path) -> str:
        if path.suffix.lower() != ".csv":
            return path.read_text(encoding="utf-8-sig")
        rows: list[str] = []
        with path.open("r", newline="", encoding="utf-8-sig") as file:
            reader = csv.reader(file)
            for row in reader:
                if row and row[0].strip():
                    rows.append(row[0].strip())
        return "\n".join(rows)

    def _choose_model_root(self) -> None:
        path = filedialog.askdirectory(title="models 폴더 선택", initialdir=self.model_root_var.get())
        if path:
            self.model_root_var.set(path)
            self.config_model.model_root = Path(path).expanduser()
            self.model_var.set(self.config_model.preferred_model_id())
            self.provider = None
            if self.engine is None:
                self._preload_tts_model()

    def _choose_video_file(self) -> None:
        path = filedialog.askopenfilename(
            title="면접관 영상 파일 선택",
            filetypes=(("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")),
        )
        if path:
            self.video_path_var.set(path)
            self.config_model.video_path = Path(path).expanduser()
            self.video_player.set_video_path(self.config_model.video_path)

    def _start_session(self) -> None:
        questions = parse_questions(self.question_text.get("1.0", "end"))
        if not questions:
            messagebox.showwarning("질문 없음", "질문을 한 개 이상 입력하세요.")
            return

        self._apply_config_from_ui()
        self.engine = InterviewEngine(questions=questions, sessions_root=self.config_model.sessions_root)
        self.provider = QwenTTSProvider(self.config_model, self.engine.session.audio_cache_dir)
        self._set_session_controls(True)
        self._render_current_question()
        self.status_var.set("세션을 시작했습니다.")
        self._speak_current(repeat=False)

    def _apply_config_from_ui(self) -> None:
        self.config_model.model_id = self.model_var.get()
        self.config_model.tts_backend = self.tts_backend_var.get()
        self.config_model.model_root = Path(self.model_root_var.get()).expanduser()
        self.config_model.video_path = Path(self.video_path_var.get()).expanduser()
        self.config_model.default_language = self.language_var.get()
        self.config_model.korean_speaker = self.korean_speaker_var.get().strip() or "Sohee"
        self.config_model.english_speaker = self.english_speaker_var.get().strip() or "Ryan"
        self.config_model.stt_model_size = self.stt_model_var.get()
        self.config_model.ensure_directories()
        self.video_player.set_video_path(self.config_model.video_path)

    def _preload_tts_model(self) -> None:
        if self.preload_running:
            return
        self._apply_config_from_ui()
        if self.config_model.tts_backend != QWEN_BACKEND:
            return

        self.preload_running = True
        self.status_var.set("Qwen3-TTS 모델을 미리 로딩 중입니다...")
        cache_dir = self.config_model.sessions_root / "_preload"
        provider = QwenTTSProvider(self.config_model, cache_dir)
        self.preload_provider = provider

        def worker() -> None:
            try:
                provider.preload()
            except Exception as exc:
                self.after(0, lambda: self._on_preload_error(exc))
                return
            self.after(0, self._on_preload_done)

        threading.Thread(target=worker, daemon=True).start()

    def _on_preload_done(self) -> None:
        self.preload_running = False
        if self.engine is None:
            if self.config_model.supports_style_instruction():
                self.status_var.set("Qwen3-TTS 모델 준비 완료. 면접관 말투 지시가 적용됩니다.")
            else:
                self.status_var.set("Qwen3-TTS 0.6B 준비 완료. 말투 지시는 1.7B 모델에서 적용됩니다.")

    def _on_preload_error(self, exc: Exception) -> None:
        self.preload_running = False
        if self.engine is None:
            self.status_var.set("Qwen3-TTS 모델 로딩 실패. TTS 진단을 확인하세요.")
            messagebox.showwarning("Qwen3-TTS preload", str(exc))

    def _render_current_question(self) -> None:
        if self.engine is None:
            return
        record = self.engine.current_record
        self.progress_var.set(f"{self.engine.current_index + 1} / {self.engine.question_count}")
        self.current_question_var.set(record.clean_question)
        self.memo_text.delete("1.0", "end")
        self.memo_text.insert("1.0", record.memo)
        self.transcript_text.delete("1.0", "end")
        self.transcript_text.insert("1.0", record.transcript)
        self.followup_text.delete("1.0", "end")
        self.followup_text.insert("1.0", record.follow_up_question)
        self.prev_button.configure(state="normal" if self.engine.current_index > 0 else "disabled")
        self.next_button.configure(state="normal" if self.engine.current_index < self.engine.question_count - 1 else "disabled")

    def _save_current_memo(self) -> None:
        if self.engine is None:
            return
        self.engine.set_current_memo(self.memo_text.get("1.0", "end"))
        self.engine.session.set_transcript(self.engine.current_index, self.transcript_text.get("1.0", "end"))
        self.engine.session.set_follow_up_question(self.engine.current_index, self.followup_text.get("1.0", "end"))
        self.engine.session.save()

    def _get_provider(self) -> QwenTTSProvider:
        if self.engine is None:
            raise RuntimeError("Session has not started.")
        if self.provider is None:
            self._apply_config_from_ui()
            self.provider = QwenTTSProvider(self.config_model, self.engine.session.audio_cache_dir)
        return self.provider

    def _speak_current(self, repeat: bool) -> None:
        if self.engine is None or self.tts_running:
            return
        self._save_current_memo()
        provider = self._get_provider()
        token = self.tts_token + 1
        self.tts_token = token
        self.tts_running = True
        self.repeat_button.configure(state="disabled")
        self.video_player.start()
        if self.config_model.tts_backend == QWEN_BACKEND:
            self.status_var.set("Qwen3-TTS 생성 및 재생 중...")
            self.after(15000, lambda: self._show_slow_tts_notice(token))
        else:
            self.status_var.set("Windows 기본 음성으로 재생 중...")

        def worker() -> None:
            try:
                result = self.engine.speak_current(provider, repeat=repeat)
            except Exception as exc:
                self.after(0, lambda: self._on_tts_error(token, exc))
                return
            self.after(0, lambda: self._on_tts_done(token, result.wav_path))

        threading.Thread(target=worker, daemon=True).start()

    def _show_slow_tts_notice(self, token: int) -> None:
        if token == self.tts_token and self.tts_running:
            self.status_var.set("Qwen3-TTS 생성 중입니다. 모델이 아직 준비 중이면 첫 질문은 조금 걸릴 수 있습니다.")

    def _on_tts_done(self, token: int, wav_path: Path) -> None:
        if token != self.tts_token:
            return
        self.tts_running = False
        self.repeat_button.configure(state="normal")
        self.video_player.stop()
        backend = self.provider._last_backend if self.provider is not None else "unknown"
        warning = self.provider._last_warning if self.provider is not None else ""
        if warning:
            self.status_var.set(f"Windows 기본 음성으로 재생했습니다. 오디오: {wav_path.name}")
            messagebox.showwarning("Qwen3-TTS fallback", warning)
        else:
            self.status_var.set(f"답변 시간을 기록 중입니다. backend={backend}, 오디오: {wav_path.name}")
        self._render_current_question()

    def _on_tts_error(self, token: int, exc: Exception) -> None:
        if token != self.tts_token:
            return
        self.tts_running = False
        self.repeat_button.configure(state="normal")
        self.video_player.stop()
        self.status_var.set("TTS 오류가 발생했습니다.")
        messagebox.showerror("TTS 오류", str(exc))

    def _stop_tts(self) -> None:
        if self.provider is not None:
            self.provider.stop()
        self.video_player.stop()
        if self.engine is not None:
            self.engine.session.start_answer(self.engine.current_index)
            self.engine.session.save()
        self.status_var.set("TTS를 중지했습니다. 답변 시간 기록을 계속합니다.")

    def _start_recording(self) -> None:
        if self.engine is None:
            return
        if self.recording:
            return
        self._save_current_memo()
        self.engine.session.start_answer(self.engine.current_index)
        index = self.engine.current_index + 1
        path = self.engine.session.answers_dir / f"answer_{index:03d}.wav"
        try:
            self.recorder.start(path)
        except STTError as exc:
            messagebox.showerror("녹음 시작 실패", str(exc))
            return

        self.recording = True
        self.recording_path = path
        self.record_button.configure(state="disabled")
        self.stop_record_button.configure(state="normal")
        self.status_var.set("답변 녹음 중입니다.")
        self.engine.session.set_answer_audio_path(self.engine.current_index, path)
        self.engine.session.save()

    def _stop_recording_and_transcribe(self) -> None:
        if self.engine is None or not self.recording:
            return
        try:
            path = self.recorder.stop()
        except STTError as exc:
            self.recording = False
            self.recording_path = None
            self.record_button.configure(state="normal")
            self.stop_record_button.configure(state="disabled")
            messagebox.showerror("녹음 중지 실패", str(exc))
            return

        self.recording = False
        self.recording_path = path
        self.record_button.configure(state="normal")
        self.stop_record_button.configure(state="disabled")
        self.engine.session.set_answer_audio_path(self.engine.current_index, path)
        self.engine.finish_current_answer()
        self.status_var.set("답변 음성을 STT 변환 중입니다...")
        index = self.engine.current_index
        question = self.engine.current_record.clean_question
        language = detect_language(question)

        def worker() -> None:
            try:
                result = self.transcriber.transcribe(path, language=language)
            except Exception as exc:
                self.after(0, lambda: self._on_transcript_error(exc))
                return
            self.after(0, lambda: self._on_transcript_done(index, result.text))

        threading.Thread(target=worker, daemon=True).start()

    def _on_transcript_done(self, index: int, transcript: str) -> None:
        if self.engine is None:
            return
        self.engine.session.set_transcript(index, transcript)
        self.engine.session.save()
        if index == self.engine.current_index:
            self.transcript_text.delete("1.0", "end")
            self.transcript_text.insert("1.0", transcript)
        self.status_var.set("STT 변환이 완료되었습니다.")

    def _on_transcript_error(self, exc: Exception) -> None:
        self.status_var.set("STT 변환 실패")
        messagebox.showerror("STT 오류", str(exc))

    def _generate_follow_up(self) -> None:
        if self.engine is None:
            return
        self._save_current_memo()
        record = self.engine.current_record
        transcript = self.transcript_text.get("1.0", "end").strip() or record.memo
        question = record.clean_question
        language = detect_language(question)
        self.status_var.set("꼬리질문 생성 중입니다...")

        def worker() -> None:
            follow_up = generate_follow_up_question(question, transcript, language)
            self.after(0, lambda: self._on_follow_up_done(follow_up))

        threading.Thread(target=worker, daemon=True).start()

    def _on_follow_up_done(self, follow_up: str) -> None:
        if self.engine is None:
            return
        self.engine.session.set_follow_up_question(self.engine.current_index, follow_up)
        self.engine.session.save()
        self.followup_text.delete("1.0", "end")
        self.followup_text.insert("1.0", follow_up)
        self.status_var.set("꼬리질문이 생성되었습니다.")

    def _speak_follow_up(self) -> None:
        if self.engine is None or self.tts_running:
            return
        self._save_current_memo()
        follow_up = self.followup_text.get("1.0", "end").strip()
        if not follow_up:
            messagebox.showwarning("꼬리질문 없음", "먼저 꼬리질문을 생성하세요.")
            return

        provider = self._get_provider()
        token = self.tts_token + 1
        self.tts_token = token
        self.tts_running = True
        self.repeat_button.configure(state="disabled")
        self.video_player.start()
        self.status_var.set("꼬리질문을 재생 중입니다...")

        def worker() -> None:
            try:
                language, speaker = provider.resolve_voice(follow_up)
                provider.speak(
                    text=follow_up,
                    cache_key=f"{self.engine.session.session_id}-{self.engine.current_index + 1}-followup",
                    language=language,
                    speaker=speaker,
                )
            except Exception as exc:
                self.after(0, lambda: self._on_tts_error(token, exc))
                return
            self.after(0, lambda: self._on_follow_up_tts_done(token))

        threading.Thread(target=worker, daemon=True).start()

    def _on_follow_up_tts_done(self, token: int) -> None:
        if token != self.tts_token:
            return
        self.tts_running = False
        self.repeat_button.configure(state="normal")
        self.video_player.stop()
        self.status_var.set("꼬리질문 재생이 끝났습니다.")

    def _test_system_sound(self) -> None:
        try:
            provider = self._get_provider() if self.engine is not None else QwenTTSProvider(
                self.config_model,
                self.config_model.sessions_root / "_diagnostics",
            )
            provider.play_system_beep()
            self.status_var.set("Windows 시스템 소리 테스트를 실행했습니다.")
        except Exception as exc:
            messagebox.showerror("소리 테스트 실패", str(exc))

    def _diagnose_tts(self) -> None:
        self._apply_config_from_ui()
        cache_dir = (
            self.engine.session.audio_cache_dir
            if self.engine is not None
            else self.config_model.sessions_root / "_diagnostics"
        )
        provider = self.provider or QwenTTSProvider(self.config_model, cache_dir)
        report = "\n".join(provider.diagnose())
        messagebox.showinfo("TTS 진단", report)

    def _next_question(self) -> None:
        if self.engine is None:
            return
        if self.recording:
            messagebox.showwarning("녹음 중", "녹음을 중지한 뒤 다음 질문으로 이동하세요.")
            return
        self._stop_tts()
        self._save_current_memo()
        self.engine.move_next()
        self._render_current_question()
        self._speak_current(repeat=False)

    def _previous_question(self) -> None:
        if self.engine is None:
            return
        if self.recording:
            messagebox.showwarning("녹음 중", "녹음을 중지한 뒤 이전 질문으로 이동하세요.")
            return
        self._stop_tts()
        self._save_current_memo()
        self.engine.move_previous()
        self._render_current_question()
        self._speak_current(repeat=False)

    def _restart_session(self) -> None:
        if self.engine is None:
            return
        if self.recording:
            messagebox.showwarning("녹음 중", "녹음을 중지한 뒤 다시 시작하세요.")
            return
        self._stop_tts()
        self._save_current_memo()
        self.engine.restart()
        self.provider = QwenTTSProvider(self.config_model, self.engine.session.audio_cache_dir)
        self._render_current_question()
        self.status_var.set("새 세션으로 다시 시작했습니다.")
        self._speak_current(repeat=False)

    def _open_session_folder(self) -> None:
        if self.engine is None:
            return
        self._save_current_memo()
        path = self.engine.session.session_dir
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            messagebox.showinfo("저장 폴더", str(path))

    def _update_timers(self) -> None:
        if self.engine is not None:
            self.total_timer_var.set(_format_seconds(self.engine.session.elapsed_seconds()))
            record = self.engine.current_record
            if record.answer_started_at and not record.answer_finished_at and record._answer_start_monotonic is not None:
                self.answer_timer_var.set(_format_seconds(time.monotonic() - record._answer_start_monotonic))
            elif record.answer_seconds is not None:
                self.answer_timer_var.set(_format_seconds(record.answer_seconds))
            else:
                self.answer_timer_var.set("00:00")
        self.after(250, self._update_timers)

    def _on_close(self) -> None:
        if self.recording:
            try:
                self.recorder.stop()
            except Exception:
                pass
            self.recording = False
        self.video_player.stop()
        if self.engine is not None:
            self._save_current_memo()
            self.engine.finish_current_answer()
        self.destroy()


def _format_seconds(seconds: float) -> str:
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def run_app() -> int:
    app = InterviewApp()
    app.mainloop()
    return 0
