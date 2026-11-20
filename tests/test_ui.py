from __future__ import annotations

from types import MappingProxyType, SimpleNamespace

from ui import components
from ui.charts import (
    build_combined_figure,
    build_figure,
    comparison_figure,
    ranking_figure,
    trend_figure,
)
from ui.format import format_metric, format_value, metric_label
from ui import profile_popup
from ui.profile_popup import PROFILE_COOKIE, build_cookie_script
from ui.state import build_conversation_filter


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


def test_charts_include_data_labels_and_axis_labels() -> None:
    trend = trend_figure(
        {
            "metrica": "faturamento_total",
            "granularidade": "mes",
            "linhas": [{"periodo": "2025-01-01", "valor": 10}],
        }
    )
    ranking = ranking_figure(
        {
            "metrica": "faturamento_total",
            "dimensao": "concessionaria",
            "linhas": [{"categoria": "Sul", "valor": 10}],
        }
    )
    comparison = comparison_figure(
        {
            "metrica": "faturamento_total",
            "periodo_atual": {"valor": 12},
            "periodo_anterior": {"valor": 10},
        }
    )

    assert trend.data[0].text is not None
    assert trend.layout.xaxis.title.text == "Período"
    assert ranking.data[0].text is not None
    assert ranking.data[0].marker.color is not None
    assert comparison.data[0].text is not None
    assert [trace.marker.color for trace in comparison.data] == ["#16A34A", "#94A3B8"]


def test_combined_trend_chart_uses_filters_as_series() -> None:
    results = [
        {
            "ferramenta": "get_trend",
            "metrica": "faturamento_total",
            "granularidade": "mes",
            "linhas": [{"periodo": "2025-01-01", "valor": 10}],
            "filtros": [
                {"dimensao": "concessionaria", "operador": "=", "valor": "Sul"},
            ],
        },
        {
            "ferramenta": "get_trend",
            "metrica": "faturamento_total",
            "granularidade": "mes",
            "linhas": [{"periodo": "2025-01-01", "valor": 20}],
            "filtros": [
                {"dimensao": "concessionaria", "operador": "=", "valor": "Norte"},
            ],
        },
    ]

    combined = build_combined_figure(results)

    assert combined is not None
    figure, consumed = combined
    assert consumed == {0, 1}
    assert [trace.name for trace in figure.data] == [
        "concessionaria=Sul",
        "concessionaria=Norte",
    ]
    assert figure.layout.legend.title.text == "Recorte"


def test_render_suggestions_triggers_new_search(monkeypatch) -> None:
    class DummyColumn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    clicked: list[str] = []
    monkeypatch.setattr(components.st, "columns", lambda count: [DummyColumn() for _ in range(count)])
    monkeypatch.setattr(
        components.st,
        "button",
        lambda label, **kwargs: "evolução" in str(label),
    )
    monkeypatch.setattr(components.st, "rerun", lambda: None)

    components.render_suggestions(
        [
            {"rotulo": "Ver evolução mensal", "pergunta": "Como o faturamento evoluiu por mês?"},
            {"rotulo": "Ver ranking", "pergunta": "Quais foram as 10 concessionárias?"},
        ],
        key_prefix="answer-1",
        on_select=clicked.append,
    )

    assert clicked == ["Como o faturamento evoluiu por mês?"]


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


def test_build_conversation_filter_normalizes_values() -> None:
    assert build_conversation_filter("concessionaria", " Sul ") == {
        "dimension": "concessionaria",
        "operator": "=",
        "value": "Sul",
    }
    assert build_conversation_filter(
        "data",
        ["2025-01-01", "2025-12-31"],
        "BETWEEN",
    ) == {
        "dimension": "data",
        "operator": "BETWEEN",
        "value": ["2025-01-01", "2025-12-31"],
    }
    assert build_conversation_filter("cidade", "") is None
    assert build_conversation_filter("data", [], "BETWEEN") is None
    assert build_conversation_filter("data", ["2026-01-01", "2025-01-01"], "BETWEEN") is None


def test_profile_cookie_script_expires_in_seven_days() -> None:
    script = build_cookie_script("profile-123")
    assert PROFILE_COOKIE in script
    assert "Max-Age=604800" in script
    assert "profile-123" in script
    assert "SameSite=Lax" in script


def test_read_cookie_accepts_mapping_proxy(monkeypatch) -> None:
    fake_st = SimpleNamespace(
        context=SimpleNamespace(
            cookies=MappingProxyType({PROFILE_COOKIE: "profile-123"})
        )
    )
    monkeypatch.setattr(profile_popup, "st", fake_st)

    assert profile_popup._read_cookie() == "profile-123"


def test_cookie_iframe_uses_positive_dimensions(monkeypatch) -> None:
    captured: list[dict[str, object]] = []

    def fake_iframe(html: str, **kwargs: object) -> None:
        captured.append({"html": html, **kwargs})

    fake_st = SimpleNamespace(iframe=fake_iframe)
    monkeypatch.setattr(profile_popup, "st", fake_st)

    profile_popup._render_iframe("<script></script>")

    assert captured == [{"html": "<script></script>", "height": 1, "width": 1}]
