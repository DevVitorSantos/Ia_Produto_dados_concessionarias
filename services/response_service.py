from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AssistantAnswer:
    text: str
    tools_used: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    event_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "resposta": self.text,
            "ferramentas_utilizadas": self.tools_used,
            "avisos": self.avisos,
            "resultados": self.tool_results,
            "event_id": self.event_id,
        }


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
        return AssistantAnswer(
            text=text,
            tools_used=list(dict.fromkeys(tools_used or [])),
            avisos=avisos,
            tool_results=list(tool_results or []),
            event_id=event_id,
        )


RESPONSE_SERVICE = ResponseService()
