import pytest

from semantic_layer import loader


def test_semantic_layer_is_valid():
    assert loader.validate_semantic_layer() == []


def test_schema_has_real_columns_and_primary_key():
    columns = loader.primary_table_columns()
    assert len(columns) == 38
    assert loader.get_schema()["tables"]["vw_fato_completa"]["primary_key"] == "id_venda"
    assert "valor_tabela" in columns
    assert "percentual_desconto" in columns


def test_faturamento_e_ticket_medio_usam_formulas_oficiais():
    assert loader.get_metric("faturamento_total")["sql"] == "SUM(valor_pago)"
    ticket = loader.get_metric("ticket_medio")["sql"]
    assert "SUM(valor_pago)" in ticket
    assert "COUNT(DISTINCT id_venda)" in ticket
    assert "AVG(ticket_medio)" not in ticket


def test_percentual_desconto_usa_fracao_e_ponderacao():
    metric = loader.get_metric("percentual_desconto_medio")
    assert metric["output_scale"] == "fraction"
    assert metric["format"] == "percent_br"
    assert "SUM(valor_desconto)" in metric["sql"]
    assert "SUM(valor_tabela)" in metric["sql"]


def test_dimensoes_reais_de_categorias_e_faixas():
    desconto = loader.get_dimension("categoria_desconto")
    faixa = loader.get_dimension("faixa_preco")
    assert desconto["allowed_values"] == ["Baixo", "Médio", "Alto"]
    assert faixa["allowed_values"] == [
        "Até 250 mil",
        "250k a 350k",
        "350k a 500k",
        "Acima de 500k",
    ]


def test_cliente_sintetico_tem_regra_de_divulgacao():
    cliente = loader.get_dimension("cliente")
    assert cliente["synthetic_pattern"] == "Cliente #"
    assert "dim_cliente" in cliente["disclosure"]
    regras = {rule["id"]: rule for rule in loader.get_business_rules()["rules"]}
    assert regras["cliente_sintetico"]["severity"] == "high"


def test_regra_de_fonte_oficial_esta_presente():
    regras = {rule["id"]: rule for rule in loader.get_business_rules()["rules"]}
    assert "projeto-dev-410722" in regras["fonte_oficial"]["rule"]
    assert "gold_clau" in regras["fonte_oficial"]["rule"]


@pytest.mark.parametrize("getter,name", [(loader.get_metric, "inexistente"), (loader.get_dimension, "inexistente")])
def test_nomes_desconhecidos_geram_erro(getter, name):
    with pytest.raises(KeyError):
        getter(name)
