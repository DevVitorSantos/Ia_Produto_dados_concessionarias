import json

import pytest

import config as config_module
from config import Settings, load_settings
from services.bigquery_service import UnsafeQueryError, validate_read_only_sql


def test_settings_defaults():
    settings = Settings(
        project_id="projeto-dev-410722",
        dataset="gold_clau",
        location="US",
        timeout_seconds=30,
        max_bytes_billed=1_000_000_000,
        max_rows=1_000,
    )
    assert settings.table("vw_fato_completa") == "`projeto-dev-410722.gold_clau.vw_fato_completa`"
    assert settings.dataset_prefix == "`projeto-dev-410722.gold_clau`"


def test_settings_rejects_invalid_table_name():
    settings = load_settings()
    with pytest.raises(ValueError):
        settings.table("vw_fato; DROP TABLE x")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "WITH base AS (SELECT 1 AS x) SELECT * FROM base",
        "SELECT 'DROP TABLE x' AS texto",
        "SELECT data FROM `projeto-dev-410722.gold_clau.vw_fato_completa` -- UPDATE",
    ],
)
def test_read_only_sql_accepts_safe_queries(sql):
    assert validate_read_only_sql(sql) == sql.strip()


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM `projeto-dev-410722.gold_clau.fato_vendas`",
        "SELECT 1; DROP TABLE x",
        "SELECT 1 WHERE 1 = 1; SELECT 2",
        "CREATE TABLE x AS SELECT 1",
    ],
)
def test_read_only_sql_rejects_unsafe_queries(sql):
    with pytest.raises(UnsafeQueryError):
        validate_read_only_sql(sql)


def test_load_settings_accepts_service_account_json_in_credentials_env(monkeypatch):
    payload = {"type": "service_account", "project_id": "projeto-dev-410722"}
    monkeypatch.setattr(config_module, "get_secret", lambda key, default=None: default)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", raising=False)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", json.dumps(payload))

    settings = config_module.load_settings()

    assert settings.credentials_info == payload
    assert settings.credentials_path is None


def test_load_settings_ignores_placeholder_credentials_path(monkeypatch):
    monkeypatch.setattr(config_module, "get_secret", lambda key, default=None: default)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", raising=False)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "caminho/para/service-account.json")

    settings = config_module.load_settings()

    assert settings.credentials_info is None
    assert settings.credentials_path is None
