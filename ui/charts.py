from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px

from ui.format import metric_label


def _title(result: dict[str, Any], suffix: str) -> str:
    metric = result.get("metrica")
    label = metric_label(str(metric)) if metric else ""
    return f"{label} — {suffix}" if label else suffix


def trend_figure(result: dict[str, Any]):
    rows = result.get("linhas") or []
    if not rows:
        return None
    dataframe = pd.DataFrame(rows)
    if "periodo" not in dataframe or "valor" not in dataframe:
        return None
    figure = px.line(
        dataframe,
        x="periodo",
        y="valor",
        markers=True,
        title=_title(result, str(result.get("granularidade", "tendência")).title()),
    )
    figure.update_layout(margin=dict(l=20, r=20, t=50, b=20), hovermode="x unified")
    return figure


def ranking_figure(result: dict[str, Any]):
    rows = result.get("linhas") or []
    if not rows:
        return None
    dataframe = pd.DataFrame(rows).head(15)
    if "categoria" not in dataframe or "valor" not in dataframe:
        return None
    figure = px.bar(
        dataframe,
        x="valor",
        y="categoria",
        orientation="h",
        title=_title(result, f"por {result.get('dimensao', 'dimensão')}"),
    )
    figure.update_layout(margin=dict(l=20, r=20, t=50, b=20), yaxis={"categoryorder": "total ascending"})
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
    figure = px.bar(
        dataframe,
        x="periodo",
        y="valor",
        title=_title(result, "comparação de períodos"),
    )
    figure.update_layout(margin=dict(l=20, r=20, t=50, b=20))
    return figure


def build_figure(result: dict[str, Any]):
    if result.get("granularidade"):
        return trend_figure(result)
    if result.get("dimensao"):
        return ranking_figure(result)
    if result.get("periodo_atual"):
        return comparison_figure(result)
    return None
