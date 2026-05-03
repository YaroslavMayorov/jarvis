from llm.ollama_client import ask_ollama
from memory.short_term import (
    add_user_message,
    add_assistant_message,
    needs_summary,
    trim_memory_with_summary,
    get_messages_to_summarize,
)


def summarize_memory(memory: list[dict]) -> str:
    old_summary = memory[1]["content"]
    messages_to_summarize = get_messages_to_summarize(memory)

    prompt = [
        {
            "role": "system",
            "content": (
                "Update the conversation summary.\n"
                "Use the old summary and the older messages.\n"
                "Keep important user facts, preferences, goals, and project state.\n"
                "Be concise."
            ),
        },
        {
            "role": "user",
            "content": (
                f"OLD SUMMARY:\n{old_summary}\n\n"
                f"OLDER MESSAGES TO ADD:\n{messages_to_summarize}"
            ),
        },
    ]

    return ask_ollama(prompt)


def process_user_message(user_text: str, memory: list[dict]) -> str:
    add_user_message(memory, user_text)

    assistant_reply = ask_ollama(memory)

    add_assistant_message(memory, assistant_reply)

    if needs_summary(memory):
        summary = summarize_memory(memory)
        trim_memory_with_summary(memory, summary)

    return assistant_reply