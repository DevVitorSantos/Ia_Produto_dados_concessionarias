from __future__ import annotations

import time
import uuid
from datetime import date
from typing import Any

import streamlit as st

from config import get_secret
from semantic_layer.loader import get_dimensions
from services.feedback_store import FeedbackStore, FeedbackStoreError
from services.openai_service import DEFAULT_MODEL, OpenAIService, describe_filter
from services.search_classifier import classify_subject, question_hash, subject_hash
from ui.components import render_suggestions, render_tool_results
from ui.profile_popup import render_profile_popup
from ui.state import (
    FEEDBACK_KEY,
    FILTER_DIMENSIONS,
    PENDING_KEY,
    SESSION_KEY,
    build_conversation_filter,
    clear_conversation,
    clear_conversation_filter,
    conversation_filter,
    history_for_api,
    init_state,
    record_feedback,
    record_message,
    repeat_count_for,
    set_conversation_filter,
)

st.set_page_config(page_title="Chat IA", page_icon="C", layout="wide")
render_profile_popup()
st.title("Chat IA")
st.caption("Perguntas em linguagem natural sobre vendas, faturamento, descontos e rankings.")

init_state()
FEEDBACK_STORE = FeedbackStore()
active_filter = conversation_filter()
if active_filter:
    st.caption(f"Filtro persistente nesta conversa: **{describe_filter(active_filter)}**")

SUGGESTIONS = [
    "Qual foi o faturamento total?",
    "Quais foram as 10 concessionárias com maior faturamento?",
    "Como o faturamento evoluiu por mês?",
    "Compare o faturamento de 2025 com o de 2026.",
]
RATINGS = (
    ("satisfatoria", "Satisfatória"),
    ("duvidas", "Tenho dúvidas"),
    ("resultado_errado", "Resultado errado"),
)


def _apply_suggestion(question: str) -> None:
    st.session_state[PENDING_KEY] = question


def _render_conversation_filter() -> dict[str, Any] | None:
    active = conversation_filter()
    if active:
        st.caption(f"Ativo: **{describe_filter(active)}**")
        if st.button("Remover filtro", key="remove_conversation_filter", width="stretch"):
            clear_conversation_filter()
            st.rerun()

    dimensions = get_dimensions()["dimensions"]
    dimension = st.selectbox(
        "Dimensão",
        options=FILTER_DIMENSIONS,
        key="conversation_filter_dimension",
        format_func=lambda key: str(dimensions.get(key, {}).get("label", key)),
    )
    if dimension == "data":
        period = st.date_input(
            "Período",
            value=(date(2025, 1, 1), date(2026, 7, 2)),
            key="conversation_filter_period",
        )
        if isinstance(period, (tuple, list)) and len(period) == 2:
            start, end = period
        elif isinstance(period, date):
            start = end = period
        else:
            start = end = None
        raw_value = [start.isoformat(), end.isoformat()] if start and end else []
        operator = "BETWEEN"
    else:
        raw_value = st.text_input("Valor", key="conversation_filter_value")
        operator = "="

    st.caption("Aplica às próximas perguntas; um novo filtro substitui o anterior.")
    if st.button(
        "Aplicar à conversa",
        type="primary",
        key="apply_conversation_filter",
        width="stretch",
    ):
        built = build_conversation_filter(dimension, raw_value, operator)
        if built is None:
            st.warning("Informe um valor válido para aplicar o filtro.")
        else:
            set_conversation_filter(built)
            st.rerun()
    return active


def _render_feedback(event_id: str) -> None:
    if not event_id:
        return
    current = st.session_state[FEEDBACK_KEY].get(event_id)
    columns = st.columns(len(RATINGS))
    for column, (value, label) in zip(columns, RATINGS):
        if column.button(
            label,
            key=f"rating_{event_id}_{value}",
            type="primary" if current == value else "secondary",
            disabled=current is not None,
            width="stretch",
        ):
            try:
                FEEDBACK_STORE.save_feedback(
                    event_id=event_id,
                    session_id=st.session_state[SESSION_KEY],
                    rating=value,
                )
                record_feedback(event_id, value)
                st.success(f"Registrado: {label}.")
            except FeedbackStoreError as exc:
                st.warning(f"Não foi possível registrar a nota: {exc}")
    if current:
        st.caption(f"Nota registrada: {dict(RATINGS).get(current, current)}.")


