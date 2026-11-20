# Rastreamento de qualidade das buscas

Este módulo registra eventos de uso do Chat IA e as notas dadas pelo usuário para identificar quais buscas são repetidas e quais respostas geraram dúvida ou erro.

## Tabelas

Dataset padrão: `analytics_ops`. Nome alterável por `FEEDBACK_DATASET`.

### `chat_events`

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `event_id` | STRING | Identificador da interação; liga evento e feedback. |
| `created_at` | TIMESTAMP | Momento da busca. |
| `session_id` | STRING | Identificador da sessão Streamlit. |
| `question` | STRING | Pergunta enviada pelo usuário. |
| `question_hash` | STRING | Hash da pergunta normalizada. |
| `subject` | STRING | Assunto classificado: faturamento, vendas, desconto, ranking, tendencia, comparacao, cliente, concessionaria, veiculo, vendedor, periodo ou outro. |
| `subject_hash` | STRING | Hash do assunto + ferramentas usadas. |
| `tools_used` | STRING REPEATED | Ferramentas chamadas na resposta. |
| `response_ms` | INTEGER | Tempo de resposta. |
| `repeat_count` | INTEGER | Quantas vezes a mesma pergunta normalizada ocorreu antes na sessão. |
| `status` | STRING | Resultado da interação. |
| `model` | STRING | Modelo OpenAI usado. |

### `chat_feedback`

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `feedback_id` | STRING | Identificador do feedback. |
| `event_id` | STRING | Evento avaliado. |
| `created_at` | TIMESTAMP | Momento da nota. |
| `session_id` | STRING | Sessão do usuário. |
| `rating` | STRING | `satisfatoria`, `duvidas` ou `resultado_errado`. |
| `comment` | STRING | Comentário opcional. |

## Permissões

A conta de serviço usada pela aplicação precisa de `bigquery.dataEditor` apenas no dataset `analytics_ops`. Ela não precisa de escrita na Gold.

A criação inicial do dataset exige `bigquery.datasets.create`. A conta de serviço atual não possui essa permissão; crie o dataset no Console do GCP ou use uma credencial administrativa local para o setup.

## Setup

Com uma credencial que tenha permissão de criação de dataset:

```bash
gcloud auth application-default login
.venv/Scripts/python scripts/setup_feedback_tables.py
```

Ou, com uma conta de serviço autorizada:

```bash
.venv/Scripts/python scripts/setup_feedback_tables.py --service-account "caminho/para/admin.json"
```

Para usar outro dataset:

```bash
export FEEDBACK_DATASET="analytics_ops"
.venv/Scripts/python scripts/setup_feedback_tables.py
```

## Solução de problemas

Se o Chat IA responder mas mostrar `Table <project number>:analytics_ops.chat_events not found`, a aplicação agora tenta localizar/criar a tabela e repetir o insert. Se persistir, confirme que `GOOGLE_APPLICATION_CREDENTIALS_JSON` em `.streamlit/secrets.toml` contém o JSON da conta de serviço — ou defina `GOOGLE_APPLICATION_CREDENTIALS` no ambiente —, conceda `bigquery.dataEditor` em `analytics_ops` e reinicie o Streamlit.

Se `DELETE` falhar com `would affect rows in the streaming buffer`, recrie as tabelas com `scripts/setup_feedback_tables.py` após remover as duas tabelas de `analytics_ops`.

## Uso

No Chat IA, cada resposta passa a ter três botões: **Satisfatória**, **Tenho dúvidas** e **Resultado errado**. A nota fica associada ao `event_id` da resposta.

A página **Qualidade** mostra:

- total de buscas no período;
- buscas repetidas e total de repetições;
- tempo médio de resposta;
- buscas e repetições por assunto;
- perguntas mais refeitas;
- erros e dúvidas por assunto.

A classificação do assunto usa regras determinísticas e as ferramentas chamadas. Não há custo adicional de LLM para classificar.

## Privacidade

- Não armazene a chave OpenAI nem o JSON da conta de serviço nas tabelas.
- Configure retenção/particionamento por `created_at` conforme a política de LGPD do projeto.
- A página Histórico continua mostrando apenas a sessão atual; a análise persistente fica na página Qualidade.
