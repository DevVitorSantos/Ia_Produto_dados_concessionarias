from __future__ import annotations

import pandas as pd
import streamlit as st

from ui.state import clear_conversation, init_state

st.set_page_config(page_title="Histórico", page_icon="H", layout="wide")
st.title("Histórico da sessão")
st.caption("Perguntas, respostas e ferramentas utilizadas durante esta sessão.")

init_state()
messages = st.session_state["chat_messages"]

if not messages:
    st.info("Ainda não há mensagens nesta sessão. Use a página **Chat IA** para começar.")
else:
    rows = []
    for index, message in enumerate(messages, start=1):
        if message.get("role") != "user":
            continue
        answer = None
        for following in messages[index:]:
            if following.get("role") == "assistant":
                answer = following.get("answer") or {}
                break
        rows.append(
            {
                "#": index,
                "Pergunta": message.get("content", ""),
                "Resposta": (answer.get("resposta") if answer else "") or "",
                "Ferramentas": ", ".join((answer or {}).get("ferramentas_utilizadas", [])),
                "Avisos": "; ".join((answer or {}).get("avisos", [])),
            }
        )

    dataframe = pd.DataFrame(rows)
    st.dataframe(dataframe, width="stretch", hide_index=True)
    st.download_button(
        "Baixar histórico CSV",
        data=dataframe.to_csv(index=False).encode("utf-8-sig"),
        file_name="historico_chat_ia.csv",
        mime="text/csv",
    )

    st.subheader("Conversa completa")
    for message in messages:
        with st.expander(f"{message['role'].capitalize()} — {message['content'][:70]}"):
            st.markdown(message["content"])
            answer = message.get("answer")
            if answer:
                st.caption("Ferramentas: " + ", ".join(answer.get("ferramentas_utilizadas", [])))
                for warning in answer.get("avisos", []):
                    st.warning(warning)

    if st.button("Limpar histórico", type="secondary", width="stretch"):
        clear_conversation()
        st.rerun()

st.caption("Esta visão é a sessão atual. Eventos persistentes de uso ficam no BigQuery; veja a página Qualidade.")
