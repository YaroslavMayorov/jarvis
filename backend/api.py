from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from main import process_user_message
from memory.short_term import init_memory
from stt.whisper_service import transcribe_audio


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

memory = init_memory()


class ChatRequest(BaseModel):
    message: str


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