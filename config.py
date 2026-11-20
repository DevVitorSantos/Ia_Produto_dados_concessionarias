from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field

DEFAULT_PROJECT_ID = "projeto-dev-410722"
DEFAULT_DATASET = "gold_clau"
DEFAULT_LOCATION = "US"
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_BYTES_BILLED = 1_000_000_000
DEFAULT_MAX_ROWS = 1_000


@dataclass(frozen=True)
class Settings:
    project_id: str
    dataset: str
    location: str
    timeout_seconds: int
    max_bytes_billed: int
    max_rows: int
    credentials_info: Mapping[str, object] | None = field(default=None, repr=False)
    credentials_path: str | None = field(default=None, repr=False)

    @property
    def dataset_prefix(self) -> str:
        return f"`{self.project_id}.{self.dataset}`"

    def table(self, name: str) -> str:
        safe_name = name.strip().strip("`")
        if not safe_name.replace("_", "").isalnum():
            raise ValueError(f"Nome de tabela inválido: {name!r}")
        return f"`{self.project_id}.{self.dataset}.{safe_name}`"


def get_secret(key: str, default: object = None) -> object:
    try:
        import streamlit as st
    except ImportError:
        return default
    try:
        value = st.secrets.get(key, default)
    except Exception:
        return default
    return default if value is None or value == "" else value


def _as_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load_settings() -> Settings:
    raw_credentials = get_secret("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    credentials_info: Mapping[str, object] | None = None
    if isinstance(raw_credentials, str) and raw_credentials.strip():
        credentials_info = json.loads(raw_credentials)
    elif isinstance(raw_credentials, Mapping):
        credentials_info = dict(raw_credentials)

    return Settings(
        project_id=str(get_secret("GCP_PROJECT_ID") or os.getenv("GCP_PROJECT_ID") or DEFAULT_PROJECT_ID),
        dataset=str(get_secret("GCP_DATASET") or os.getenv("GCP_DATASET") or DEFAULT_DATASET),
        location=str(get_secret("GCP_LOCATION") or os.getenv("GCP_LOCATION") or DEFAULT_LOCATION),
        timeout_seconds=_as_int(
            get_secret("BIGQUERY_TIMEOUT_SECONDS") or os.getenv("BIGQUERY_TIMEOUT_SECONDS"),
            DEFAULT_TIMEOUT_SECONDS,
        ),
        max_bytes_billed=_as_int(
            get_secret("BIGQUERY_MAX_BYTES_BILLED") or os.getenv("BIGQUERY_MAX_BYTES_BILLED"),
            DEFAULT_MAX_BYTES_BILLED,
        ),
        max_rows=_as_int(
            get_secret("BIGQUERY_MAX_ROWS") or os.getenv("BIGQUERY_MAX_ROWS"),
            DEFAULT_MAX_ROWS,
        ),
        credentials_info=credentials_info,
        credentials_path=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
    )
