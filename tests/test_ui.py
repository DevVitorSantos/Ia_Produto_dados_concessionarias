from __future__ import annotations

from ui import components
from ui.charts import build_figure, comparison_figure, ranking_figure, trend_figure
from ui.format import format_metric, format_value, metric_label


def test_format_value_brazilian_outputs() -> None:
    assert format_value(1234567.5, "currency_br") == "R$ 1.234.567,50"
    assert format_value(0.1234, "percent_br") == "12,34%"
    assert format_value(1234, "integer_br") == "1.234"
    assert format_value(None, "currency_br") == "—"


def test_format_metric_uses_semantic_definition() -> None:
    assert format_metric("faturamento_total", 10) == "R$ 10,00"
    assert metric_label("faturamento_total") == "Faturamento total"


def test_charts_are_generated_for_official_tool_results() -> None:
    trend_result = {
        "metrica": "faturamento_total",
        "granularidade": "mes",
        "linhas": [{"periodo": "2025-01-01", "valor": 10}],
    }
    ranking_result = {
        "metrica": "faturamento_total",
        "dimensao": "concessionaria",
        "linhas": [{"categoria": "Sul", "valor": 10}],
    }
    comparison_result = {
        "metrica": "faturamento_total",
        "periodo_atual": {"valor": 12},
        "periodo_anterior": {"valor": 10},
    }

    assert trend_figure(trend_result).data[0].type == "scatter"
    assert ranking_figure(ranking_result).data[0].type == "bar"
    assert comparison_figure(comparison_result).data[0].type == "bar"
    assert build_figure(trend_result).data[0].type == "scatter"
    assert build_figure(ranking_result).data[0].type == "bar"
    assert build_figure(comparison_result).data[0].type == "bar"
    assert build_figure({"metrica": "faturamento_total", "valor": 10}) is None


def test_render_tool_results_assigns_unique_plotly_keys(monkeypatch) -> None:
    keys: list[str] = []
    monkeypatch.setattr(components, "build_figure", lambda result: object())
    monkeypatch.setattr(
        components.st,
        "plotly_chart",
        lambda figure, **kwargs: keys.append(kwargs["key"]),
    )

    components.render_tool_results(
        [{"grafico": 1}, {"grafico": 2}], key_prefix="answer-event"
    )

    assert keys == ["answer-event-0", "answer-event-1"]
