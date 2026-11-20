from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from google.api_core.exceptions import GoogleAPIError
from google.auth.exceptions import GoogleAuthError
from google.cloud import bigquery
from google.oauth2 import service_account

from config import Settings, load_settings

_ALLOWED_FIRST_KEYWORDS = {"SELECT", "WITH"}
_FORBIDDEN_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "MERGE",
    "CREATE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "CALL",
    "EXECUTE",
    "SCRIPT",
    "EXPORT",
    "LOAD",
    "COPY",
}


class BigQueryServiceError(RuntimeError):
    pass


class UnsafeQueryError(BigQueryServiceError):
    pass


class ConfigurationError(BigQueryServiceError):
    pass


def _remove_literals_and_comments(sql: str) -> str:
    text = re.sub(r"--[^\n]*", " ", sql)
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    text = re.sub(r"'(?:''|\\.|[^'])*'", " ", text)
    text = re.sub(r'"(?:\\.|[^"])*"', " ", text)
    text = re.sub(r"`(?:``|[^`])*`", " ", text)
    return text


def validate_read_only_sql(sql: str) -> str:
    if not isinstance(sql, str) or not sql.strip():
        raise UnsafeQueryError("A consulta SQL está vazia.")

    cleaned = _remove_literals_and_comments(sql)
    statements = [part.strip() for part in cleaned.split(";") if part.strip()]
    if len(statements) != 1:
        raise UnsafeQueryError("Apenas uma instrução SELECT/WITH é permitida por consulta.")

    tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", cleaned.upper())
    if not tokens or tokens[0] not in _ALLOWED_FIRST_KEYWORDS:
        raise UnsafeQueryError("A consulta deve começar com SELECT ou WITH.")

    forbidden = sorted(set(tokens) & _FORBIDDEN_KEYWORDS)
    if forbidden:
        raise UnsafeQueryError(f"Operação não permitida: {', '.join(forbidden)}.")

    return sql.strip()


class BigQueryService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()
        self._client: bigquery.Client | None = None

    @property
    def client(self) -> bigquery.Client:
        if self._client is None:
            try:
                credentials = None
                if self.settings.credentials_info:
                    credentials = service_account.Credentials.from_service_account_info(
                        dict(self.settings.credentials_info)
                    )
                elif self.settings.credentials_path:
                    credentials = service_account.Credentials.from_service_account_file(
                        self.settings.credentials_path
                    )
                self._client = bigquery.Client(
                    project=self.settings.project_id,
                    credentials=credentials,
                    location=self.settings.location,
                )
            except (GoogleAuthError, ValueError) as exc:
                raise ConfigurationError(
                    f"Não foi possível autenticar no BigQuery: {type(exc).__name__}: {exc}"
                ) from exc
        return self._client

    def query(
        self,
        sql: str,
        *,
        parameters: Sequence[bigquery.QueryParameter] | None = None,
        max_rows: int | None = None,
        timeout_seconds: int | None = None,
    ) -> list[dict[str, Any]]:
        safe_sql = validate_read_only_sql(sql)
        timeout = timeout_seconds or self.settings.timeout_seconds
        limit = max_rows or self.settings.max_rows

        job_config = bigquery.QueryJobConfig(
            query_parameters=list(parameters or []),
            maximum_bytes_billed=self.settings.max_bytes_billed,
            use_query_cache=True,
            job_timeout_ms=timeout * 1000,
        )

        try:
            job = self.client.query(
                safe_sql,
                job_config=job_config,
                location=self.settings.location,
                timeout=timeout,
            )
            rows: list[dict[str, Any]] = []
            for row in job.result(timeout=timeout):
                if len(rows) >= limit:
                    break
                rows.append(dict(row.items()))
            return rows
        except (GoogleAPIError, GoogleAuthError, ValueError) as exc:
            raise BigQueryServiceError(
                f"Falha ao consultar BigQuery: {type(exc).__name__}: {exc}"
            ) from exc

    def validate_connection(self) -> list[dict[str, Any]]:
        return self.query("SELECT 1 AS ok")

    def list_gold_objects(self) -> list[dict[str, Any]]:
        information_schema = f"{self.settings.dataset_prefix}.INFORMATION_SCHEMA.TABLES"
        return self.query(
            f"SELECT table_name, table_type FROM {information_schema} ORDER BY table_name"
        )

    def count_sales(self) -> list[dict[str, Any]]:
        table = self.settings.table("vw_fato_completa")
        return self.query(
            f"""
            SELECT
              COUNT(*) AS total_vendas,
              COUNT(DISTINCT id_venda) AS vendas_distintas,
              SUM(valor_pago) AS faturamento,
              MIN(data) AS primeira_data,
              MAX(data) AS ultima_data
            FROM {table}
            """
        )

    def revenue_by_year(self) -> list[dict[str, Any]]:
        table = self.settings.table("vw_fato_completa")
        return self.query(
            f"""
            SELECT
              EXTRACT(YEAR FROM data) AS ano,
              COUNT(*) AS vendas,
              SUM(valor_pago) AS faturamento
            FROM {table}
            GROUP BY ano
            ORDER BY ano
            """
        )

    def discount_profile(self) -> list[dict[str, Any]]:
        table = self.settings.table("vw_fato_completa")
        return self.query(
            f"""
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN valor_desconto < 0 THEN 1 ELSE 0 END) AS desconto_negativo,
              SUM(CASE WHEN valor_desconto > 0 THEN 1 ELSE 0 END) AS desconto_positivo,
              MIN(percentual_desconto) AS min_percentual,
              MAX(percentual_desconto) AS max_percentual
            FROM {table}
            """
        )

    def dimension_key_check(self) -> list[dict[str, Any]]:
        project_dataset = self.settings.dataset_prefix
        return self.query(
            f"""
            SELECT 'dim_tempo' AS dimensao, COUNT(*) AS total, COUNT(DISTINCT id_tempo) AS chaves FROM {project_dataset}.dim_tempo
            UNION ALL SELECT 'dim_cliente', COUNT(*), COUNT(DISTINCT id_cliente) FROM {project_dataset}.dim_cliente
            UNION ALL SELECT 'dim_veiculo', COUNT(*), COUNT(DISTINCT id_veiculo) FROM {project_dataset}.dim_veiculo
            UNION ALL SELECT 'dim_vendedor', COUNT(*), COUNT(DISTINCT id_vendedor) FROM {project_dataset}.dim_vendedor
            UNION ALL SELECT 'dim_concessionaria', COUNT(*), COUNT(DISTINCT id_concessionaria) FROM {project_dataset}.dim_concessionaria
            """
        )

    def run_smoke_checks(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "conexao": self.validate_connection(),
            "objetos_gold": self.list_gold_objects(),
            "vendas": self.count_sales(),
            "por_ano": self.revenue_by_year(),
            "desconto": self.discount_profile(),
            "chaves": self.dimension_key_check(),
        }
