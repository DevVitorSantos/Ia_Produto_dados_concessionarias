from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent.instructions import INSTRUCTIONS, build_instructions
from agent.tools import tool_schemas
from queries.analytics import AnalyticsError, AnalyticsQueries
from services.openai_service import OpenAIService, describe_filter
from services.response_service import ResponseService


class FakeAnalytics:
    def get_kpi(self, **kwargs):
        self.kwargs = kwargs
        return {"metrica": kwargs["metric"], "valor": 100.0, "cliente": "Cliente #999"}


class FakeExecutor:
    def __init__(self, result: str) -> None:
        self.result = result
        self.calls: list[tuple[str, dict]] = []
        self.last_calls: list[str] = []

    def execute(self, name: str, arguments: dict) -> str:
        self.calls.append((name, arguments))
        self.last_calls.append(name)
        return self.result


class FakeItem:
    def __init__(self, **data) -> None:
        self.__dict__.update(data)

    def model_dump(self, **kwargs) -> dict:
        return dict(self.__dict__)


class FakeResponses:
    def __init__(self, responses: list) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, responses: list) -> None:
        self.responses = FakeResponses(responses)


class FakeBigQueryService:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.sql = ""
        self.parameters: list = []
        self.max_rows = None

    def query(self, sql: str, parameters=None, max_rows=None):
        self.sql = sql
        self.parameters = parameters or []
        self.max_rows = max_rows
        return self.rows


def _response(*items, text: str) -> SimpleNamespace:
    return SimpleNamespace(status="completed", output=list(items), output_text=text)


def test_tool_schemas_expose_five_official_tools() -> None:
    schemas = tool_schemas()
    assert [item["name"] for item in schemas] == [
        "get_kpi",
        "get_ranking",
        "compare_periods",
        "get_trend",
        "get_filtered_data",
    ]
    assert all(item["type"] == "function" for item in schemas)
    assert all(item["strict"] is False for item in schemas)
    assert "faturamento_total" in schemas[0]["parameters"]["properties"]["metric"]["enum"]
    filter_operators = schemas[0]["parameters"]["properties"]["filters"]["items"]["properties"]["operator"]["enum"]
    assert "BETWEEN" in filter_operators


def test_instructions_contain_critical_business_rules() -> None:
    assert "Cliente #" in INSTRUCTIONS
    assert "2026-07-02" in INSTRUCTIONS
    assert "Nunca invente números" in INSTRUCTIONS
    assert "frações com sinal" in INSTRUCTIONS
    assert "sugestoes" in INSTRUCTIONS
    assert "objeto JSON válido" in INSTRUCTIONS
    assert "menor número possível de chamadas" in INSTRUCTIONS


def test_instructions_include_persistent_filter_context() -> None:
    instructions = build_instructions("Concessionária = Sul")

    assert "Filtro persistente da conversa: Concessionária = Sul" in instructions
    assert "não tente substituí-lo" in instructions


def test_describe_filter_formats_dimension_label_and_range() -> None:
    assert (
        describe_filter({"dimension": "concessionaria", "operator": "=", "value": "Sul"})
        == "Concessionária = Sul"
    )
    assert (
        describe_filter(
            {
                "dimension": "data",
                "operator": "BETWEEN",
                "value": ["2025-01-01", "2026-07-02"],
            }
        )
        == "Data da venda entre 2025-01-01 e 2026-07-02"
    )
    assert describe_filter(None) == ""


def test_openai_service_parses_structured_sections_and_suggestions() -> None:
    payload = (
        '{"resumo":"O faturamento cresceu e concentra receita no Sul.",'
        '"resposta":"Gráfico de evolução mensal com destaques.",'
        '"prova":"Tabela com os valores usados no gráfico.",'
        '"sugestoes":[{"rotulo":"Ver ranking","pergunta":"Quais foram as 10 concessionárias com maior faturamento?"}]}'
    )
    client = FakeClient([_response(FakeItem(type="message", content=[], id="msg_1"), text=payload)])
    service = OpenAIService(tool_executor=FakeExecutor("{}"), client=client, model="test-model")

    answer = service.ask("Como o faturamento evoluiu?")

    assert answer.text == "O faturamento cresceu e concentra receita no Sul."
    assert answer.secoes.resposta == "Gráfico de evolução mensal com destaques."
    assert answer.secoes.prova == "Tabela com os valores usados no gráfico."
    assert answer.secoes.sugestoes[0]["rotulo"] == "Ver ranking"
    assert answer.to_dict()["secoes"]["sugestoes"] == answer.secoes.sugestoes


def test_openai_service_applies_persistent_filter_to_tool_arguments() -> None:
    call = FakeItem(
        type="function_call",
        name="get_kpi",
        arguments=(
            '{"metric": "faturamento_total", "filters": ['
            '{"dimension": "concessionaria", "operator": "=", "value": "Norte"}]}'
        ),
        call_id="call_1",
    )
    message = FakeItem(type="message", content=[], id="msg_1")
    client = FakeClient([_response(call, text=""), _response(message, text="Ok")])
    executor = FakeExecutor('{"metrica": "faturamento_total", "valor": 100.0}')
    service = OpenAIService(tool_executor=executor, client=client, model="test-model")

    service.ask(
        "Qual foi o faturamento?",
        persistent_filter={"dimension": "concessionaria", "operator": "=", "value": "Sul"},
    )

    assert executor.calls[0][1]["filters"] == [
        {"dimension": "concessionaria", "operator": "=", "value": "Sul"}
    ]
    assert "Concessionária = Sul" in client.responses.calls[0]["instructions"]


