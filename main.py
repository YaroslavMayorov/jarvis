from llm.ollama_client import ask_ollama
from memory.short_term import add_user_message, add_assistant_message


def process_user_message(user_text: str, memory: list[dict]) -> str:
    add_user_message(memory, user_text)

    assistant_reply = ask_ollama(memory)

    add_assistant_message(memory, assistant_reply)

    return assistant_reply