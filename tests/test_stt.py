from ai_interviewer.stt import input_device_id_from_label


def test_input_device_id_from_label() -> None:
    assert input_device_id_from_label("Default") is None
    assert input_device_id_from_label("") is None
    assert input_device_id_from_label("2: USB Microphone") == 2
    assert input_device_id_from_label("not a device") is None
