import os
import subprocess
import uuid
import shutil
from pathlib import Path

import requests
from dotenv import load_dotenv
from fastapi import UploadFile, File, Form, FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
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

VOICES_DIR.mkdir(parents=True, exist_ok=True)
AVATARS_DIR.mkdir(parents=True, exist_ok=True)

memory = init_memory()


class ChatRequest(BaseModel):
    message: str


class SpeakCloneRequest(BaseModel):
    text: str
    voice_id: str


class ElevenLabsAPIError(RuntimeError):
    """Represents an error response returned by ElevenLabs API.

    Carries the upstream HTTP status code and the response text to allow
    the endpoint to map it to an appropriate client-facing status.
    """

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def speak_default(text: str) -> None:
    subprocess.run(["say", "-v", "Samantha", text], check=True)


def convert_audio_to_wav(input_path: Path) -> Path:
    output_path = input_path.with_suffix(".wav")

    # Validate ffmpeg availability early to provide a clear error
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg is not installed or not found in PATH. Please install ffmpeg and try again."
        )

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
    except FileNotFoundError:
        # Edge case: ffmpeg disappeared between the earlier check and now
        raise RuntimeError(
            "ffmpeg binary not found at runtime. Ensure ffmpeg is installed and accessible in PATH."
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg failed: {e.stderr}")

    return output_path


def create_custom_voice(name: str, audio_file_path: str) -> str:
    url = "https://api.elevenlabs.io/v1/voices/add"

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
    }

    try:
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
    except requests.RequestException as e:
        # Network/connection error to upstream
        raise RuntimeError(f"ElevenLabs voice clone request failed: {e}")

    if response.status_code >= 400:
        # Bubble up upstream error with its status for proper mapping
        raise ElevenLabsAPIError(response.status_code, response.text)

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

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=60,
        )
    except requests.RequestException as e:
        # Network/connection error to upstream
        raise RuntimeError(f"ElevenLabs TTS request failed: {e}")

    if response.status_code >= 400:
        # Bubble up upstream error with its status for proper mapping
        raise ElevenLabsAPIError(response.status_code, response.text)

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
        original_suffix = Path(file.filename or "voice").suffix or ".audio"
        original_file_id = f"{uuid.uuid4()}{original_suffix}"
        original_path = VOICES_DIR / original_file_id

        original_path.write_bytes(await file.read())

        wav_path = convert_audio_to_wav(original_path)

        elevenlabs_voice_id = create_custom_voice(
            name=f"Custom voice {uuid.uuid4()}",
            audio_file_path=str(wav_path),
        )

        return {
            "voice_id": elevenlabs_voice_id,
            "local_original_file_id": original_file_id,
            "local_wav_file": wav_path.name,
            "voice_path": str(wav_path),
        }

    except Exception as e:
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
def speak_default_endpoint(text: str = Form(...)):
    speak_default(text)
    return {"status": "ok"}


@app.post("/speak-clone")
async def speak_clone_endpoint(
    # Accept either multipart/form-data (Form) or JSON (Body)
    text: str | None = Form(None),
    voice_id: str | None = Form(None),
    payload: SpeakCloneRequest | None = Body(None),
    voice_file: UploadFile | None = File(None),
):
    try:
        # Prefer JSON payload if provided
        if payload is not None:
            text = payload.text
            voice_id = payload.voice_id

        # If a raw voice file is provided, create a temporary custom voice first
        if voice_file is not None and voice_id is None:
            # Save uploaded file
            original_suffix = Path(voice_file.filename or "voice").suffix or ".audio"
            original_file_id = f"{uuid.uuid4()}{original_suffix}"
            original_path = VOICES_DIR / original_file_id
            original_path.write_bytes(await voice_file.read())

            # Convert to wav and create voice on ElevenLabs
            wav_path = convert_audio_to_wav(original_path)
            voice_id = create_custom_voice(
                name=f"Custom voice {uuid.uuid4()}",
                audio_file_path=str(wav_path),
            )

        # Validate inputs regardless of the source
        if not text:
            raise HTTPException(status_code=400, detail="Missing required field: 'text'.")

        if not voice_id:
            raise HTTPException(
                status_code=400,
                detail="Provide either 'voice_id' (form or JSON) or 'voice_file' (multipart/form-data).",
            )

        audio_bytes = clone_voice_api(text, voice_id)

        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
        )
    except ElevenLabsAPIError as e:
        # Map upstream ElevenLabs errors: 4xx -> 400 (client input/quota), 5xx -> 502
        status = getattr(e, "status_code", 500)
        detail = str(e)
        if 400 <= status <= 499:
            raise HTTPException(status_code=400, detail=detail)
        # Treat 5xx as upstream failure
        raise HTTPException(status_code=502, detail=detail)
    except RuntimeError as e:
        # Classify known runtime errors for clearer client feedback
        msg = str(e)
        if "ffmpeg" in msg.lower():
            # Conversion failure or missing dependency
            raise HTTPException(status_code=424, detail=msg)
        # Likely upstream ElevenLabs error surfaced from helper functions
        raise HTTPException(status_code=502, detail=msg)
    except Exception as e:
        # Unexpected error
        raise HTTPException(status_code=500, detail=str(e))