from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from google.api_core.exceptions import NotFound

from config import Settings
from services.profile_store import (
    PROFILE_TABLE,
    ProfileStore,
    normalize_profile,
    profile_is_fresh,
)


class FakeResult:
    def result(self) -> None:
        return None


class FakeClient:
    def __init__(self, errors: list[Exception] | None = None) -> None:
        self.calls: list[tuple[str, object]] = []
        self.errors = list(errors or [])

    def query(self, sql: str, job_config: object = None) -> FakeResult:
        self.calls.append((sql, job_config))
        if self.errors:
            error = self.errors.pop(0)
            if error:
                raise error
        return FakeResult()


class FakeSetupClient:
    def __init__(self) -> None:
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


class FakeService:
    def __init__(self, rows: list[dict] | None = None) -> None:
        self.rows = rows or []
        self.calls: list[tuple[str, object]] = []

    def query(self, sql: str, *, parameters=None, max_rows=None):
        self.calls.append((sql, parameters))
        return self.rows


def _settings() -> Settings:
    return Settings(
        project_id="p",
        dataset="d",
        location="US",
        timeout_seconds=30,
        max_bytes_billed=1,
        max_rows=10,
    )


def test_normalize_profile_trims_and_validates() -> None:
    profile = normalize_profile(" Ana ", " USER@Example.com ", "Analista", "Vendas")
    assert profile == {
        "nome": "Ana",
        "email": "user@example.com",
        "cargo": "Analista",
        "setor": "Vendas",
    }
    with pytest.raises(ValueError):
        normalize_profile("", "user@example.com", "Analista", "Vendas")
    with pytest.raises(ValueError):
        normalize_profile("Ana", "invalido", "Analista", "Vendas")


def test_profile_is_fresh_respects_seven_days() -> None:
    now = datetime.now(timezone.utc)
    fresh = now.isoformat().replace("+00:00", "Z")
    stale = (now - timedelta(days=8)).isoformat().replace("+00:00", "Z")
    assert profile_is_fresh({"updated_at": fresh})
    assert not profile_is_fresh({"updated_at": stale})
    assert not profile_is_fresh({})


def test_get_profile_uses_parameterized_query() -> None:
    row = {"profile_id": "abc", "nome": "Ana", "email": "user@example.com"}
    service = FakeService([row])
    store = ProfileStore(
        settings=_settings(),
        dataset_id="d",
        service=service,
        client=FakeClient(),
    )

    result = store.get_profile(" abc ")

    assert result == row
    sql, parameters = service.calls[0]
    assert "WHERE profile_id = @profile_id" in sql
    assert parameters[0].name == "profile_id"
    assert parameters[0].value == "abc"


def test_save_profile_uses_merge_and_normalizes_values() -> None:
    client = FakeClient()
    store = ProfileStore(settings=_settings(), dataset_id="d", client=client)

    profile = store.save_profile(
        profile_id="abc",
        nome=" Ana ",
        email=" USER@Example.com ",
        cargo="Analista",
        setor="Vendas",
    )

    sql, job_config = client.calls[0]
    assert sql.strip().startswith("MERGE")
    assert f"p.d.{PROFILE_TABLE}" in sql
    values = {item.name: item.value for item in job_config.query_parameters}
    assert values["profile_id"] == "abc"
    assert values["email"] == "user@example.com"
    assert profile["profile_id"] == "abc"


def test_save_profile_creates_table_when_missing() -> None:
    client = FakeClient([NotFound("missing")])
    setup_client = FakeSetupClient()
    store = ProfileStore(
        settings=_settings(),
        dataset_id="d",
        client=client,
        setup_client=setup_client,
    )

    store.save_profile(
        profile_id="abc",
        nome="Ana",
        email="user@example.com",
        cargo="Analista",
        setor="Vendas",
    )

    assert len(client.calls) == 2
    assert len(setup_client.created_tables) == 1
