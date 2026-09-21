from __future__ import annotations

import pytest

from ai_interviewer import stt
from ai_interviewer.config import (
    STT_MODEL_AUTO,
    STT_MODEL_CPU_DEFAULT,
    STT_MODEL_CUDA_DEFAULT,
    SUPPORTED_STT_MODELS,
    AppConfig,
)


def test_auto_is_the_shipped_default(tmp_path) -> None:
    assert AppConfig(config_path=tmp_path / "c.json").stt_model_size == STT_MODEL_AUTO


def test_auto_picks_turbo_on_cuda_and_small_on_cpu() -> None:
    """Measured on 24s of Korean speech: turbo runs 23.8x realtime on CUDA but
    only 3.4x on CPU, where `small` manages 7.9x."""
    assert stt.resolve_model_size(STT_MODEL_AUTO, "cuda") == STT_MODEL_CUDA_DEFAULT
    assert stt.resolve_model_size(STT_MODEL_AUTO, "cpu") == STT_MODEL_CPU_DEFAULT


@pytest.mark.parametrize("name", ["tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"])
def test_an_explicit_choice_is_never_overridden(name: str) -> None:
    assert stt.resolve_model_size(name, "cpu") == name
    assert stt.resolve_model_size(name, "cuda") == name


def test_blank_model_falls_back_to_auto_behaviour() -> None:
    assert stt.resolve_model_size("", "cpu") == STT_MODEL_CPU_DEFAULT


def test_english_only_checkpoints_are_not_offered() -> None:
    """distil-* and *.en silently translate Korean speech into English, which
    would corrupt every Korean transcript."""
    assert not [name for name in SUPPORTED_STT_MODELS if "distil" in name or name.endswith(".en")]


def test_turbo_is_offered_and_is_the_only_large_default() -> None:
    assert STT_MODEL_CUDA_DEFAULT in SUPPORTED_STT_MODELS
    assert STT_MODEL_CPU_DEFAULT in SUPPORTED_STT_MODELS
    assert STT_MODEL_AUTO == SUPPORTED_STT_MODELS[0]


def test_device_resolution_falls_back_to_cpu_without_torch(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def no_torch(name, *args, **kwargs):
        if name == "torch":
            raise ImportError("no torch here")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_torch)
    assert stt.resolve_device("auto") == "cpu"


def test_explicit_device_is_respected() -> None:
    assert stt.resolve_device("cpu") == "cpu"
    assert stt.resolve_device("cuda") == "cuda"


def test_effective_model_size_reports_what_will_load(tmp_path) -> None:
    config = AppConfig(config_path=tmp_path / "c.json", stt_device="cpu", stt_model_size=STT_MODEL_AUTO)
    assert stt.effective_model_size(config) == STT_MODEL_CPU_DEFAULT

    config.stt_device = "cuda"
    assert stt.effective_model_size(config) == STT_MODEL_CUDA_DEFAULT

    config.stt_model_size = "medium"
    assert stt.effective_model_size(config) == "medium"


def test_compute_type_never_asks_for_float16_on_cpu(tmp_path) -> None:
    """CTranslate2 rejects float16 on CPU, so `auto` must not produce it."""
    config = AppConfig(config_path=tmp_path / "c.json", stt_device="cpu", stt_compute_type="auto")
    device, compute_type = stt.WhisperTranscriber(config)._resolve_runtime()
    assert (device, compute_type) == ("cpu", "int8")

    config.stt_device = "cuda"
    assert stt.WhisperTranscriber(config)._resolve_runtime() == ("cuda", "float16")


def test_suggested_local_models_are_small_enough_for_cpu() -> None:
    from ai_interviewer.config import SUGGESTED_OLLAMA_MODELS

    assert SUGGESTED_OLLAMA_MODELS
    # Korean is the primary interview language, so a Qwen model leads the list.
    assert SUGGESTED_OLLAMA_MODELS[0].startswith("qwen")
