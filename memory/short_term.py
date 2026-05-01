MAX_RECENT_MESSAGES = 10


def init_memory() -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "You are Jarvis, a helpful voice assistant. "
                "Answer clearly and briefly."
            ),
        },
        {
            "role": "system",
            "content": "Conversation summary: no previous context yet.",
        },
    ]


def add_user_message(memory: list[dict], text: str) -> None:
    memory.append({
        "role": "user",
        "content": text,
    })


def add_assistant_message(memory: list[dict], text: str) -> None:
    memory.append({
        "role": "assistant",
        "content": text,
    })

def get_conversation(memory: list[dict]) -> list[dict]:
    return memory[2:]

def get_messages_to_summarize(memory: list[dict]) -> list[dict]:
    conversation = get_conversation(memory)

    return conversation[:-MAX_RECENT_MESSAGES]


def get_recent_messages(memory: list[dict]) -> list[dict]:
    conversation = get_conversation(memory)

    return conversation[-MAX_RECENT_MESSAGES:]


def needs_summary(memory: list[dict]) -> bool:
    return len(get_messages_to_summarize(memory)) > 0


def trim_memory_with_summary(memory: list[dict], new_summary: str) -> None:
    system_message = memory[0]

    summary_message = {
        "role": "system",
        "content": f"Conversation summary: {new_summary}",
    }

    recent_messages = get_recent_messages(memory)

    memory.clear()
    memory.append(system_message)
    memory.append(summary_message)
    memory.extend(recent_messages)
    print(memory)