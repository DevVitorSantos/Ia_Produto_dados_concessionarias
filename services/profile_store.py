from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from google.api_core.exceptions import GoogleAPIError, NotFound
from google.auth.exceptions import GoogleAuthError
from google.cloud import bigquery
from google.oauth2 import service_account

from config import Settings, get_secret, load_settings
from services.bigquery_service import BigQueryService, BigQueryServiceError

PROFILE_TABLE = "chat_user_profiles"
COOKIE_TTL_DAYS = 7
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

PROFILE_SCHEMA = (
    bigquery.SchemaField("profile_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("updated_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("nome", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("email", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("cargo", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("setor", "STRING", mode="REQUIRED"),
)


class ProfileStoreError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_profile(
    nome: object,
    email: object,
    cargo: object,
    setor: object,
) -> dict[str, str]:
    values = {
        "nome": str(nome or "").strip(),
        "email": str(email or "").strip().lower(),
        "cargo": str(cargo or "").strip(),
        "setor": str(setor or "").strip(),
    }
    if any(not value for value in values.values()):
        raise ValueError("Preencha nome, e-mail, cargo e setor.")
    if not _EMAIL_RE.match(values["email"]):
        raise ValueError("Informe um e-mail válido.")
    if any(len(value) > 200 for value in values.values()):
        raise ValueError("Os campos devem ter até 200 caracteres.")
    return values


def profile_is_fresh(profile: object, days: int = COOKIE_TTL_DAYS) -> bool:
    if not isinstance(profile, dict):
        return False
    updated_at = profile.get("updated_at")
    if isinstance(updated_at, str):
        try:
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        except ValueError:
            return False
    if not isinstance(updated_at, datetime):
        return False
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - updated_at
    return timedelta(0) <= age <= timedelta(days=days)


class ProfileStore:
    def __init__(
        self,
        settings: Settings | None = None,
        dataset_id: str | None = None,
        client: Any | None = None,
        setup_client: Any | None = None,
        service: Any | None = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.dataset_id = str(
            dataset_id
            or get_secret("FEEDBACK_DATASET")
            or os.getenv("FEEDBACK_DATASET")
            or "analytics_ops"
        )
        self._service = service or BigQueryService(self.settings)
        self._client = client
        self._setup_client = setup_client

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = self._service.client
        return self._client

    @property
    def setup_client(self) -> Any:
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

    def table_id(self) -> str:
        return f"{self.settings.project_id}.{self.dataset_id}.{PROFILE_TABLE}"

    def _qualified_table(self) -> str:
        return f"`{self.table_id()}`"

    def ensure_table(self) -> None:
        dataset = self.setup_client.dataset(self.dataset_id)
        self.setup_client.create_dataset(dataset, exists_ok=True)
        self.setup_client.create_table(
            bigquery.Table(dataset.table(PROFILE_TABLE), schema=list(PROFILE_SCHEMA)),
            exists_ok=True,
        )

    def get_profile(self, profile_id: str) -> dict[str, Any] | None:
        clean_id = str(profile_id or "").strip()
        if not clean_id:
            return None
        sql = f"""
        SELECT
          profile_id,
          created_at,
          updated_at,
          nome,
          email,
          cargo,
          setor
        FROM {self._qualified_table()}
        WHERE profile_id = @profile_id
        """
        try:
            rows = self._service.query(
                sql,
                parameters=[
                    bigquery.ScalarQueryParameter("profile_id", "STRING", clean_id)
                ],
            )
        except BigQueryServiceError as exc:
            raise ProfileStoreError(str(exc)) from exc
        return rows[0] if rows else None

    def save_profile(
        self,
        *,
        profile_id: str | None = None,
        nome: object,
        email: object,
        cargo: object,
        setor: object,
    ) -> dict[str, Any]:
        values = normalize_profile(nome, email, cargo, setor)
        resolved_id = str(profile_id or uuid.uuid4())
        created_at = _now()
        updated_at = created_at

        sql = f"""
        MERGE {self._qualified_table()} AS T
        USING (
          SELECT
            @profile_id AS profile_id,
            @created_at AS created_at,
            @updated_at AS updated_at,
            @nome AS nome,
            @email AS email,
            @cargo AS cargo,
            @setor AS setor
        ) AS S
        ON T.profile_id = S.profile_id
        WHEN MATCHED THEN UPDATE SET
          updated_at = S.updated_at,
          nome = S.nome,
          email = S.email,
          cargo = S.cargo,
          setor = S.setor
        WHEN NOT MATCHED THEN INSERT
          (profile_id, created_at, updated_at, nome, email, cargo, setor)
        VALUES
          (S.profile_id, S.created_at, S.updated_at, S.nome, S.email, S.cargo, S.setor)
        """
        parameters = [
            bigquery.ScalarQueryParameter("profile_id", "STRING", resolved_id),
            bigquery.ScalarQueryParameter("created_at", "TIMESTAMP", created_at),
            bigquery.ScalarQueryParameter("updated_at", "TIMESTAMP", updated_at),
            bigquery.ScalarQueryParameter("nome", "STRING", values["nome"]),
            bigquery.ScalarQueryParameter("email", "STRING", values["email"]),
            bigquery.ScalarQueryParameter("cargo", "STRING", values["cargo"]),
            bigquery.ScalarQueryParameter("setor", "STRING", values["setor"]),
        ]
        job_config = bigquery.QueryJobConfig(query_parameters=parameters)

        try:
            self.client.query(sql, job_config=job_config).result()
        except NotFound:
            self.ensure_table()
            try:
                self.client.query(sql, job_config=job_config).result()
            except (GoogleAPIError, GoogleAuthError, AttributeError) as exc:
                raise ProfileStoreError(
                    f"Não foi possível salvar o perfil em {self.table_id()}: {exc}"
                ) from exc
        except (GoogleAPIError, GoogleAuthError, AttributeError) as exc:
            raise ProfileStoreError(
                f"Não foi possível salvar o perfil em {self.table_id()}: {exc}"
            ) from exc

        return {
            "profile_id": resolved_id,
            "created_at": created_at,
            "updated_at": updated_at,
            **values,
        }
