from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px

from ui.format import format_metric, format_value, metric_label

BLUE = "#2563EB"
GREEN = "#16A34A"
GRAY = "#94A3B8"
CHART_COLORS = [
    BLUE,
    GREEN,
    "#F59E0B",
    "#7C3AED",
    "#EC4899",
    "#0EA5E9",
    "#64748B",
    "#14B8A6",
]


def _series_label(result: dict[str, Any], index: int) -> str:
    filters = result.get("filtros") or []
    if filters:
        return ", ".join(
            f"{item.get('dimensao')}={item.get('valor')}" for item in filters
        )
    return str(result.get("label") or result.get("metrica") or f"Série {index + 1}")


def _title(result: dict[str, Any], suffix: str) -> str:
    metric = result.get("metrica")
    label = metric_label(str(metric)) if metric else ""
    return f"{label} — {suffix}" if label else suffix


def _metric_name(result: dict[str, Any]) -> str:
    metric = result.get("metrica")
    return metric_label(str(metric)) if metric else "Valor"


def _formatted_values(result: dict[str, Any], values: pd.Series) -> list[str]:
    metric = result.get("metrica")
    if metric:
        return [format_metric(str(metric), value) for value in values]
    return [format_value(value) for value in values]


def trend_figure(result: dict[str, Any]):
    rows = result.get("linhas") or []
    if not rows:
        return None
    dataframe = pd.DataFrame(rows)
    if "periodo" not in dataframe or "valor" not in dataframe:
        return None
    metric_name = _metric_name(result)
    figure = px.line(
        dataframe,
        x="periodo",
        y="valor",
        text=_formatted_values(result, dataframe["valor"]),
        markers=True,
        color_discrete_sequence=[BLUE],
        labels={"periodo": "Período", "valor": metric_name},
        title=_title(result, str(result.get("granularidade", "tendência")).title()),
    )
    figure.update_traces(
        textposition="top center",
        line=dict(width=3),
        marker=dict(size=8),
    )
    figure.update_layout(
        margin=dict(l=20, r=20, t=60, b=40),
        hovermode="x unified",
        xaxis_title="Período",
        yaxis_title=metric_name,
    )
    return figure


def ranking_figure(result: dict[str, Any]):
    rows = result.get("linhas") or []
    if not rows:
        return None
    dataframe = pd.DataFrame(rows).head(15)
    if "categoria" not in dataframe or "valor" not in dataframe:
        return None
    dimension = str(result.get("dimensao") or "Categoria")
    metric_name = _metric_name(result)
    figure = px.bar(
        dataframe,
        x="valor",
        y="categoria",
        orientation="h",
        text=_formatted_values(result, dataframe["valor"]),
        color="valor",
        color_continuous_scale="Blues",
        labels={"categoria": dimension.title(), "valor": metric_name},
        title=_title(result, f"por {result.get('dimensao', 'dimensão')}"),
    )
    figure.update_traces(textposition="outside", cliponaxis=False)
    figure.update_layout(
        margin=dict(l=20, r=40, t=60, b=40),
        xaxis_title=metric_name,
        yaxis_title="",
        yaxis={"categoryorder": "total ascending"},
        coloraxis_showscale=False,
    )
    return figure


def comparison_figure(result: dict[str, Any]):
    current = result.get("periodo_atual") or {}
    previous = result.get("periodo_anterior") or {}
    dataframe = pd.DataFrame(
        [
            {"periodo": "Atual", "valor": current.get("valor")},
            {"periodo": "Anterior", "valor": previous.get("valor")},
        ]
    )
    if dataframe["valor"].isna().all():
        return None
    metric_name = _metric_name(result)
    figure = px.bar(
        dataframe,
        x="periodo",
        y="valor",
        text=_formatted_values(result, dataframe["valor"]),
        color="periodo",
        color_discrete_sequence=[GREEN, GRAY],
        labels={"periodo": "Período", "valor": metric_name},
        title=_title(result, "comparação de períodos"),
    )
    figure.update_traces(textposition="outside", cliponaxis=False)
    figure.update_layout(
        margin=dict(l=20, r=20, t=60, b=40),
        xaxis_title="Período",
        yaxis_title=metric_name,
    )
    return figure


def build_combined_figure(results: list[dict[str, Any]] | None):
    candidates: list[tuple[int, dict[str, Any]]] = [
        (index, result)
        for index, result in enumerate(results or [])
        if result.get("granularidade") and result.get("linhas")
    ]
    if len(candidates) < 2:
        return None

    frames: list[pd.DataFrame] = []
    consumed: set[int] = set()
    for index, result in candidates:
        dataframe = pd.DataFrame(result["linhas"])
        if not {"periodo", "valor"}.issubset(dataframe.columns):
            continue
        series = dataframe[["periodo", "valor"]].copy()
        series["serie"] = _series_label(result, index)
        frames.append(series)
        consumed.add(index)

    if len(frames) < 2:
        return None

    combined = pd.concat(frames, ignore_index=True)
    base = candidates[0][1]
    metric_name = _metric_name(base)
    figure = px.line(
        combined,
        x="periodo",
        y="valor",
        color="serie",
        text=_formatted_values(base, combined["valor"]),
        markers=True,
        color_discrete_sequence=CHART_COLORS,
        labels={"periodo": "Período", "valor": metric_name, "serie": "Recorte"},
        title=_title(base, str(base.get("granularidade", "tendência")).title()),
    )
    figure.update_traces(
        textposition="top center",
        line=dict(width=2),
        marker=dict(size=6),
    )
    figure.update_layout(
        margin=dict(l=20, r=20, t=60, b=60),
        hovermode="x unified",
        xaxis_title="Período",
        yaxis_title=metric_name,
        legend_title="Recorte",
    )
    return figure, consumed


def build_figure(result: dict[str, Any]):
    if result.get("granularidade"):
        return trend_figure(result)
    if result.get("dimensao"):
        return ranking_figure(result)
    if result.get("periodo_atual"):
        return comparison_figure(result)
    return None
