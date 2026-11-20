from __future__ import annotations

import pytest
from google.api_core.exceptions import NotFound

from config import Settings
from services.feedback_store import FeedbackStore, FeedbackStoreError
from services.search_classifier import (
    classify_subject,
    normalize_question,
    question_hash,
    subject_hash,
)


class FakeClient:
    def __init__(self, errors: list[list[dict]] | None = None) -> None:
        self.calls: list[tuple[str, list[dict], list[str] | None]] = []
        self.errors = errors or []

    def insert_rows_json(self, table_id, rows, row_ids=None):
        self.calls.append((table_id, rows, row_ids))
        return self.errors.pop(0) if self.errors else []


class MissingTableClient(FakeClient):
    def insert_rows_json(self, table_id, rows, row_ids=None):
        raise NotFound("table missing")


class FakeResult:
    def result(self) -> None:
        return None


class FakeSetupClient:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.created_tables: list[object] = []

    def dataset(self, dataset_id: str) -> "FakeSetupClient":
        return self

    def table(self, name: str) -> str:
        return f"p.d.{name}"

    def create_dataset(self, dataset: object, exists_ok: bool = False) -> object:
        return dataset

    def create_table(self, table: object, exists_ok: bool = False) -> object:
        self.created_tables.append(table)
        return table

    def query(self, sql: str) -> FakeResult:
        self.queries.append(sql)
        return FakeResult()


class FakeBigQueryService:
    def __init__(self, responses: list[list[dict]]) -> None:
        self.responses = responses
        self.sqls: list[str] = []

    def table(self, name: str) -> str:
        return f"`p.d.{name}`"

    def query(self, sql: str, parameters=None, max_rows=None):
        self.sqls.append(sql)
        return self.responses.pop(0)


def _settings() -> Settings:
    return Settings(
        project_id="p",
        dataset="d",
        location="US",
        timeout_seconds=30,
        max_bytes_billed=1,
        max_rows=10,
    )


def test_normalize_question_removes_accents_and_punctuation() -> None:
    assert normalize_question("  Qual foi o faturamento?  ") == "qual foi o faturamento"


def test_classify_subject_uses_keywords_and_tools() -> None:
    assert classify_subject("Como o faturamento evoluiu por mês?") == "tendencia"
    assert classify_subject("Quais as maiores concessionárias?", ["get_ranking"]) == "ranking"
    assert classify_subject("Compare 2025 com 2026", ["compare_periods"]) == "comparacao"
    assert classify_subject("algo aleatório") == "outro"


def test_hashes_are_stable_and_separate_subjects() -> None:
    assert question_hash("Faturamento total!") == question_hash("faturamento total")
    assert subject_hash("faturamento", ["get_kpi"]) == subject_hash("faturamento", ["get_kpi"])
    assert subject_hash("faturamento", ["get_kpi"]) != subject_hash("faturamento", ["get_trend"])


def test_save_event_uses_events_table_and_generated_id() -> None:
    client = FakeClient()
    store = FeedbackStore(settings=_settings(), dataset_id="analytics_ops", client=client)

    event_id = store.save_event(
        session_id="sessao-1",
        question="Qual foi o faturamento?",
        question_hash="q1",
        subject="faturamento",
        subject_hash="s1",
        tools_used=["get_kpi"],
        response_ms=1200,
        repeat_count=2,
        status="sucesso",
        model="gpt-4.1-mini",
    )

    table_id, rows, row_ids = client.calls[0]
    assert table_id == "p.analytics_ops.chat_events"
    assert rows[0]["event_id"] == event_id
    assert rows[0]["repeat_count"] == 2
    assert row_ids == [event_id]


def test_save_event_raises_on_insert_errors() -> None:
    client = FakeClient(errors=[[{"index": 0, "errors": [{"reason": "invalid"}]}]])
    store = FeedbackStore(settings=_settings(), dataset_id="analytics_ops", client=client)

    with pytest.raises(FeedbackStoreError, match="evento"):
        store.save_event(
            session_id="sessao-1",
            question="Pergunta",
            question_hash="q",
            subject="outro",
            subject_hash="s",
            tools_used=[],
            response_ms=1,
            repeat_count=0,
            status="sucesso",
            model="test",
        )


def test_save_event_wraps_bigquery_table_not_found() -> None:
    store = FeedbackStore(
        settings=_settings(), dataset_id="analytics_ops", client=MissingTableClient()
    )

    with pytest.raises(FeedbackStoreError, match="tabela de evento de busca"):
        store.save_event(
            session_id="sessao-1",
            question="Pergunta",
            question_hash="q",
            subject="outro",
            subject_hash="s",
            tools_used=[],
            response_ms=1,
            repeat_count=0,
            status="sucesso",
            model="test",
        )


def test_save_feedback_validates_rating() -> None:
    client = FakeClient()
    store = FeedbackStore(settings=_settings(), dataset_id="analytics_ops", client=client)

    with pytest.raises(FeedbackStoreError, match="Nota inválida"):
        store.save_feedback(event_id="e1", session_id="s1", rating="otimo")

    feedback_id = store.save_feedback(
        event_id="e1", session_id="s1", rating="resultado_errado"
    )
    table_id, rows, row_ids = client.calls[0]
    assert table_id == "p.analytics_ops.chat_feedback"
    assert rows[0]["feedback_id"] == feedback_id
    assert rows[0]["rating"] == "resultado_errado"
    assert row_ids == [feedback_id]


def test_quality_report_queries_events_and_feedback() -> None:
    fake_service = FakeBigQueryService(
        [
            [{"buscas": 10, "buscas_repetidas": 3, "repeticoes": 5, "tempo_medio_ms": 900}],
            [{"assunto": "faturamento", "buscas": 4, "repeticoes": 2}],
            [{"assunto": "faturamento", "pergunta": "Qual foi o faturamento?", "vezes": 3}],
        ]
    )
    store = FeedbackStore(settings=_settings(), dataset_id="analytics_ops")
    store._service = fake_service

    report = store.quality_report(days=30)

    assert report["resumo"][0]["buscas"] == 10
    assert report["por_assunto"][0]["assunto"] == "faturamento"
    assert len(fake_service.sqls) == 3
    assert "analytics_ops.chat_events" in fake_service.sqls[0]
    assert "analytics_ops.chat_feedback" in fake_service.sqls[1]


def test_ensure_tables_creates_interactions_view() -> None:
    setup_client = FakeSetupClient()
    store = FeedbackStore(settings=_settings(), dataset_id="d")
    store._setup_client = setup_client

    store.ensure_tables()

    assert len(setup_client.created_tables) == 2
    assert len(setup_client.queries) == 1
    sql = setup_client.queries[0]
    assert sql.startswith("CREATE OR REPLACE VIEW `p.d.vw_chat_interactions` AS")
    assert "COALESCE(n.feedback_count, 0) AS feedback_count" in sql
    assert "n.feedback_id IS NOT NULL AS tem_feedback" in sql
    assert "n.rn = 1" in sql
