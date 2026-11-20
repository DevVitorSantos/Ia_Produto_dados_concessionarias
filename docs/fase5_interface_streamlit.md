# Fase 5 — Interface e visualizações

## Status

Implementada com Streamlit e Plotly. A validação visual com perguntas reais depende da chave OpenAI rotacionada e configurada fora do chat.

## Arquivos criados

| Arquivo | Função |
|---|---|
| `streamlit_app.py` | Página inicial, configuração global e orientação de navegação. |
| `pages/1_Chat_IA.py` | Chat com histórico, sugestões, respostas, avisos, tabelas e gráficos. |
| `pages/2_Indicadores.py` | Cards de KPIs, filtros de período/dimensão, tendência mensal e ranking. |
| `pages/3_Historico.py` | Histórico da sessão e exportação CSV. |
| `pages/4_Qualidade.py` | Análise persistente de buscas repetidas e notas de qualidade. |
| `ui/format.py` | Formatação brasileira de moeda, percentual, inteiros e labels das métricas. |
| `ui/charts.py` | Construção de gráficos Plotly de tendência, ranking e comparação. |
| `ui/components.py` | Renderização de cards, tabelas e gráficos nos resultados das ferramentas. |
| `ui/state.py` | Estado da conversa em `st.session_state`. |

## Como executar

```powershell
.venv/Scripts/python -m streamlit run streamlit_app.py
```

Sempre execute com o Python do `.venv`; o Python global pode não ter `google-cloud-bigquery` instalado.

Antes de usar o Chat IA, configure localmente:

```powershell
$env:OPENAI_API_KEY = "sua-chave-rotacionada"
$env:OPENAI_MODEL = "gpt-4.1-mini"
```

A página de Indicadores usa a credencial BigQuery já prevista nas Fases 1 e 2.

## Experiência implementada

- chat com histórico durante a sessão;
- sugestões de perguntas;
- cards com as métricas oficiais;
- gráficos Plotly para evolução mensal, ranking e comparação de períodos;
- tabelas com download CSV;
- aviso automático sobre rótulos sintéticos `Cliente #`;
- tratamento amigável para credenciais ausentes e erros de consulta;
- histórico exportável da sessão;
- botões de nota nas respostas e persistência de eventos no BigQuery, detalhada em `docs/qualidade_rastreamento.md`.

## Dependências adicionadas

- `streamlit>=1.41,<2` — instalado `1.67.0`.
- `plotly>=5.24,<7` — instalado `6.9.0`.

## Validação

- testes automatizados do projeto: 37 aprovados após o módulo de rastreamento de qualidade;
- `compileall` e `git diff --check` executados ao final;
- validação local no navegador: Home, Indicadores, Chat IA e Histórico renderizaram sem erros de console;
- Indicadores carregou KPIs reais do BigQuery: R$ 3.444.157.639,69, 7.720 vendas e R$ 446.134,41 de ticket médio;
- Chat IA exibiu corretamente o aviso de `OPENAI_API_KEY` ausente, sem tentar chamada externa;
- corrigido import circular entre `queries.analytics`, `services` e `agent` durante a validação no navegador;
- corrigido ambiente local: instâncias iniciadas com Python global foram substituídas pela instância do `.venv`, que contém `google-cloud-bigquery`;
- validação ao vivo do Chat IA com OpenAI: "Qual foi o faturamento total?" retornou R$ 3.444.157.639,69 via `get_kpi`;
- validação ao vivo de gráfico no chat: "Como o faturamento evoluiu por mês?" gerou tabela e gráfico Plotly via `get_trend`;
- chave configurada apenas em `.streamlit/secrets.toml`, protegida pelo `.gitignore`; `.streamlit/secrets.toml.example` restaurado sem credencial;
- rastreamento de qualidade validado com testes unitários de classificação, gravação de eventos/feedback e consultas de repetição;
- setup das tabelas preparado em `scripts/setup_feedback_tables.py`; a conta de serviço atual não tem permissão para criar datasets e precisa receber `bigquery.dataEditor` apenas em `analytics_ops`.

## Próxima etapa

Fase 6 — preparar GitHub, configurar Secrets no Streamlit Community Cloud e publicar o MVP.