def test_openai_service_maps_date_filter_to_period_arguments() -> None:
    call = FakeItem(
        type="function_call",
        name="get_trend",
        arguments=(
            '{"metric": "faturamento_total", "granularity": "mes", '
            '"start_date": "2024-01-01"}'
        ),
        call_id="call_1",
    )
    message = FakeItem(type="message", content=[], id="msg_1")
    client = FakeClient([_response(call, text=""), _response(message, text="Ok")])
    executor = FakeExecutor('{"metrica": "faturamento_total", "valor": 100.0}')
    service = OpenAIService(tool_executor=executor, client=client, model="test-model")

    service.ask(
        "Como o faturamento evoluiu?",
        persistent_filter={
            "dimension": "data",
            "operator": "BETWEEN",
            "value": ["2025-01-01", "2026-07-02"],
        },
    )

    assert executor.calls[0][1]["start_date"] == "2025-01-01"
    assert executor.calls[0][1]["end_date"] == "2026-07-02"
    assert "filters" not in executor.calls[0][1]


def test_openai_service_keeps_date_filter_on_compare_periods() -> None:
    persistent_filter = {
        "dimension": "data",
        "operator": "BETWEEN",
        "value": ["2025-01-01", "2026-07-02"],
    }
    call = FakeItem(
        type="function_call",
        name="compare_periods",
        arguments=(
            '{"metric": "faturamento_total", "current_start": "2026-01-01", '
            '"current_end": "2026-06-30", "previous_start": "2025-01-01", '
            '"previous_end": "2025-06-30"}'
        ),
        call_id="call_1",
    )
    message = FakeItem(type="message", content=[], id="msg_1")
    client = FakeClient([_response(call, text=""), _response(message, text="Ok")])
    executor = FakeExecutor('{"metrica": "faturamento_total", "valor": 100.0}')
    service = OpenAIService(tool_executor=executor, client=client, model="test-model")

    service.ask("Compare os períodos.", persistent_filter=persistent_filter)

    assert executor.calls[0][1]["filters"] == [persistent_filter]


def test_openai_service_runs_function_call_until_final_answer() -> None:
    call = FakeItem(
        type="function_call",
        name="get_kpi",
        arguments='{"metric": "faturamento_total"}',
        call_id="call_1",
    )
    message = FakeItem(type="message", content=[], id="msg_1")
    client = FakeClient(
        [
            _response(call, text=""),
            _response(message, text="Faturamento: R$ 100,00."),
        ]
    )
    executor = FakeExecutor('{"metrica": "faturamento_total", "valor": 100.0, "cliente": "Cliente #999"}')

    service = OpenAIService(tool_executor=executor, client=client, model="test-model")
    answer = service.ask("Qual foi o faturamento?")

    assert answer.text == "Faturamento: R$ 100,00."
    assert answer.event_id
    assert answer.to_dict()["event_id"] == answer.event_id
    assert answer.tools_used == ["get_kpi"]
    assert answer.avisos
    assert answer.secoes.resumo == "Faturamento: R$ 100,00."
    assert answer.secoes.sugestoes
    assert answer.tool_results[0]["ferramenta"] == "get_kpi"
    assert answer.tool_results[0]["valor"] == 100.0
    assert executor.calls == [("get_kpi", {"metric": "faturamento_total"})]
    assert len(client.responses.calls) == 2
    assert client.responses.calls[0]["store"] is False
    assert client.responses.calls[1]["input"][-2]["call_id"] == "call_1"


def test_openai_service_requires_api_key_when_client_is_absent(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        "services.openai_service.get_secret", lambda key, default=None: None
    )
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIService(tool_executor=FakeExecutor("{}"))


def test_response_service_builds_synthetic_client_warning() -> None:
    answer = ResponseService().build("Ok", ["get_kpi"], ['{"cliente": "Cliente #1"}'])
    assert "Cliente #" in answer.avisos[0]
    assert answer.to_dict()["ferramentas_utilizadas"] == ["get_kpi"]


def test_analytics_builds_parameterized_query() -> None:
    fake_service = FakeBigQueryService([{"valor": 100}])
    analytics = AnalyticsQueries(service=fake_service)

    result = analytics.get_kpi(
        "faturamento_total",
        start_date="2025-01-01",
        filters=[{"dimension": "vendedor", "operator": "=", "value": "João"}],
    )

    assert result["valor"] == 100
    assert result["filtros"] == [
        {"dimensao": "vendedor", "operador": "=", "valor": "João"}
    ]
    assert "data >= @start_date" in fake_service.sql
    assert "vendedor = @f0" in fake_service.sql
    parameters = {item.name: item.value for item in fake_service.parameters}
    assert parameters["f0"] == "João"


def test_analytics_builds_between_date_filter() -> None:
    fake_service = FakeBigQueryService([{"valor": 100}])
    analytics = AnalyticsQueries(service=fake_service)

    result = analytics.get_kpi(
        "faturamento_total",
        filters=[
            {
                "dimension": "data",
                "operator": "BETWEEN",
                "value": ["2025-01-01", "2025-12-31"],
            }
        ],
    )

    assert result["valor"] == 100
    assert "data BETWEEN @f0_inicio AND @f0_fim" in fake_service.sql
    parameters = {item.name: item.value for item in fake_service.parameters}
    assert parameters["f0_inicio"].isoformat() == "2025-01-01"
    assert parameters["f0_fim"].isoformat() == "2025-12-31"


def test_analytics_rejects_unknown_metric_and_operator() -> None:
    analytics = AnalyticsQueries(service=FakeBigQueryService([]))
    with pytest.raises(AnalyticsError, match="Métrica desconhecida"):
        analytics.get_kpi("metrica_inventada")
    with pytest.raises(AnalyticsError, match="Operador de filtro não permitido"):
        analytics.get_kpi(
            "faturamento_total",
            filters=[{"dimension": "vendedor", "operator": "DROP", "value": "x"}],
        )
