import tempfile
import whisper
import os

_model = None


def get_whisper_model():
    global _model

    if _model is None:
        _model = whisper.load_model("base")

    return _model


def transcribe_audio(audio_bytes: bytes) -> str:
    model = get_whisper_model()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
        temp_audio.write(audio_bytes)
        temp_audio_path = temp_audio.name

    result = model.transcribe(temp_audio_path)
    os.remove(temp_audio_path)

    return result["text"].strip()