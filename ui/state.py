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
FILTER_KEY = "conversation_filter"

FILTER_DIMENSIONS = (
    "data",
    "concessionaria",
    "cidade",
    "estado",
    "vendedor",
    "modelo",
    "categoria_desconto",
    "faixa_preco",
)


def build_conversation_filter(
    dimension: str,
    value: Any,
    operator: str = "=",
) -> dict[str, Any] | None:
    dimension_name = str(dimension or "").strip()
    if not dimension_name:
        return None
    normalized_operator = str(operator or "=").strip().upper()

    if normalized_operator == "BETWEEN":
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            return None
        start, end = value
        if start in (None, "") or end in (None, ""):
            return None
        start_text, end_text = str(start).strip(), str(end).strip()
        if start_text > end_text:
            return None
        return {
            "dimension": dimension_name,
            "operator": "BETWEEN",
            "value": [start_text, end_text],
        }

    text = str(value or "").strip()
    if not text:
        return None
    return {
        "dimension": dimension_name,
        "operator": normalized_operator,
        "value": text,
    }


def init_state() -> None:
    st.session_state.setdefault(MESSAGES_KEY, [])
    st.session_state.setdefault(ANSWERS_KEY, [])
    st.session_state.setdefault(PENDING_KEY, None)
    st.session_state.setdefault(SESSION_KEY, str(uuid.uuid4()))
    st.session_state.setdefault(FEEDBACK_KEY, {})
    st.session_state.setdefault(FILTER_KEY, None)


def conversation_filter() -> dict[str, Any] | None:
    init_state()
    value = st.session_state.get(FILTER_KEY)
    return value if isinstance(value, dict) else None


def set_conversation_filter(value: dict[str, Any] | None) -> None:
    init_state()
    st.session_state[FILTER_KEY] = value


def clear_conversation_filter() -> None:
    set_conversation_filter(None)


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
