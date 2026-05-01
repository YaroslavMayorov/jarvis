MAX_MESSAGES = 12
def init_memory():
    return [
        {
            "role": "system",
            "content": "You are Jarvis, a helpful voice assistant. Answer clearly and briefly."
        }
    ]


def add_user_message(memory, text):
    memory.append({"role": "user", "content": text})
    trim_memory(memory)


def add_assistant_message(memory, text):
    memory.append({"role": "assistant", "content": text})
    trim_memory(memory)


def trim_memory(memory):
    system_message = memory[0]
    conversation = memory[1:]

    if len(conversation) > MAX_MESSAGES:
        conversation = conversation[-MAX_MESSAGES:]

    memory.clear()
    memory.append(system_message)
    memory.extend(conversation)