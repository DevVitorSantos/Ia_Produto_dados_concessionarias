from __future__ import annotations

from typing import Any, Callable

import pandas as pd
import streamlit as st

from ui.charts import build_combined_figure, build_figure
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
    results: list[dict[str, Any]] | None,
    *,
    key_prefix: str = "tool-results",
    show_charts: bool = True,
    show_tables: bool = True,
    show_details: bool = True,
    table_expanded: bool = False,
    combine_charts: bool = True,
    max_charts: int = 3,
    max_tables: int = 5,
) -> None:
    all_results = list(results or [])
    consumed_charts: set[int] = set()
    charts_shown = 0
    tables_shown = 0

    if show_charts and combine_charts:
        combined = build_combined_figure(all_results)
        if combined is not None:
            figure, consumed_charts = combined
            st.plotly_chart(
                figure,
                theme="streamlit",
                width="stretch",
                key=f"{key_prefix}-combined",
            )
            charts_shown += 1

    if show_tables and len(all_results) > max_tables:
        st.caption(
            f"Exibindo as primeiras {max_tables} tabelas de {len(all_results)} resultados disponíveis."
        )

    for index, result in enumerate(all_results):
        tool = result.get("ferramenta", "ferramenta")
        if "erro" in result:
            st.error(f"{tool}: {result['erro']}")
            continue

        if show_charts and "valor" in result and "metrica" in result and len(result) <= 8:
            render_metric_cards({str(result["metrica"]): result["valor"]})

        if show_charts and index not in consumed_charts and charts_shown < max_charts:
            figure = build_figure(result)
            if figure is not None:
                st.plotly_chart(
                    figure,
                    theme="streamlit",
                    width="stretch",
                    key=f"{key_prefix}-{index}",
                )
                charts_shown += 1

        if not show_tables or tables_shown >= max_tables:
            continue

        rows = result.get("linhas")
        if isinstance(rows, list) and rows:
            with st.expander(f"Tabela — {tool}", expanded=table_expanded):
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            tables_shown += 1
        elif "valor" in result and "metrica" in result:
            proof = pd.DataFrame(
                [{metric_label(str(result["metrica"])): result["valor"]}]
            )
            st.dataframe(proof, width="stretch", hide_index=True)
            tables_shown += 1

        if show_details and result.get("periodo_atual"):
            with st.expander(f"Detalhes — {tool}", expanded=False):
                st.json(result)


def render_suggestions(
    suggestions: list[Any] | None,
    *,
    key_prefix: str,
    on_select: Callable[[str], None],
) -> None:
    items: list[tuple[str, str]] = []
    for item in suggestions or []:
        if isinstance(item, dict):
            label = str(item.get("rotulo") or item.get("pergunta") or "").strip()
            question = str(item.get("pergunta") or label).strip()
        elif isinstance(item, str):
            label = item.strip()
            question = label
        else:
            continue
        if label and question:
            items.append((label, question))
    if not items:
        st.caption("Nenhuma sugestão adicional para este recorte.")
        return

    columns = st.columns(min(2, len(items)))
    for column, (label, question), index in zip(columns, items, range(len(items))):
        with column:
            if st.button(label, key=f"{key_prefix}-suggestion-{index}", width="stretch"):
                on_select(question)
                st.rerun()
