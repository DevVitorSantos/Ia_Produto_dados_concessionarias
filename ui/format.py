from __future__ import annotations

from typing import Any

from semantic_layer.loader import get_metric


def _br_number(value: float, decimals: int = 2) -> str:
    return f"{value:,.{decimals}f}".replace(",", "@").replace(".", ",").replace("@", ".")


def format_value(value: Any, kind: str = "text") -> str:
    if value is None:
        return "—"
    if kind == "currency_br":
        return f"R$ {_br_number(float(value))}"
    if kind == "percent_br":
        return f"{_br_number(float(value) * 100)}%"
    if kind == "integer_br":
        return f"{int(value):,}".replace(",", ".")
    return str(value)


def format_metric(metric: str, value: Any) -> str:
    definition = get_metric(metric)
    return format_value(value, str(definition.get("format", "text")))


def metric_label(metric: str) -> str:
    return str(get_metric(metric).get("label", metric))
