import streamlit as st

from main import process_user_message
from memory.short_term import init_memory


st.set_page_config(
    page_title="Jarvis",
    page_icon="🤖",
    layout="centered"
)

st.title("🤖 Jarvis")

if "memory" not in st.session_state:
    st.session_state.memory = init_memory()

for message in st.session_state.memory:
    if message["role"] == "system":
        continue

    with st.chat_message(message["role"]):
        st.write(message["content"])

user_text = st.chat_input("Ask Jarvis something...")

if user_text:
    with st.chat_message("user"):
        st.write(user_text)

    with st.chat_message("assistant"):
        with st.spinner("Jarvis is thinking..."):
            reply = process_user_message(
                user_text,
                st.session_state.memory
            )
            st.write(reply)