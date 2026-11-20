from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AnswerSections:
    resumo: str = ""
    resposta: str = ""
    prova: str = ""
    sugestoes: list[dict[str, str]] = field(default_factory=list)


@dataclass
class AssistantAnswer:
    text: str
    secoes: AnswerSections = field(default_factory=AnswerSections)
    tools_used: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    event_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "resposta": self.text,
            "secoes": asdict(self.secoes),
            "sugestoes": self.secoes.sugestoes,
            "ferramentas_utilizadas": self.tools_used,
            "avisos": self.avisos,
            "resultados": self.tool_results,
            "event_id": self.event_id,
        }


DEFAULT_SUGGESTIONS = [
    {"rotulo": "Ver evolução mensal", "pergunta": "Como o faturamento evoluiu por mês?"},
    {
        "rotulo": "Ver ranking de concessionárias",
        "pergunta": "Quais foram as 10 concessionárias com maior faturamento?",
    },
    {"rotulo": "Comparar períodos", "pergunta": "Compare o faturamento de 2025 com o de 2026."},
]


def _extract_json(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(cleaned[start : end + 1])
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _normalize_suggestions(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    suggestions: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, dict):
            label = str(item.get("rotulo") or item.get("label") or item.get("titulo") or "").strip()
            question = str(item.get("pergunta") or item.get("question") or "").strip()
        elif isinstance(item, str):
            label = item.strip()
            question = item.strip()
        else:
            continue
        if not label or not question:
            continue
        suggestions.append({"rotulo": label[:80], "pergunta": question[:300]})
        if len(suggestions) == 4:
            break
    return suggestions


def _fallback_suggestions(tool_results: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    results = tool_results or []
    suggestions: list[dict[str, str]] = []
    if any("granularidade" in result for result in results):
        suggestions.append(DEFAULT_SUGGESTIONS[2])
    if any("dimensao" in result for result in results):
        suggestions.append(DEFAULT_SUGGESTIONS[0])
    if any("periodo_atual" in result for result in results):
        suggestions.append(DEFAULT_SUGGESTIONS[1])
    if not suggestions:
        suggestions = list(DEFAULT_SUGGESTIONS[:2])
    return suggestions[:3]


def parse_sections(
    text: str,
    *,
    tool_results: list[dict[str, Any]] | None = None,
) -> AnswerSections:
    data = _extract_json(text) or {}
    resumo = str(data.get("resumo") or "").strip()
    resposta = str(data.get("resposta") or "").strip()
    prova = str(data.get("prova") or "").strip()
    sugestoes = _normalize_suggestions(data.get("sugestoes") or data.get("sugestões"))

    if not any((resumo, resposta, prova)):
        resumo = text.strip()
        resposta = "O gráfico abaixo resume os dados consultados."
        prova = "Tabela de referência gerada a partir da consulta."
    else:
        resposta = resposta or "O gráfico abaixo resume os dados consultados."
        prova = prova or "Tabela de referência gerada a partir da consulta."

    if not sugestoes:
        sugestoes = _fallback_suggestions(tool_results)

    return AnswerSections(
        resumo=resumo,
        resposta=resposta,
        prova=prova,
        sugestoes=sugestoes,
    )


class ResponseService:
    def build(
        self,
        text: str,
        tools_used: list[str] | None = None,
        tool_outputs: list[str] | None = None,
        tool_results: list[dict[str, Any]] | None = None,
        event_id: str = "",
    ) -> AssistantAnswer:
        avisos: list[str] = []
        joined = " ".join(tool_outputs or [])
        if "Cliente #" in joined:
            avisos.append(
                "Alguns resultados usam rótulos sintéticos 'Cliente #' porque o cliente não foi encontrado em dim_cliente."
            )
        results = list(tool_results or [])
        secoes = parse_sections(text, tool_results=results)
        return AssistantAnswer(
            text=secoes.resumo or secoes.resposta,
            secoes=secoes,
            tools_used=list(dict.fromkeys(tools_used or [])),
            avisos=avisos,
            tool_results=results,
            event_id=event_id,
        )


RESPONSE_SERVICE = ResponseService()
