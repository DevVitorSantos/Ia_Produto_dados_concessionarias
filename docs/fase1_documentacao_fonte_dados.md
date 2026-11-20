# Fase 1 — Documentação técnica da fonte de dados

## Objetivo

Documentar a fonte de dados real antes de escrever qualquer código da aplicação, para que a camada semântica e o assistente usem indicadores consistentes.

**Fonte oficial confirmada:** BigQuery de produção do projeto `projeto-dev-410722`, dataset `gold_clau`, localização `US`. O repositório GitHub é contexto histórico e não define o comportamento atual das métricas.

## Projeto original analisado

- Repositório: `https://github.com/DevVitorSantos/Produto_dados_concessionarias`
- Commit: `e978e449829a05bb2f6a7e1940c3d7e40cc43d0e`
- Estrutura relevante:
  - `definitions/silver/` — 7 modelos `.sqlx`.
  - `definitions/gold/` — 5 dimensões, 1 fato e 1 view.
  - `docs/` — documentação de dashboards.
- Documentos lidos: `README.md`, `projeto_nova_drive_modelagem_BG.txt`, `definitions/sources/`, `docs/guia_implementacao_dashboards.md` e os `.sqlx` da Gold.

## Ambiente validado

| Item | Valor |
| --- | --- |
| Projeto GCP | `projeto-dev-410722` |
| Dataset | `gold_clau` |
| Localização | `US` |
| View principal | `projeto-dev-410722.gold_clau.vw_fato_completa` |
| Objetos encontrados | 7 |
| Colunas na view | 38 |

A conta de serviço recebeu `roles/bigquery.jobUser` no projeto e `roles/bigquery.dataViewer` no dataset. Consultas de leitura foram executadas com sucesso.

## Objetos Gold

- `dim_cliente`
- `dim_concessionaria`
- `dim_tempo`
- `dim_vendedor`
- `dim_veiculo`
- `fato_vendas`
- `vw_fato_completa`

A view é o único objeto que deve ser consultado pelo assistente. Ela já traz os atributos de dimensão necessários para filtros, rankings e agrupamentos.

## Granularidade e relacionamentos

- A fato tem **uma linha por venda** (`id_venda`).
- `vw_fato_completa` faz LEFT JOIN com as dimensões usando `id_tempo`, `id_cliente`, `id_veiculo`, `id_vendedor` e `id_concessionaria`.
- Todas as chaves de dimensão são únicas; os joins não duplicam linhas.
- `dim_tempo` cobre `2017-01-01` a `2035-12-31`.
- `fato_vendas` cobre `2025-01-01` a `2026-07-02`.

## Validações com dados reais

| Verificação | Resultado |
| --- | --- |
| Linhas da view | 7.720 |
| `id_venda` distintos | 7.720 |
| Faturamento total | R$ 3.444.157.639,69 |
| Vendas em 2025 | 4.090 / R$ 2.029.298.597,07 |
| Vendas em 2026 | 3.630 / R$ 1.414.859.042,62 |
| Vendedores | 53 |
| Concessionárias | 29 |
| Modelos de veículo | 8 |
| `quantidade_venda` | sempre 1 |
| `ticket_medio` x `valor_pago` | iguais em 100% das linhas |
| `valor_desconto = valor_tabela - valor_pago` | 100% das linhas |
| `percentual_desconto` | fração com sinal, de -2,1626 a 0,7018 |
| `venda_com_desconto` | 3.927 com desconto; 3.793 sem |
| Clientes sem match real | 6.484 de 7.720 (84%) |

## Regras de negócio oficiais

