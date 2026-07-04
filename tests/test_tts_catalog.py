from ai_interviewer.config import DEFAULT_MODEL_ID, LARGE_MODEL_ID, AppConfig, model_dir_name
from ai_interviewer.default_questions import ENGLISH_MODE, KOREAN_MODE
from ai_interviewer.tts_catalog import default_speaker_for_language, speaker_ids, speaker_options, tts_model_options


def test_speaker_catalog_lists_supported_custom_voice_speakers() -> None:
    ids = speaker_ids()

    assert len(ids) == 9
    assert "Sohee" in ids
    assert "Ryan" in ids
    assert "Aiden" in ids
    assert default_speaker_for_language(KOREAN_MODE).speaker_id == "Sohee"
    assert default_speaker_for_language(ENGLISH_MODE).speaker_id == "Ryan"
    assert speaker_options(KOREAN_MODE)[0].speaker_id == "Sohee"
    assert speaker_options(ENGLISH_MODE)[0].speaker_id == "Ryan"


def test_tts_model_catalog_marks_local_install_state(tmp_path) -> None:
    config = AppConfig(model_root=tmp_path / "models", config_path=tmp_path / "config.json")
    model_dir = config.model_root / model_dir_name(DEFAULT_MODEL_ID)
    model_dir.mkdir(parents=True)
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "model.safetensors").write_bytes(b"fake")

    options = tts_model_options(config)
    by_id = {option.model_id: option for option in options}

    assert by_id[DEFAULT_MODEL_ID].installed is True
    assert by_id[LARGE_MODEL_ID].installed is False
    assert by_id[LARGE_MODEL_ID].supports_tone_control is True


def test_tts_model_catalog_treats_empty_dir_as_not_installed(tmp_path) -> None:
    config = AppConfig(model_root=tmp_path / "models", config_path=tmp_path / "config.json")
    (config.model_root / model_dir_name(DEFAULT_MODEL_ID)).mkdir(parents=True)

    options = tts_model_options(config)
    by_id = {option.model_id: option for option in options}

    assert by_id[DEFAULT_MODEL_ID].installed is False
