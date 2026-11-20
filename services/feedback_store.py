from __future__ import annotations

import os
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from google.api_core.exceptions import GoogleAPIError, NotFound
from google.auth.exceptions import GoogleAuthError
from google.cloud import bigquery
from google.oauth2 import service_account

from config import Settings, get_secret, load_settings
from services.bigquery_service import BigQueryService, BigQueryServiceError

EVENTS_TABLE = "chat_events"
FEEDBACK_TABLE = "chat_feedback"
VALID_RATINGS = ("satisfatoria", "duvidas", "resultado_errado")

EVENT_SCHEMA = (
    bigquery.SchemaField("event_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("session_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("question", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("question_hash", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("subject", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("subject_hash", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("tools_used", "STRING", mode="REPEATED"),
    bigquery.SchemaField("response_ms", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("repeat_count", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("model", "STRING", mode="REQUIRED"),
)

FEEDBACK_SCHEMA = (
    bigquery.SchemaField("feedback_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("event_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("session_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("rating", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("comment", "STRING"),
)


class FeedbackStoreError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class FeedbackStore:
    def __init__(
        self,
        settings: Settings | None = None,
        dataset_id: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.dataset_id = str(
            dataset_id
            or get_secret("FEEDBACK_DATASET")
            or os.getenv("FEEDBACK_DATASET")
            or "analytics_ops"
        )
        self._service = BigQueryService(self.settings)
        self._client = client
        self._setup_client: bigquery.Client | None = None

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = self._service.client
        return self._client

    @property
    def setup_client(self) -> bigquery.Client:
        if self._setup_client is None:
            if self.settings.credentials_info:
                credentials = service_account.Credentials.from_service_account_info(
                    dict(self.settings.credentials_info)
                )
            elif self.settings.credentials_path:
                credentials = service_account.Credentials.from_service_account_file(
                    self.settings.credentials_path
                )
            else:
                credentials = None
            self._setup_client = bigquery.Client(
                project=self.settings.project_id,
                credentials=credentials,
                location=self.settings.location,
            )
        return self._setup_client

    def events_table_id(self) -> str:
        return f"{self.settings.project_id}.{self.dataset_id}.{EVENTS_TABLE}"

    def feedback_table_id(self) -> str:
        return f"{self.settings.project_id}.{self.dataset_id}.{FEEDBACK_TABLE}"

    def _qualified_table(self, name: str) -> str:
        return f"`{self.settings.project_id}.{self.dataset_id}.{name}`"

    def _table_for_insert(self, name: str, schema: tuple[Any, ...]) -> Any:
        table_id = f"{self.settings.project_id}.{self.dataset_id}.{name}"
        client = self.client
        # Keep lightweight test doubles compatible; the production client
        # returns a Table resource, avoiding ambiguity in insertAll table IDs.
        if not hasattr(client, "get_table"):
            return table_id
        try:
            return client.get_table(table_id)
        except NotFound:
            try:
                return self._create_table_for_insert(name, schema)
            except (GoogleAPIError, GoogleAuthError) as exc:
                raise FeedbackStoreError(
                    f"A tabela {table_id} não foi encontrada e não pôde ser criada. "
                    "Confirme as permissões no dataset e execute o setup de rastreamento."
                ) from exc
        except (GoogleAPIError, GoogleAuthError) as exc:
            raise FeedbackStoreError(
                f"Não foi possível acessar a tabela {table_id}: {exc}"
            ) from exc

    def _create_table_for_insert(
        self, name: str, schema: tuple[Any, ...]
    ) -> bigquery.Table:
        table_ref = self.client.dataset(
            self.dataset_id, project=self.settings.project_id
        ).table(name)
        return self.client.create_table(
            bigquery.Table(table_ref, schema=list(schema)), exists_ok=True
        )

    def _insert_rows(
        self,
        table_name: str,
        schema: tuple[Any, ...],
        row: dict[str, Any],
        row_id: str,
        error_label: str,
    ) -> None:
        table = self._table_for_insert(table_name, schema)
        try:
            errors = self.client.insert_rows_json(table, [row], row_ids=[row_id])
        except NotFound as exc:
            try:
                table = self._create_table_for_insert(table_name, schema)
                errors = self.client.insert_rows_json(table, [row], row_ids=[row_id])
            except (GoogleAPIError, GoogleAuthError, AttributeError) as retry_exc:
                raise FeedbackStoreError(
                    f"A tabela de {error_label} não foi localizada no BigQuery. "
                    "Confirme o projeto/dataset configurado e execute o setup de rastreamento."
                ) from retry_exc
        except (GoogleAPIError, GoogleAuthError) as exc:
            raise FeedbackStoreError(
                f"Falha ao salvar {error_label} no BigQuery: {exc}"
            ) from exc
        if errors:
            raise FeedbackStoreError(f"Falha ao salvar {error_label}: {errors}")

    def ensure_tables(self) -> None:
        dataset = self.setup_client.dataset(self.dataset_id)
        self.setup_client.create_dataset(dataset, exists_ok=True)
        self.setup_client.create_table(
            bigquery.Table(dataset.table(EVENTS_TABLE), schema=list(EVENT_SCHEMA)),
            exists_ok=True,
        )
        self.setup_client.create_table(
            bigquery.Table(dataset.table(FEEDBACK_TABLE), schema=list(FEEDBACK_SCHEMA)),
            exists_ok=True,
        )

    def save_event(
        self,
        *,
        session_id: str,
        question: str,
        question_hash: str,
        subject: str,
        subject_hash: str,
        tools_used: Iterable[str],
        response_ms: int,
        repeat_count: int,
        status: str,
        model: str,
        event_id: str | None = None,
    ) -> str:
        resolved_event_id = event_id or str(uuid.uuid4())
        row = {
            "event_id": resolved_event_id,
            "created_at": _now(),
            "session_id": session_id,
            "question": question,
            "question_hash": question_hash,
            "subject": subject,
            "subject_hash": subject_hash,
            "tools_used": list(dict.fromkeys(tools_used)),
            "response_ms": int(response_ms),
            "repeat_count": int(repeat_count),
            "status": status,
            "model": model,
        }
        self._insert_rows(
            EVENTS_TABLE,
            EVENT_SCHEMA,
            row,
            resolved_event_id,
            "evento de busca",
        )
        return resolved_event_id

    def save_feedback(
        self,
        *,
        event_id: str,
        session_id: str,
        rating: str,
        comment: str = "",
    ) -> str:
        if rating not in VALID_RATINGS:
            raise FeedbackStoreError(f"Nota inválida: {rating}")
        feedback_id = str(uuid.uuid4())
        row = {
            "feedback_id": feedback_id,
            "event_id": event_id,
            "created_at": _now(),
            "session_id": session_id,
            "rating": rating,
            "comment": comment or None,
        }
        self._insert_rows(
            FEEDBACK_TABLE,
            FEEDBACK_SCHEMA,
            row,
            feedback_id,
            "feedback",
        )
        return feedback_id

    def quality_report(self, days: int = 30) -> dict[str, list[dict[str, Any]]]:
        events = self._qualified_table(EVENTS_TABLE)
        feedback = self._qualified_table(FEEDBACK_TABLE)
        window = f"TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {int(days)} DAY)"

        summary_sql = f"""
        SELECT
          COUNT(*) AS buscas,
          COUNTIF(repeat_count > 0) AS buscas_repetidas,
          SUM(repeat_count) AS repeticoes,
          ROUND(AVG(response_ms)) AS tempo_medio_ms
        FROM {events}
        WHERE created_at >= {window}
        """
        subject_sql = f"""
        WITH notas AS (
          SELECT
            event_id,
            rating,
            ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY created_at DESC) AS rn
          FROM {feedback}
          WHERE created_at >= {window}
        )
        SELECT
          e.subject AS assunto,
          COUNT(*) AS buscas,
          COUNTIF(e.repeat_count > 0) AS buscas_repetidas,
          SUM(e.repeat_count) AS repeticoes,
          COUNTIF(n.rating = 'satisfatoria') AS satisfatorias,
          COUNTIF(n.rating = 'duvidas') AS duvidas,
          COUNTIF(n.rating = 'resultado_errado') AS resultado_errado,
          ROUND(AVG(e.response_ms)) AS tempo_medio_ms
        FROM {events} AS e
        LEFT JOIN notas AS n ON n.event_id = e.event_id AND n.rn = 1
        WHERE e.created_at >= {window}
        GROUP BY e.subject
        ORDER BY repeticoes DESC, buscas DESC
        """
        repeated_sql = f"""
        SELECT
          e.subject AS assunto,
          e.question AS pergunta,
          COUNT(*) AS vezes,
          COUNTIF(n.rating = 'resultado_errado') AS resultado_errado,
          COUNTIF(n.rating = 'duvidas') AS duvidas
        FROM {events} AS e
        LEFT JOIN (
          SELECT
            event_id,
            rating,
            ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY created_at DESC) AS rn
          FROM {feedback}
        ) AS n ON n.event_id = e.event_id AND n.rn = 1
        WHERE e.created_at >= {window} AND e.repeat_count > 0
        GROUP BY e.subject, e.question
        ORDER BY vezes DESC
        """
        try:
            return {
                "resumo": self._service.query(summary_sql),
                "por_assunto": self._service.query(subject_sql),
                "repetidas": self._service.query(repeated_sql),
            }
        except BigQueryServiceError as exc:
            raise FeedbackStoreError(str(exc)) from exc
