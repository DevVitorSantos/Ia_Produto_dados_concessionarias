from __future__ import annotations

import uuid
from typing import Any

import streamlit as st

from services.search_classifier import normalize_question

MESSAGES_KEY = "chat_messages"
ANSWERS_KEY = "chat_answers"
PENDING_KEY = "pending_prompt"
SESSION_KEY = "chat_session_id"
FEEDBACK_KEY = "chat_feedback"


def init_state() -> None:
    st.session_state.setdefault(MESSAGES_KEY, [])
    st.session_state.setdefault(ANSWERS_KEY, [])
    st.session_state.setdefault(PENDING_KEY, None)
    st.session_state.setdefault(SESSION_KEY, str(uuid.uuid4()))
    st.session_state.setdefault(FEEDBACK_KEY, {})


def clear_conversation() -> None:
    st.session_state[MESSAGES_KEY] = []
    st.session_state[ANSWERS_KEY] = []
    st.session_state[PENDING_KEY] = None


def record_message(role: str, content: str, answer: Any | None = None) -> None:
    init_state()
    payload = {"role": role, "content": content}
    if answer is not None:
        payload["answer"] = answer.to_dict()
        st.session_state[ANSWERS_KEY].append(answer.to_dict())
    st.session_state[MESSAGES_KEY].append(payload)


def history_for_api() -> list[dict[str, str]]:
    init_state()
    return [
        {"role": item["role"], "content": item["content"]}
        for item in st.session_state[MESSAGES_KEY]
        if item.get("role") in {"user", "assistant"}
    ]


def repeat_count_for(question: str) -> int:
    init_state()
    normalized = normalize_question(question)
    return sum(
        1
        for item in st.session_state[MESSAGES_KEY]
        if item.get("role") == "user"
        and normalize_question(str(item.get("content", ""))) == normalized
    )


def record_feedback(event_id: str, rating: str) -> None:
    init_state()
    st.session_state[FEEDBACK_KEY][event_id] = rating
