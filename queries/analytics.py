from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from google.cloud import bigquery

from config import Settings, load_settings
from semantic_layer.loader import get_dimension, get_metric, get_schema, primary_table_columns

if TYPE_CHECKING:
    from services.bigquery_service import BigQueryService

_ALLOWED_OPERATORS = {"=", "!=", ">", ">=", "<", "<=", "IN", "NOT IN", "BETWEEN"}
_GRANULARITIES = {
    "dia": "data",
    "mes": "ano_mes",
    "trimestre": "trimestre",
    "ano": "ano",
}


class AnalyticsError(ValueError):
    pass


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _filter_summary(filters: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [
        {
            "dimensao": item.get("dimension"),
            "operador": item.get("operator"),
            "valor": item.get("value"),
        }
        for item in filters or []
    ]


def _parse_date(value: str | None, field: str) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise AnalyticsError(f"{field} deve estar no formato AAAA-MM-DD.") from exc


def _sql_type(declared_type: str) -> str:
    return {
        "INTEGER": "INT64",
        "DATE": "DATE",
        "BOOLEAN": "BOOL",
    }.get(declared_type, "STRING")


def _convert_value(value: Any, declared_type: str) -> Any:
    if declared_type == "INTEGER":
        return int(value)
    if declared_type == "DATE":
        return _parse_date(str(value), "valor de data")
    if declared_type == "BOOLEAN":
        if isinstance(value, bool):
            return value
        return str(value).lower() in {"1", "true", "sim", "yes"}
    return str(value)


class AnalyticsQueries:
    def __init__(self, service: BigQueryService | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()
        if service is None:
            from services.bigquery_service import BigQueryService

            service = BigQueryService(self.settings)
        self.service = service
        self.table = self.settings.table(self.settings_table_name())

    def settings_table_name(self) -> str:
        return get_schema()["primary_table"]

    def _metric_sql(self, metric_name: str) -> tuple[str, dict[str, Any]]:
        try:
            metric = get_metric(metric_name)
        except KeyError as exc:
            raise AnalyticsError(f"Métrica desconhecida: {metric_name}") from exc
        return str(metric["sql"]), metric

    def _dimension_column(self, dimension_name: str) -> tuple[str, str]:
        try:
            dimension = get_dimension(dimension_name)
        except KeyError as exc:
            raise AnalyticsError(f"Dimensão desconhecida: {dimension_name}") from exc
        return str(dimension["column"]), str(dimension.get("type", "STRING"))

    def _build_where(
        self,
        filters: list[dict[str, Any]] | None,
        start_date: str | None,
        end_date: str | None,
    ) -> tuple[str, list[bigquery.QueryParameter]]:
        clauses: list[str] = []
        parameters: list[bigquery.QueryParameter] = []

        first_date = _parse_date(start_date, "start_date")
        last_date = _parse_date(end_date, "end_date")
        if first_date:
            clauses.append("data >= @start_date")
            parameters.append(bigquery.ScalarQueryParameter("start_date", "DATE", first_date))
        if last_date:
            clauses.append("data <= @end_date")
            parameters.append(bigquery.ScalarQueryParameter("end_date", "DATE", last_date))

        for index, item in enumerate(filters or []):
            if not isinstance(item, dict):
                raise AnalyticsError("Cada filtro deve ser um objeto com dimension, operator e value.")
            dimension_name = item.get("dimension")
            operator = str(item.get("operator", "=")).upper()
            if operator not in _ALLOWED_OPERATORS:
                raise AnalyticsError(f"Operador de filtro não permitido: {operator}")
            column, declared_type = self._dimension_column(str(dimension_name))
            sql_type = _sql_type(declared_type)
            value = item.get("value")

            if operator == "BETWEEN":
                if not isinstance(value, (list, tuple)) or len(value) != 2:
                    raise AnalyticsError("Filtro BETWEEN exige exatamente dois valores.")
                start_name = f"f{index}_inicio"
                end_name = f"f{index}_fim"
                clauses.append(f"{column} BETWEEN @{start_name} AND @{end_name}")
                parameters.append(
                    bigquery.ScalarQueryParameter(
                        start_name, sql_type, _convert_value(value[0], declared_type)
                    )
                )
                parameters.append(
                    bigquery.ScalarQueryParameter(
                        end_name, sql_type, _convert_value(value[1], declared_type)
                    )
                )
            elif operator in {"IN", "NOT IN"}:
                if not isinstance(value, list) or not value:
                    raise AnalyticsError(f"Filtro {operator} exige uma lista de valores.")
                placeholders = []
                for position, element in enumerate(value):
                    name = f"f{index}_{position}"
                    placeholders.append(f"@{name}")
                    parameters.append(
                        bigquery.ScalarQueryParameter(name, sql_type, _convert_value(element, declared_type))
                    )
                clauses.append(f"{column} {operator} ({', '.join(placeholders)})")
            else:
                name = f"f{index}"
                clauses.append(f"{column} {operator} @{name}")
                parameters.append(
                    bigquery.ScalarQueryParameter(name, sql_type, _convert_value(value, declared_type))
                )

        where = " AND ".join(clauses)
        return (f"WHERE {where}" if where else ""), parameters

    def _metric_value(
        self,
        metric_name: str,
        filters: list[dict[str, Any]] | None,
        start_date: str | None,
        end_date: str | None,
    ) -> Any:
        metric_sql, _ = self._metric_sql(metric_name)
        where, parameters = self._build_where(filters, start_date, end_date)
        rows = self.service.query(
            f"SELECT {metric_sql} AS valor FROM {self.table} {where}",
            parameters=parameters,
            max_rows=1,
        )
        return rows[0]["valor"] if rows else None

    def get_kpi(
        self,
        metric: str,
        start_date: str | None = None,
        end_date: str | None = None,
        filters: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        value = self._metric_value(metric, filters, start_date, end_date)
        _, definition = self._metric_sql(metric)
        return _json_safe(
            {
                "metrica": metric,
                "label": definition.get("label", metric),
                "valor": value,
                "unidade": definition.get("unit"),
                "periodo": {"inicio": start_date, "fim": end_date},
                "filtros": _filter_summary(filters),
            }
        )

    def get_ranking(
        self,
        metric: str,
        dimension: str,
        limit: int = 10,
        start_date: str | None = None,
        end_date: str | None = None,
        filters: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        limit = int(limit)
        if not 1 <= limit <= 50:
            raise AnalyticsError("limit deve estar entre 1 e 50.")
        metric_sql, definition = self._metric_sql(metric)
        column, _ = self._dimension_column(dimension)
        where, parameters = self._build_where(filters, start_date, end_date)
        rows = self.service.query(
            f"SELECT {column} AS categoria, {metric_sql} AS valor FROM {self.table} {where} "
            f"GROUP BY categoria ORDER BY valor DESC LIMIT {limit}",
            parameters=parameters,
            max_rows=limit,
        )
        return _json_safe(
            {
                "metrica": metric,
                "label": definition.get("label", metric),
                "dimensao": dimension,
                "linhas": rows,
                "filtros": _filter_summary(filters),
            }
        )

    def compare_periods(
        self,
        metric: str,
        current_start: str,
        current_end: str,
        previous_start: str,
        previous_end: str,
        filters: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        _parse_date(current_start, "current_start")
        _parse_date(current_end, "current_end")
        _parse_date(previous_start, "previous_start")
        _parse_date(previous_end, "previous_end")

        current = self._metric_value(metric, filters, current_start, current_end)
        previous = self._metric_value(metric, filters, previous_start, previous_end)
        delta = None if current is None or previous is None else current - previous
        percentage = None if delta is None or not previous else delta / previous
        return _json_safe(
            {
                "metrica": metric,
                "periodo_atual": {"inicio": current_start, "fim": current_end, "valor": current},
                "periodo_anterior": {"inicio": previous_start, "fim": previous_end, "valor": previous},
                "variacao_absoluta": delta,
                "variacao_percentual": percentage,
                "filtros": _filter_summary(filters),
            }
        )

    def get_trend(
        self,
        metric: str,
        granularity: str = "mes",
        start_date: str | None = None,
        end_date: str | None = None,
        filters: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if granularity not in _GRANULARITIES:
            raise AnalyticsError(f"Granularidade inválida: {granularity}")
        metric_sql, definition = self._metric_sql(metric)
        period_column = _GRANULARITIES[granularity]
        where, parameters = self._build_where(filters, start_date, end_date)
        rows = self.service.query(
            f"SELECT {period_column} AS periodo, {metric_sql} AS valor FROM {self.table} {where} "
            "GROUP BY periodo ORDER BY periodo",
            parameters=parameters,
        )
        return _json_safe(
            {
                "metrica": metric,
                "label": definition.get("label", metric),
                "granularidade": granularity,
                "linhas": rows,
                "filtros": _filter_summary(filters),
            }
        )

    def get_filtered_data(
        self,
        columns: list[str] | None = None,
        filters: list[dict[str, Any]] | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        limit = int(limit)
        if not 1 <= limit <= 100:
            raise AnalyticsError("limit deve estar entre 1 e 100.")
        available = primary_table_columns()
        selected = columns or ["data", "id_venda", "valor_pago", "cliente", "modelo", "vendedor"]
        invalid = [column for column in selected if column not in available]
        if invalid:
            raise AnalyticsError(f"Colunas não permitidas: {', '.join(invalid)}")
        where, parameters = self._build_where(filters, None, None)
        parameters.append(bigquery.ScalarQueryParameter("limit", "INT64", limit))
        rows = self.service.query(
            f"SELECT {', '.join(selected)} FROM {self.table} {where} LIMIT @limit",
            parameters=parameters,
            max_rows=limit,
        )
        return _json_safe(
            {
                "linhas": rows,
                "quantidade": len(rows),
                "filtros": _filter_summary(filters),
            }
        )
