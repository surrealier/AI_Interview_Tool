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
from ai_interviewer.question_parser import parse_questions
from ai_interviewer.tts.qwen_provider import QwenTTSProvider


class InterviewApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AI Interviewer")
        self.geometry("1120x760")
        self.minsize(980, 680)

        self.config_model = AppConfig()
        self.config_model.ensure_directories()
        self.engine: InterviewEngine | None = None
        self.provider: QwenTTSProvider | None = None
        self.tts_token = 0
        self.tts_running = False

        self._build_variables()
        self._build_ui()
        self._set_session_controls(False)
        self.after(250, self._update_timers)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_variables(self) -> None:
        self.tts_backend_var = tk.StringVar(value=WINDOWS_SAPI_BACKEND)
        self.model_var = tk.StringVar(value=DEFAULT_MODEL_ID)
        self.model_root_var = tk.StringVar(value=str(self.config_model.model_root))
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
        self.question_text.insert(
            "1.0",
            "1. 자기소개를 해주세요.\n"
            "1.2. 가장 자신 있는 프로젝트를 설명해주세요.\n"
            "Q3. What is your biggest strength?\n",
        )

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

        session_frame = ttk.LabelFrame(root, text="면접 진행", padding=10)
        session_frame.grid(row=1, column=1, rowspan=2, sticky="nsew")
        session_frame.columnconfigure(0, weight=1)
        session_frame.rowconfigure(2, weight=1)

        info = ttk.Frame(session_frame)
        info.grid(row=0, column=0, sticky="ew")
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
        question_box.grid(row=1, column=0, sticky="ew", pady=10)
        question_box.columnconfigure(0, weight=1)
        ttk.Label(
            question_box,
            textvariable=self.current_question_var,
            wraplength=360,
            justify="left",
            font=("Segoe UI", 13),
        ).grid(row=0, column=0, sticky="ew")

        memo_box = ttk.LabelFrame(session_frame, text="메모", padding=8)
        memo_box.grid(row=2, column=0, sticky="nsew")
        memo_box.columnconfigure(0, weight=1)
        memo_box.rowconfigure(0, weight=1)
        self.memo_text = tk.Text(memo_box, wrap="word", height=8)
        self.memo_text.grid(row=0, column=0, sticky="nsew")

        controls = ttk.Frame(session_frame)
        controls.grid(row=3, column=0, sticky="ew", pady=(10, 0))
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

        self.prev_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.next_button.grid(row=0, column=1, sticky="ew", padx=4)
        self.repeat_button.grid(row=0, column=2, sticky="ew", padx=4)
        self.stop_button.grid(row=0, column=3, sticky="ew", padx=(4, 0))
        self.restart_button.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0), padx=(0, 4))
        self.open_folder_button.grid(row=1, column=2, columnspan=2, sticky="ew", pady=(6, 0), padx=(4, 0))
        self.sound_test_button.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0), padx=(0, 4))
        self.diagnostics_button.grid(row=2, column=2, columnspan=2, sticky="ew", pady=(6, 0), padx=(4, 0))

    def _set_session_controls(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in (
            self.prev_button,
            self.next_button,
            self.repeat_button,
            self.stop_button,
            self.restart_button,
            self.open_folder_button,
        ):
            button.configure(state=state)
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
            self.provider = None

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
        self.config_model.default_language = self.language_var.get()
        self.config_model.korean_speaker = self.korean_speaker_var.get().strip() or "Sohee"
        self.config_model.english_speaker = self.english_speaker_var.get().strip() or "Ryan"
        self.config_model.ensure_directories()

    def _render_current_question(self) -> None:
        if self.engine is None:
            return
        record = self.engine.current_record
        self.progress_var.set(f"{self.engine.current_index + 1} / {self.engine.question_count}")
        self.current_question_var.set(record.clean_question)
        self.memo_text.delete("1.0", "end")
        self.memo_text.insert("1.0", record.memo)
        self.prev_button.configure(state="normal" if self.engine.current_index > 0 else "disabled")
        self.next_button.configure(state="normal" if self.engine.current_index < self.engine.question_count - 1 else "disabled")

    def _save_current_memo(self) -> None:
        if self.engine is None:
            return
        self.engine.set_current_memo(self.memo_text.get("1.0", "end"))
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
            self.status_var.set("TTS 생성 중입니다. 첫 실행은 모델 로딩 때문에 몇 분 걸릴 수 있습니다.")

    def _on_tts_done(self, token: int, wav_path: Path) -> None:
        if token != self.tts_token:
            return
        self.tts_running = False
        self.repeat_button.configure(state="normal")
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
        self.status_var.set("TTS 오류가 발생했습니다.")
        messagebox.showerror("TTS 오류", str(exc))

    def _stop_tts(self) -> None:
        if self.provider is not None:
            self.provider.stop()
        if self.engine is not None:
            self.engine.session.start_answer(self.engine.current_index)
            self.engine.session.save()
        self.status_var.set("TTS를 중지했습니다. 답변 시간 기록을 계속합니다.")

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
        self._stop_tts()
        self._save_current_memo()
        self.engine.move_next()
        self._render_current_question()
        self._speak_current(repeat=False)

    def _previous_question(self) -> None:
        if self.engine is None:
            return
        self._stop_tts()
        self._save_current_memo()
        self.engine.move_previous()
        self._render_current_question()
        self._speak_current(repeat=False)

    def _restart_session(self) -> None:
        if self.engine is None:
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