def _render_answer(answer: dict[str, Any], *, key_prefix: str) -> None:
    sections = answer.get("secoes") or {}
    resumo = str(sections.get("resumo") or answer.get("resposta", "")).strip()
    resposta = str(sections.get("resposta", "")).strip()
    prova = str(sections.get("prova", "")).strip()

    for warning in answer.get("avisos", []):
        st.warning(warning)

    st.markdown("### Resumo")
    st.markdown(resumo or "Consulta concluída.")

    st.markdown("### Resposta")
    if resposta:
        st.caption(resposta)
    render_tool_results(
        answer.get("resultados"),
        key_prefix=f"{key_prefix}-resposta",
        show_charts=True,
        show_tables=False,
        show_details=False,
        max_charts=3,
    )

    st.markdown("### Prova")
    if prova:
        st.caption(prova)
    render_tool_results(
        answer.get("resultados"),
        key_prefix=f"{key_prefix}-prova",
        show_charts=False,
        show_tables=True,
        show_details=True,
        table_expanded=True,
        max_tables=3,
    )

    st.markdown("### Sugestões")
    render_suggestions(
        sections.get("sugestoes") or answer.get("sugestoes"),
        key_prefix=key_prefix,
        on_select=_apply_suggestion,
    )
    _render_feedback(str(answer.get("event_id", "")))


def _save_event(
    *,
    question: str,
    tools_used: list[str],
    response_ms: int,
    repeat_count: int,
    status: str,
    event_id: str | None = None,
) -> None:
    model = str(get_secret("OPENAI_MODEL") or DEFAULT_MODEL)
    subject = classify_subject(question, tools_used)
    FEEDBACK_STORE.save_event(
        event_id=event_id,
        session_id=st.session_state[SESSION_KEY],
        question=question,
        question_hash=question_hash(question),
        subject=subject,
        subject_hash=subject_hash(subject, tools_used),
        tools_used=tools_used,
        response_ms=response_ms,
        repeat_count=repeat_count,
        status=status,
        model=model,
    )


with st.sidebar:
    st.header("Filtro persistente")
    _render_conversation_filter()
    st.divider()
    st.header("Sugestões iniciais")
    columns = st.columns(1)
    for suggestion in SUGGESTIONS:
        if st.button(suggestion, key=f"suggestion_{suggestion}", width="stretch"):
            st.session_state[PENDING_KEY] = suggestion
            st.rerun()
    if st.button("Limpar conversa", type="secondary", width="stretch"):
        clear_conversation()
        st.rerun()

for message_index, message in enumerate(st.session_state["chat_messages"]):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        answer = message.get("answer")
        if answer:
            _render_answer(
                answer,
                key_prefix=f"chat-history-{message_index}-{answer.get('event_id', 'legacy')}",
            )

prompt = st.chat_input("Digite sua pergunta sobre os dados de vendas...")
if not prompt and st.session_state.get(PENDING_KEY):
    prompt = st.session_state[PENDING_KEY]
    st.session_state[PENDING_KEY] = None

if prompt:
    history = history_for_api()
    repeat_count = repeat_count_for(prompt)
    started_at = time.perf_counter()
    with st.chat_message("user"):
        st.markdown(prompt)
    record_message("user", prompt)

    try:
        with st.spinner("Consultando os dados..."):
            answer = OpenAIService().ask(
                prompt,
                history=history,
                persistent_filter=active_filter,
            )
    except RuntimeError as exc:
        message = str(exc)
        if "OPENAI_API_KEY" in message:
            st.error(
                "Chave OpenAI não configurada. Defina `OPENAI_API_KEY` nas variáveis de ambiente "
                "ou no `.streamlit/secrets.toml`."
            )
        else:
            st.error(message)
        st.stop()
    except Exception as exc:
        st.error(f"Não foi possível responder agora: {exc}")
        st.stop()

    response_ms = int((time.perf_counter() - started_at) * 1000)
    event_id = answer.event_id or str(uuid.uuid4())
    try:
        _save_event(
            question=prompt,
            tools_used=answer.tools_used,
            response_ms=response_ms,
            repeat_count=repeat_count,
            status="sucesso",
            event_id=event_id,
        )
        answer.event_id = event_id
    except FeedbackStoreError as exc:
        st.warning(f"Resposta gerada, mas o evento não foi registrado: {exc}")

    with st.chat_message("assistant"):
        _render_answer(answer.to_dict(), key_prefix=f"chat-answer-{answer.event_id}")
    record_message("assistant", answer.text, answer)
