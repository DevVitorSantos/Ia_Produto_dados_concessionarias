# Fase 3 — Camada semântica

## Objetivo

Centralizar schema, métricas, dimensões e regras de negócio em arquivos versionáveis, evitando que o modelo interprete a Gold de formas divergentes.

## Arquivos criados

| Arquivo | Conteúdo |
| --- | --- |
| `semantic_layer/schema.yaml` | Projeto, dataset, localização, 38 colunas reais de `vw_fato_completa`, chave primária e 5 relacionamentos. |
| `semantic_layer/metrics.yaml` | 9 indicadores com SQL, agregação, unidade, formato e notas. |
| `semantic_layer/dimensions.yaml` | 28 dimensões com papéis, tipos, valores permitidos e regra de cliente sintético. |
| `semantic_layer/business_rules.yaml` | 18 regras com severidade, incluindo fonte oficial, segurança e limitações. |
| `semantic_layer/loader.py` | Carregamento, acesso por nome e validação automática da camada. |
| `tests/test_semantic_layer.py` | Testes das fórmulas, dimensões, regras e consistência com o schema. |

## Fórmulas oficiais registradas

- Faturamento: `SUM(valor_pago)`.
- Quantidade de vendas: `COUNT(DISTINCT id_venda)`.
- Ticket médio: `SUM(valor_pago) / NULLIF(COUNT(DISTINCT id_venda), 0)`.
- Desconto total: `SUM(valor_desconto)`.
- Desconto médio: `SUM(valor_desconto) / NULLIF(COUNT(DISTINCT id_venda), 0)`.
- Percentual médio de desconto: `SUM(valor_desconto) / NULLIF(SUM(valor_tabela), 0)`, em fração.
- Média simples do percentual: `AVG(percentual_desconto)`, somente mediante pedido explícito.
- Veículos vendidos: `COUNT(id_venda)`.
- Valor de tabela total: `SUM(valor_tabela)`.

## Regras críticas

1. Produção é a fonte oficial; repositório é contexto histórico.
2. Somente `vw_fato_completa` pode ser consultada pelo assistente.
3. SQL somente leitura, sem SQL arbitrário.
4. `percentual_desconto` é fração com sinal; converter para porcentagem só ao formatar.
5. Rótulos `Cliente #id` devem ser sinalizados como clientes sem match em `dim_cliente`.
6. "Último mês" significa o último mês disponível: a base termina em `2026-07-02`.
7. Metas, forecast e classificação de performance não têm fonte na Gold e devem ser recusados com explicação.

## Validação

```bash
.venv/Scripts/python -m pytest -q
```

Resultado: 19 testes aprovados, incluindo 10 da Fase 2 e 9 da camada semântica. A função `validate_semantic_layer()` confere colunas, tipos, chaves, relacionamentos e completeness das regras.

## Situação

Fase 3 concluída. Fase 4 implementada em `docs/fase4_agente_openai.md`, usando Responses API, Function Calling e as 5 ferramentas controladas.
