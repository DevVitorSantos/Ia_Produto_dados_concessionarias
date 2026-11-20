from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from ui.charts import build_figure
from ui.format import format_metric, metric_label


def render_metric_cards(values: dict[str, Any], columns: int = 3) -> None:
    items = [(metric_label(metric), format_metric(metric, value)) for metric, value in values.items()]
    if not items:
        st.info("Nenhum indicador selecionado.")
        return
    for start in range(0, len(items), columns):
        cells = st.columns(columns)
        for cell, (label, formatted) in zip(cells, items[start : start + columns]):
            with cell:
                st.metric(label, formatted)


def render_tool_results(
    results: list[dict[str, Any]] | None, *, key_prefix: str = "tool-results"
) -> None:
    for index, result in enumerate(results or []):
        tool = result.get("ferramenta", "ferramenta")
        if "erro" in result:
            st.error(f"{tool}: {result['erro']}")
            continue

        if "valor" in result and "metrica" in result and len(result) <= 8:
            render_metric_cards({str(result["metrica"]): result["valor"]})
            continue

        figure = build_figure(result)
        if figure is not None:
            st.plotly_chart(
                figure,
                theme="streamlit",
                width="stretch",
                key=f"{key_prefix}-{index}",
            )

        rows = result.get("linhas")
        if isinstance(rows, list) and rows:
            with st.expander(f"Tabela — {tool}", expanded=False):
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

        if result.get("periodo_atual"):
            with st.expander(f"Detalhes — {tool}", expanded=False):
                st.json(result)
