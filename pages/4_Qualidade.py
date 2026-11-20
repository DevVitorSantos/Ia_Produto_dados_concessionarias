from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from services.feedback_store import FeedbackStore, FeedbackStoreError

st.set_page_config(page_title="Qualidade", page_icon="Q", layout="wide")
st.title("Qualidade e repetição das buscas")
st.caption("Análise de buscas repetidas e notas dadas pelo usuário nas respostas do Chat IA.")


def main() -> None:
    days = st.sidebar.slider("Período", min_value=7, max_value=90, value=30, step=7)

    try:
        report = FeedbackStore().quality_report(days=days)
    except FeedbackStoreError as exc:
        st.error(f"Não foi possível carregar o relatório: {exc}")
        return

    summary = report["resumo"]
    if summary:
        item = summary[0]
        metrics = st.columns(4)
        metrics[0].metric("Buscas", int(item.get("buscas") or 0))
        metrics[1].metric("Buscas repetidas", int(item.get("buscas_repetidas") or 0))
        metrics[2].metric("Repetições", int(item.get("repeticoes") or 0))
        metrics[3].metric("Tempo médio (ms)", int(item.get("tempo_medio_ms") or 0))

    by_subject = pd.DataFrame(report["por_assunto"])
    st.subheader("Por assunto")
    if by_subject.empty:
        st.info("Ainda não há buscas registradas no período.")
    else:
        st.dataframe(by_subject, width="stretch", hide_index=True)
        figure = go.Figure()
        figure.add_trace(
            go.Bar(x=by_subject["assunto"], y=by_subject["repeticoes"], name="Repetições")
        )
        figure.add_trace(
            go.Bar(
                x=by_subject["assunto"],
                y=by_subject["resultado_errado"],
                name="Resultado errado",
            )
        )
        figure.update_layout(barmode="group", height=420, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(figure, width="stretch")

    st.subheader("Buscas mais refeitas")
    repeated = pd.DataFrame(report["repetidas"])
    if repeated.empty:
        st.info("Nenhuma busca foi repetida no período.")
    else:
        st.dataframe(repeated, width="stretch", hide_index=True)


main()