1. **Venda:** registro em `vw_fato_completa`, identificado por `id_venda`.
2. **Faturamento:** `SUM(valor_pago)`.
3. **Quantidade de vendas:** `COUNT(id_venda)`; não usar soma de `quantidade_venda` para esse fim.
4. **Ticket médio:** `SUM(valor_pago) / COUNT(id_venda)`. O campo `ticket_medio` da view é igual a `valor_pago` da linha porque a quantidade é sempre 1.
5. **Desconto em valor:** `valor_desconto = valor_tabela - valor_pago`, com sinal. Valor negativo significa venda acima da tabela.
6. **Desconto percentual:** `percentual_desconto = (valor_tabela - valor_pago) / valor_tabela`, não arredondado. Multiplicar por 100 apenas ao formatar a resposta.
7. **Categorias de desconto:** `Baixo` até 5%, `Médio` entre 5% e 10%, `Alto` acima de 10%, aplicados sobre a fração.
8. **Faixas de preço:** `Até 250 mil`, `250k a 350k`, `350k a 500k`, `Acima de 500k`.
9. **Comparação de períodos:** usar a última data disponível como referência; os dados terminam em `2026-07-02`.
10. **Clientes:** quando `cliente` começar com `Cliente #`, sinalizar que o rótulo foi gerado pela view porque não houve correspondência em `dim_cliente`.

## Divergências em relação ao repositório

| Tema | Repositório | Produção (oficial) |
| --- | --- | --- |
| `percentual_desconto` | 0 a 100, sem sinal | fração com sinal |
| Categorias de desconto | Sem Desconto / Leve / Moderado / Agressivo | Baixo / Médio / Alto |
| Faixas de preço | Popular / Padrão / Alto Padrão / Premium | até 250k / 250k a 350k / 350k a 500k / acima de 500k |
| `dim_tempo` | 2020 a 2030 | 2017 a 2035 |
| Rótulo de cliente | somente `dim_cliente` | `COALESCE(c.cliente, CONCAT('Cliente #', f.id_cliente))` |

## Limitações que devem aparecer nas respostas

- Metas mensal (R$ 200 mil) e anual (R$ 3 milhões) existem apenas no guia de dashboards do Looker Studio; **não há coluna de meta na Gold**.
- `cliente_recorrente` e a classificação de performance (Destaque / Bom / Atenção) não existem prontos na Gold.
- 84% dos rótulos de cliente são sintéticos.
- Não existe fonte para forecast ou metas na Gold.
- Dados de 2026 param em julho, então "último mês" deve significar o último mês disponível na base.

## Consultas de validação usadas

```sql
SELECT
  COUNT(*) AS total_vendas,
  COUNT(DISTINCT id_venda) AS vendas_distintas,
  SUM(valor_pago) AS faturamento,
  MIN(data) AS primeira_data,
  MAX(data) AS ultima_data
FROM `projeto-dev-410722.gold_clau.vw_fato_completa`;

SELECT
  EXTRACT(YEAR FROM data) AS ano,
  COUNT(*) AS vendas,
  SUM(valor_pago) AS faturamento
FROM `projeto-dev-410722.gold_clau.vw_fato_completa`
GROUP BY ano
ORDER BY ano;

SELECT 'dim_tempo' AS dim, COUNT(*) AS total, COUNT(DISTINCT id_tempo) AS chaves
FROM `projeto-dev-410722.gold_clau.dim_tempo`
UNION ALL SELECT 'dim_cliente', COUNT(*), COUNT(DISTINCT id_cliente)
FROM `projeto-dev-410722.gold_clau.dim_cliente`
UNION ALL SELECT 'dim_veiculo', COUNT(*), COUNT(DISTINCT id_veiculo)
FROM `projeto-dev-410722.gold_clau.dim_veiculo`
UNION ALL SELECT 'dim_vendedor', COUNT(*), COUNT(DISTINCT id_vendedor)
FROM `projeto-dev-410722.gold_clau.dim_vendedor`
UNION ALL SELECT 'dim_concessionaria', COUNT(*), COUNT(DISTINCT id_concessionaria)
FROM `projeto-dev-410722.gold_clau.dim_concessionaria`;
```

## Situação

- [x] Repositório original analisado até o commit `e978e44`.
- [x] Schema real e SQL da view obtidos via BigQuery API.
- [x] Dados validados com consultas reais.
- [x] Fonte oficial confirmada como produção.
- [x] Ressalva de clientes sintéticos confirmada.
- [x] Entregável em HTML e Markdown.
- [x] Próxima etapa iniciada: Fase 2 — conexão com BigQuery.

Nenhuma credencial está incluída neste documento.
