from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

SEMANTIC_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=None)
def _read_yaml(filename: str) -> dict[str, Any]:
    path = SEMANTIC_DIR / filename
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Arquivo semântico inválido: {filename}")
    return data


@lru_cache(maxsize=None)
def get_schema() -> dict[str, Any]:
    return _read_yaml("schema.yaml")


@lru_cache(maxsize=None)
def get_metrics() -> dict[str, Any]:
    return _read_yaml("metrics.yaml")


@lru_cache(maxsize=None)
def get_dimensions() -> dict[str, Any]:
    return _read_yaml("dimensions.yaml")


@lru_cache(maxsize=None)
def get_business_rules() -> dict[str, Any]:
    return _read_yaml("business_rules.yaml")


def get_metric(name: str) -> dict[str, Any]:
    try:
        return get_metrics()["metrics"][name]
    except KeyError as exc:
        raise KeyError(f"Métrica desconhecida: {name}") from exc


def get_dimension(name: str) -> dict[str, Any]:
    try:
        return get_dimensions()["dimensions"][name]
    except KeyError as exc:
        raise KeyError(f"Dimensão desconhecida: {name}") from exc


def primary_table_columns() -> dict[str, Any]:
    schema = get_schema()
    table = schema["tables"][schema["primary_table"]]
    return table["columns"]


def validate_semantic_layer() -> list[str]:
    errors: list[str] = []
    try:
        schema = get_schema()
        metrics = get_metrics()["metrics"]
        dimensions = get_dimensions()["dimensions"]
        rules = get_business_rules()["rules"]
    except Exception as exc:
        return [f"Falha ao carregar camada semântica: {exc}"]

    primary_name = schema.get("primary_table")
    tables = schema.get("tables", {})
    if primary_name not in tables:
        return [f"Tabela principal ausente no schema: {primary_name}"]

    primary = tables[primary_name]
    columns = primary.get("columns", {})
    expected_columns = schema.get("validation", {}).get("expected_columns")
    if expected_columns is not None and len(columns) != expected_columns:
        errors.append(
            f"Esperadas {expected_columns} colunas na tabela principal; encontradas {len(columns)}."
        )

    if primary.get("primary_key") not in columns:
        errors.append("Chave primária da tabela principal não está entre as colunas.")

    for relationship in schema.get("relationships", []):
        for field in ("from_column", "to_table", "to_column", "join_type"):
            if not relationship.get(field):
                errors.append(f"Relacionamento sem campo {field}: {relationship}")
        if relationship.get("from_column") not in columns:
            errors.append(f"Coluna de origem inexistente: {relationship.get('from_column')}")

    for name, metric in metrics.items():
        sql = str(metric.get("sql", "")).strip()
        if not sql:
            errors.append(f"Métrica {name} sem SQL definida.")
        declared_column = metric.get("column")
        if declared_column and declared_column not in columns:
            errors.append(f"Métrica {name} usa coluna inexistente: {declared_column}")
        referenced = set(re.findall(r"\b[a-z][a-z0-9_]*\b", sql.lower())) & set(columns)
        if not referenced:
            errors.append(f"Métrica {name} não referencia colunas conhecidas do schema.")

    for name, dimension in dimensions.items():
        column_name = dimension.get("column")
        if column_name not in columns:
            errors.append(f"Dimensão {name} usa coluna inexistente: {column_name}")
            continue
        declared_type = dimension.get("type")
        if declared_type and declared_type != columns[column_name]["type"]:
            errors.append(
                f"Dimensão {name} declara {declared_type}, mas o schema indica "
                f"{columns[column_name]['type']}."
            )

    rule_ids = [rule.get("id") for rule in rules]
    if len(rule_ids) != len(set(rule_ids)):
        errors.append("Existem IDs de regras duplicados.")

    for rule in rules:
        for field in ("id", "rule", "action", "severity"):
            if not rule.get(field):
                errors.append(f"Regra sem campo {field}: {rule}")

    return errors
