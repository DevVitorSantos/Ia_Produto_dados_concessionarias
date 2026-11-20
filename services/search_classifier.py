from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable

SUBJECT_RULES: dict[str, tuple[str, ...]] = {
    "faturamento": ("faturamento", "receita", "total", "valor", "ticket medio", "ticket médio"),
    "vendas": ("venda", "vendas", "unidades", "quantidade", "volume"),
    "desconto": ("desconto", "descontos", "percentual", "percentual desconto"),
    "ranking": ("ranking", "top", "melhores", "piores", "maiores", "menores", "ordem"),
    "tendencia": ("tendencia", "tendência", "evolucao", "evolução", "evoluiu", "mensal", "por mes", "por mês"),
    "comparacao": ("compare", "comparar", "comparacao", "comparação", "versus", "contra"),
    "cliente": ("cliente", "clientes", "consumidor"),
    "concessionaria": ("concessionaria", "concessionárias", "loja", "unidade"),
    "veiculo": ("veiculo", "veículos", "carro", "modelo", "marca"),
    "vendedor": ("vendedor", "vendedores", "equipe", "time de vendas"),
    "periodo": ("periodo", "período", "ano", "mes", "mês", "data", "entre"),
}

TOOL_SUBJECTS: dict[str, str] = {
    "get_kpi": "faturamento",
    "get_ranking": "ranking",
    "compare_periods": "comparacao",
    "get_trend": "tendencia",
    "get_filtered_data": "vendas",
}


def _strip_accents(value: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFD", value) if unicodedata.category(char) != "Mn"
    )


def normalize_question(question: str) -> str:
    value = _strip_accents(question).lower().strip()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def question_hash(question: str) -> str:
    return _digest(normalize_question(question))


def subject_hash(subject: str, tools_used: Iterable[str] | None = None) -> str:
    tools = sorted(set(tools_used or []))
    return _digest(f"{subject}|{','.join(tools)}")


def classify_subject(question: str, tools_used: Iterable[str] | None = None) -> str:
    normalized = normalize_question(question)
    scores: dict[str, float] = {subject: 0.0 for subject in SUBJECT_RULES}

    for subject, keywords in SUBJECT_RULES.items():
        for keyword in keywords:
            pattern = rf"\b{re.escape(normalize_question(keyword))}\b"
            scores[subject] += len(re.findall(pattern, normalized))

    for tool in set(tools_used or []):
        subject = TOOL_SUBJECTS.get(tool)
        if subject:
            scores[subject] += 0.5

    best = max(scores, key=lambda subject: (scores[subject], -list(SUBJECT_RULES).index(subject)))
    if scores[best] == 0:
        return "outro"
    return best
