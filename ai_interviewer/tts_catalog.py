from __future__ import annotations

from dataclasses import dataclass

from ai_interviewer.config import AppConfig, DEFAULT_MODEL_ID, LARGE_MODEL_ID, is_model_installed
from ai_interviewer.default_questions import ENGLISH_MODE, KOREAN_MODE
from ai_interviewer.i18n import tr


@dataclass(frozen=True, slots=True)
class TTSModelOption:
    model_id: str
    display_name: str
    description: str
    installed: bool
    supports_tone_control: bool
    recommended: bool = False


@dataclass(frozen=True, slots=True)
class SpeakerOption:
    speaker_id: str
    display_name: str
    description: str
    native_language: str
    recommended_languages: tuple[str, ...]


@dataclass(slots=True)
class InterviewSetupState:
    language: str
    model_id: str
    speaker: str
    interview_type: str
    question_source: str = "default"
    questions_text: str = ""
    sound_test_status: str = "not_run"
    enable_stt: bool = True
    allow_fallback: bool = False
    followup_provider: str = "Auto"


SPEAKERS: tuple[SpeakerOption, ...] = (
    SpeakerOption("Sohee", "Sohee", "Warm Korean female voice.", "Korean", (KOREAN_MODE,)),
    SpeakerOption("Ryan", "Ryan", "Dynamic male voice with rhythm.", "English", (ENGLISH_MODE,)),
    SpeakerOption("Aiden", "Aiden", "Sunny American male voice.", "English", (ENGLISH_MODE,)),
    SpeakerOption("Vivian", "Vivian", "Bright young female voice.", "Chinese", ()),
    SpeakerOption("Serena", "Serena", "Warm, gentle young female voice.", "Chinese", ()),
    SpeakerOption("Uncle_Fu", "Uncle_Fu", "Seasoned male voice, mellow timbre.", "Chinese", ()),
    SpeakerOption("Dylan", "Dylan", "Youthful Beijing male voice.", "Chinese (Beijing)", ()),
    SpeakerOption("Eric", "Eric", "Lively Chengdu male voice.", "Chinese (Sichuan)", ()),
    SpeakerOption("Ono_Anna", "Ono_Anna", "Playful Japanese female voice.", "Japanese", ()),
)


def tts_model_options(config: AppConfig) -> tuple[TTSModelOption, ...]:
    large_installed = is_model_installed(config.model_root, LARGE_MODEL_ID)
    default_installed = is_model_installed(config.model_root, DEFAULT_MODEL_ID)
    return (
        TTSModelOption(
            model_id=DEFAULT_MODEL_ID,
            display_name="0.6B CustomVoice",
            description=tr("catalog.model_06_desc"),
            installed=default_installed,
            supports_tone_control=False,
            recommended=not large_installed,
        ),
        TTSModelOption(
            model_id=LARGE_MODEL_ID,
            display_name="1.7B CustomVoice",
            description=tr("catalog.model_17_desc"),
            installed=large_installed,
            supports_tone_control=True,
            recommended=True,
        ),
    )


def model_option_by_id(config: AppConfig, model_id: str) -> TTSModelOption:
    for option in tts_model_options(config):
        if option.model_id == model_id:
            return option
    return tts_model_options(config)[0]


def speaker_options(language: str | None = None) -> tuple[SpeakerOption, ...]:
    if language is None:
        return SPEAKERS
    recommended = [speaker for speaker in SPEAKERS if language in speaker.recommended_languages]
    others = [speaker for speaker in SPEAKERS if language not in speaker.recommended_languages]
    return tuple(recommended + others)


def speaker_by_id(speaker_id: str) -> SpeakerOption:
    normalized = speaker_id.strip().lower()
    for speaker in SPEAKERS:
        if speaker.speaker_id.lower() == normalized:
            return speaker
    return default_speaker_for_language(KOREAN_MODE)


def speaker_ids(language: str | None = None) -> tuple[str, ...]:
    return tuple(speaker.speaker_id for speaker in speaker_options(language))


def default_speaker_for_language(language: str) -> SpeakerOption:
    if language == ENGLISH_MODE:
        return speaker_by_id("Ryan")
    return next(speaker for speaker in SPEAKERS if speaker.speaker_id == "Sohee")


def speaker_description(speaker: SpeakerOption) -> str:
    return tr(f"catalog.speaker.{speaker.speaker_id}")


def native_language_label(speaker: SpeakerOption) -> str:
    return tr(f"lang.native.{speaker.native_language}")


def backend_display_name(backend: str) -> str:
    return tr(f"backend.{backend}")


def speaker_label(speaker: SpeakerOption) -> str:
    return f"{speaker.display_name} · {native_language_label(speaker)} · {speaker_description(speaker)}"
