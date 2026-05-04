import os
import subprocess
import traceback
import uuid
from pathlib import Path
from fastapi.staticfiles import StaticFiles

import requests
from dotenv import load_dotenv
from fastapi import UploadFile, File, Form, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from main import process_user_message
from memory.short_term import init_memory
from stt.whisper_service import transcribe_audio

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

if not ELEVENLABS_API_KEY:
    raise RuntimeError("ELEVENLABS_API_KEY is missing in .env")

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
UPLOADS_DIR = BASE_DIR / "uploads"
VOICES_DIR = UPLOADS_DIR / "voices"
AVATARS_DIR = UPLOADS_DIR / "avatars"
TTS_DIR = UPLOADS_DIR / "tts"

VOICES_DIR.mkdir(parents=True, exist_ok=True)
AVATARS_DIR.mkdir(parents=True, exist_ok=True)
TTS_DIR.mkdir(parents=True, exist_ok=True)
# Serve uploaded files (voices, avatars, tts) as static
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

memory = init_memory()


class ChatRequest(BaseModel):
    message: str


def speak_default(text: str) -> None:
    subprocess.run(["say", "-v", "Samantha", text], check=True)


def convert_audio_to_wav(input_path: Path) -> Path:
    output_path = input_path.with_suffix(".wav")

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "44100",
        str(output_path),
    ]

    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg failed: {e.stderr}")

    return output_path


def _save_tts_bytes(audio_bytes: bytes, ext: str = ".mp3") -> Path:
    file_id = f"{uuid.uuid4()}{ext}"
    out_path = TTS_DIR / file_id
    out_path.write_bytes(audio_bytes)
    return out_path


def _say_tts_to_mp3(text: str) -> Path:
    """Use macOS 'say' to synthesize speech and convert to mp3, then save under TTS_DIR.

    Falls back to raising RuntimeError if any step fails.
    """
    tmp_aiff = TTS_DIR / f"{uuid.uuid4()}.aiff"
    out_mp3 = TTS_DIR / f"{uuid.uuid4()}.mp3"

    try:
        # Generate AIFF using system voice
        subprocess.run(["say", "-v", "Samantha", "-o", str(tmp_aiff), text], check=True)

        # Convert to MP3 via ffmpeg
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(tmp_aiff),
            "-ar",
            "44100",
            "-ac",
            "2",
            "-b:a",
            "128k",
            str(out_mp3),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"TTS generation failed: {e.stderr}")
    finally:
        try:
            if tmp_aiff.exists():
                tmp_aiff.unlink()
        except Exception:
            pass

    return out_mp3


def create_custom_voice(name: str, audio_file_path: str) -> str:
    url = "https://api.elevenlabs.io/v1/voices/add"

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
    }

    with open(audio_file_path, "rb") as audio:
        files = [
            ("files", (Path(audio_file_path).name, audio, "audio/wav")),
        ]

        data = {
            "name": name,
            "description": "Custom cloned voice for assistant project",
        }

        response = requests.post(
            url,
            headers=headers,
            files=files,
            data=data,
            timeout=60,
        )

    if response.status_code >= 400:
        raise RuntimeError(f"ElevenLabs voice clone error: {response.text}")

    return response.json()["voice_id"]


def clone_voice_api(text: str, voice_id: str) -> bytes:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128"

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.8,
            "style": 0.2,
            "use_speaker_boost": True,
        },
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=60,
    )

    if response.status_code >= 400:
        raise RuntimeError(f"ElevenLabs TTS error: {response.text}")

    return response.content


@app.post("/chat")
def chat(request: ChatRequest):
    reply = process_user_message(request.message, memory)
    return {"reply": reply}


@app.post("/voice")
async def voice(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    text = transcribe_audio(audio_bytes)
    reply = process_user_message(text, memory)

    return {
        "transcript": text,
        "reply": reply,
    }


@app.post("/upload-voice")
async def upload_voice_endpoint(file: UploadFile = File(...)):
    try:
        filename = file.filename or "voice.wav"

        wav_path = VOICES_DIR / filename

        # если уже есть → НЕ создаём новый voice
        if wav_path.exists():
            voice_id = wav_path.with_suffix(".id").read_text()
            print("✅ reused voice_id:", voice_id)
            return {"voice_id": voice_id}

        # сохраняем файл
        wav_path.write_bytes(await file.read())

        # конвертируем (перезапишет)
        wav_path = convert_audio_to_wav(wav_path)

        # создаём voice
        voice_id = create_custom_voice(
            name=filename,
            audio_file_path=str(wav_path),
        )

        # сохраняем voice_id рядом
        (wav_path.with_suffix(".id")).write_text(voice_id)

        return {"voice_id": voice_id}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload-avatar")
async def upload_avatar_endpoint(file: UploadFile = File(...)):
    suffix = Path(file.filename or "avatar.png").suffix or ".png"
    avatar_id = f"{uuid.uuid4()}{suffix}"

    save_path = AVATARS_DIR / avatar_id
    save_path.write_bytes(await file.read())

    return {
        "avatar_id": avatar_id,
        "avatar_path": str(save_path),
    }


@app.post("/speak-default")
def speak_default_endpoint(request: Request, text: str = Form(...)):
    # Generate and save mp3 locally, return a persistent URL
    out_mp3 = _say_tts_to_mp3(text)

    base_url = str(request.base_url).rstrip("/")
    audio_rel = f"/uploads/tts/{out_mp3.name}"
    audio_url = f"{base_url}{audio_rel}"

    return {
        "audio_url": audio_url,
        "file": out_mp3.name,
        "path": str(out_mp3),
    }


@app.post("/speak-clone")
async def speak_clone_endpoint(
    request: Request,
    text: str = Form(...),
    voice_id: str = Form(...),
):
    try:
        audio_bytes = clone_voice_api(text, voice_id)

        saved_path = _save_tts_bytes(audio_bytes, ext=".mp3")
        base_url = str(request.base_url).rstrip("/")
        audio_url = f"{base_url}/uploads/tts/{saved_path.name}"

        return {
            "audio_url": audio_url,
            "file": saved_path.name,
            "path": str(saved_path),
            "voice_id": voice_id,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
