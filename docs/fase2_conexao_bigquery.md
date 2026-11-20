# Fase 2 — Conexão com BigQuery

## Objetivo

Implementar a conexão com o BigQuery, garantir acesso somente leitura ao Gold e validar consultas reais antes de construir a camada semântica.

## O que foi desenvolvido

| Arquivo | Finalidade |
| --- | --- |
| `requirements.txt` | Dependências de BigQuery, autenticação, pandas e testes. |
| `.gitignore` | Protege JSON de credencial, `.env`, `.venv` e secrets do Streamlit. |
| `.streamlit/secrets.toml.example` | Modelo de configuração sem credenciais reais. |
| `config.py` | Leitura de configuração por Secrets do Streamlit ou variáveis de ambiente. |
| `services/bigquery_service.py` | Cliente BigQuery, validação de SQL somente leitura e consultas de teste. |
| `tests/test_bigquery_service.py` | Testes unitários das regras de segurança e do nome de tabelas. |
| `scripts/smoke_test_bigquery.py` | Validação ponta a ponta contra o dataset real. |
| `README.md` | Instruções de instalação, configuração e teste. |

## Segurança implementada

- A consulta deve começar com `SELECT` ou `WITH`.
- Comentários e literais são removidos antes da validação, evitando falsos positivos.
- Palavras como `INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE`, `MERGE`, `ALTER` e `TRUNCATE` são rejeitadas.
- Apenas uma instrução por chamada; multiple statements são bloqueados.
- Consultas usam `maximum_bytes_billed`, `job_timeout_ms` e limite máximo de linhas.
- Nenhuma credencial aparece em logs, testes ou arquivos versionáveis.

## Como testar

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m pytest -q

export GOOGLE_APPLICATION_CREDENTIALS="caminho/para/service-account.json"
export GCP_PROJECT_ID="projeto-dev-410722"
export GCP_DATASET="gold_clau"
export GCP_LOCATION="US"
.venv/Scripts/python scripts/smoke_test_bigquery.py
```

## Resultado da validação real

- 10 testes unitários aprovados.
- Conexão: `SELECT 1` retornou `ok = 1`.
- 7 objetos Gold listados.
- 7.720 vendas e 7.720 IDs distintos.
- Faturamento: R$ 3.444.157.639,69.
- Período: 01/01/2025 a 02/07/2026.
- 2025: 4.090 vendas / R$ 2.029.298.597,07.
- 2026: 3.630 vendas / R$ 1.414.859.042,62.
- Desconto: 3.793 negativos, 3.927 positivos, fração de -2,16256388 a 0,701795113.
- Chaves de dimensão únicas em todas as 5 dimensões.

## Situação

Fase 2 concluída. Próxima etapa: Fase 3 — camada semântica com `metrics.yaml`, `dimensions.yaml`, `business_rules.yaml` e `schema.yaml`.
