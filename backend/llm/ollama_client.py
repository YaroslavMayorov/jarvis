import ollama

MODEL_NAME = "llama3.2:3b"


def ask_ollama(messages: list[dict]) -> str:
    response = ollama.chat(
        model=MODEL_NAME,
        messages=messages
    )

    return response["message"]["content"]