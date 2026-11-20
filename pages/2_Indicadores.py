from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from queries.analytics import AnalyticsQueries
from semantic_layer.loader import get_dimensions, get_metrics
from ui.charts import build_figure
from ui.components import render_metric_cards

st.set_page_config(page_title="Indicadores", page_icon="I", layout="wide")
st.title("Indicadores")
st.caption("KPIs oficiais calculados diretamente da view Gold, sem SQL livre.")

st.session_state.setdefault("indicadores", None)

metrics = get_metrics()["metrics"]
dimensions = get_dimensions()["dimensions"]
default_metrics = [
    "faturamento_total",
    "quantidade_vendas",
    "ticket_medio",
    "desconto_medio",
    "veiculos_vendidos",
]
default_metrics = [metric for metric in default_metrics if metric in metrics]

with st.sidebar:
    st.header("Filtros")
    period = st.date_input("Período", value=(date(2025, 1, 1), date(2026, 7, 2)))
    if isinstance(period, (tuple, list)) and len(period) == 2:
        start_date, end_date = period
    else:
        start_date = end_date = period

    selected_metrics = st.multiselect(
        "Métricas",
        options=sorted(metrics),
        default=default_metrics,
        format_func=lambda key: str(metrics[key].get("label", key)),
    )
    filter_dimension = st.selectbox(
        "Filtrar por",
        options=["Todos", "concessionaria", "vendedor", "cidade", "estado", "modelo", "categoria_desconto"],
        format_func=lambda key: "Todos" if key == "Todos" else str(dimensions[key].get("label", key)),
    )
    filter_value = st.text_input("Valor do filtro", disabled=filter_dimension == "Todos")
    load = st.button("Carregar indicadores", type="primary", width="stretch")

if load:
    try:
        analytics = AnalyticsQueries()
        filters: list[dict[str, Any]] = []
        if filter_dimension != "Todos" and filter_value.strip():
            filters.append(
                {"dimension": filter_dimension, "operator": "=", "value": filter_value.strip()}
            )
        start = start_date.isoformat()
        end = end_date.isoformat()

        values = {
            metric: analytics.get_kpi(metric, start, end, filters)["valor"]
            for metric in selected_metrics
        }
        main_metric = selected_metrics[0] if selected_metrics else "faturamento_total"
        trend = analytics.get_trend(main_metric, "mes", start, end, filters)
        ranking = analytics.get_ranking(
            main_metric,
            "concessionaria",
            limit=10,
            start_date=start,
            end_date=end,
            filters=filters,
        )
        st.session_state["indicadores"] = {
            "valores": values,
            "tendencia": trend,
            "ranking": ranking,
            "metrica_principal": main_metric,
        }
    except Exception as exc:
        st.error(f"Não foi possível carregar os indicadores: {exc}")

result = st.session_state.get("indicadores")
if result:
    render_metric_cards(result["valores"], columns=3)
    st.subheader("Evolução mensal")
    figure = build_figure(result["tendencia"])
    if figure:
        st.plotly_chart(figure, theme="streamlit", width="stretch")
    else:
        st.info("Sem dados para o período selecionado.")

    st.subheader("Ranking por concessionária")
    ranking = result["ranking"]
    figure = build_figure(ranking)
    if figure:
        st.plotly_chart(figure, theme="streamlit", width="stretch")
    if ranking.get("linhas"):
        dataframe = pd.DataFrame(ranking["linhas"])
        st.dataframe(dataframe, width="stretch", hide_index=True)
        st.download_button(
            "Baixar ranking CSV",
            data=dataframe.to_csv(index=False).encode("utf-8-sig"),
            file_name="ranking_concessionarias.csv",
            mime="text/csv",
        )
else:
    st.info("Escolha os filtros e clique em **Carregar indicadores**.")
