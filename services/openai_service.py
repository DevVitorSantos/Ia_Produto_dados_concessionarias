from __future__ import annotations

import json
import os
import uuid
from typing import Any

from openai import OpenAI

from agent.instructions import INSTRUCTIONS
from agent.tools import ToolExecutor, tool_schemas
from config import get_secret
from services.response_service import RESPONSE_SERVICE, AssistantAnswer

DEFAULT_MODEL = "gpt-6-luna"
MAX_TOOL_ROUNDS = 6


def _dump_item(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        return item.model_dump(exclude_none=True)
    return dict(item)


class OpenAIService:
    def __init__(
        self,
        tool_executor: ToolExecutor | None = None,
        client: Any | None = None,
        model: str | None = None,
    ) -> None:
        self.tool_executor = tool_executor or ToolExecutor()
        api_key = get_secret("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        if client is None and not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY não configurada. Defina a variável de ambiente ou .streamlit/secrets.toml."
            )
        self.client = client or OpenAI(api_key=str(api_key))
        self.model = str(model or get_secret("OPENAI_MODEL") or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL)
        self.tools = tool_schemas()

    def ask(self, question: str, history: list[Any] | None = None) -> AssistantAnswer:
        event_id = str(uuid.uuid4())
        input_items: list[Any] = [_dump_item(item) for item in (history or [])]
        input_items.append({"role": "user", "content": question})
        tool_outputs: list[str] = []
        tool_results: list[dict[str, Any]] = []

        for _ in range(MAX_TOOL_ROUNDS):
            response = self.client.responses.create(
                model=self.model,
                instructions=INSTRUCTIONS,
                input=input_items,
                tools=self.tools,
                store=False,
            )
            if getattr(response, "status", "completed") != "completed":
                raise RuntimeError(f"Resposta OpenAI finalizada com status {response.status}")

            output_items = list(getattr(response, "output", []))
            input_items.extend(_dump_item(item) for item in output_items)
            calls = [item for item in output_items if getattr(item, "type", None) == "function_call"]

            if not calls:
                text = str(getattr(response, "output_text", "") or "")
                return RESPONSE_SERVICE.build(
                    text,
                    tools_used=self.tool_executor.last_calls,
                    tool_outputs=tool_outputs,
                    tool_results=tool_results,
                    event_id=event_id,
                )

            for call in calls:
                try:
                    arguments = json.loads(call.arguments)
                except (TypeError, ValueError):
                    arguments = {}
                result = self.tool_executor.execute(call.name, arguments)
                tool_outputs.append(result)
                try:
                    parsed = json.loads(result)
                except (TypeError, ValueError):
                    parsed = {"resultado": result}
                if isinstance(parsed, dict):
                    tool_results.append({"ferramenta": call.name, **parsed})
                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": result,
                    }
                )

        raise RuntimeError("Limite de rodadas de ferramentas atingido.")
