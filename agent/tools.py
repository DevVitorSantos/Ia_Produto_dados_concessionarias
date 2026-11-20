from __future__ import annotations

import json
from typing import Any

from queries.analytics import AnalyticsQueries
from semantic_layer.loader import get_dimensions, get_metrics, primary_table_columns

_METRICS = sorted(get_metrics()["metrics"])
_DIMENSIONS = sorted(get_dimensions()["dimensions"])
_COLUMNS = sorted(primary_table_columns())
_OPERATORS = ["=", "!=", ">", ">=", "<", "<=", "IN", "NOT IN", "BETWEEN"]


def _filter_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "dimension": {"type": "string", "enum": _DIMENSIONS},
            "operator": {"type": "string", "enum": _OPERATORS},
            "value": {"type": ["string", "number", "boolean", "array"]},
        },
        "required": ["dimension", "operator", "value"],
        "additionalProperties": False,
    }


def _common_properties() -> dict[str, Any]:
    return {
        "start_date": {"type": "string", "description": "Data inicial AAAA-MM-DD."},
        "end_date": {"type": "string", "description": "Data final AAAA-MM-DD."},
        "filters": {"type": "array", "items": _filter_schema()},
    }


def tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": "get_kpi",
            "description": "Retorna o valor de uma métrica oficial, opcionalmente filtrada por período e dimensões.",
            "parameters": {
                "type": "object",
                "properties": {"metric": {"type": "string", "enum": _METRICS}, **_common_properties()},
                "required": ["metric"],
                "additionalProperties": False,
            },
            "strict": False,
        },
        {
            "type": "function",
            "name": "get_ranking",
            "description": "Retorna ranking de uma métrica por dimensão, ordenado do maior para o menor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string", "enum": _METRICS},
                    "dimension": {"type": "string", "enum": _DIMENSIONS},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    **_common_properties(),
                },
                "required": ["metric", "dimension"],
                "additionalProperties": False,
            },
            "strict": False,
        },
        {
            "type": "function",
            "name": "compare_periods",
            "description": "Compara uma métrica entre dois períodos e calcula variação absoluta e percentual.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string", "enum": _METRICS},
                    "current_start": {"type": "string", "description": "Início do período atual AAAA-MM-DD."},
                    "current_end": {"type": "string", "description": "Fim do período atual AAAA-MM-DD."},
                    "previous_start": {"type": "string", "description": "Início do período anterior AAAA-MM-DD."},
                    "previous_end": {"type": "string", "description": "Fim do período anterior AAAA-MM-DD."},
                    "filters": {"type": "array", "items": _filter_schema()},
                },
                "required": ["metric", "current_start", "current_end", "previous_start", "previous_end"],
                "additionalProperties": False,
            },
            "strict": False,
        },
        {
            "type": "function",
            "name": "get_trend",
            "description": "Retorna série temporal de uma métrica por dia, mês, trimestre ou ano.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string", "enum": _METRICS},
                    "granularity": {"type": "string", "enum": ["dia", "mes", "trimestre", "ano"]},
                    **_common_properties(),
                },
                "required": ["metric"],
                "additionalProperties": False,
            },
            "strict": False,
        },
        {
            "type": "function",
            "name": "get_filtered_data",
            "description": "Retorna linhas agregadas ou detalhadas de colunas permitidas da view Gold, com filtros opcionais.",
            "parameters": {
                "type": "object",
                "properties": {
                    "columns": {"type": "array", "items": {"type": "string", "enum": _COLUMNS}},
                    "filters": {"type": "array", "items": _filter_schema()},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "additionalProperties": False,
            },
            "strict": False,
        },
    ]


class ToolExecutor:
    def __init__(self, analytics: AnalyticsQueries | None = None) -> None:
        self._analytics = analytics
        self.last_calls: list[str] = []

    @property
    def analytics(self) -> AnalyticsQueries:
        if self._analytics is None:
            self._analytics = AnalyticsQueries()
        return self._analytics

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        self.last_calls.append(name)
        handlers = {
            "get_kpi": self.analytics.get_kpi,
            "get_ranking": self.analytics.get_ranking,
            "compare_periods": self.analytics.compare_periods,
            "get_trend": self.analytics.get_trend,
            "get_filtered_data": self.analytics.get_filtered_data,
        }
        handler = handlers.get(name)
        if handler is None:
            return json.dumps({"erro": f"Ferramenta desconhecida: {name}"}, ensure_ascii=False)
        try:
            result = handler(**arguments)
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as exc:
            return json.dumps(
                {"erro": str(exc), "tipo": type(exc).__name__},
                ensure_ascii=False,
            )


TOOL_EXECUTOR = ToolExecutor()
