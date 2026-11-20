# Fase 4 — Integração com OpenAI e Function Calling

## Status

Implementação concluída com testes automatizados. Validação ponta a ponta com a API real fica pendente até que uma chave OpenAI válida seja configurada fora do chat.

> A chave enviada no chat estava exposta e deve ser revogada. O código nunca grava nem repete o valor da chave.

## Arquitetura

- `agent/instructions.py`: instruções em pt-BR, limites da base, regras de desconto,aviso de clientes sintéticos e proibição de SQL livre.
- `agent/tools.py`: contratos das 5 ferramentas e executor validado.
- `queries/analytics.py`: consultas parametrizadas à `vw_fato_completa`, sempre derivadas da camada semântica.
- `services/openai_service.py`: loop da Responses API com `function_call` e `function_call_output`.
- `services/response_service.py`: normalização da resposta final e avisos automáticos.

## Fluxo da Responses API

1. `client.responses.create(...)` com `instructions`, `input`, `tools` e `store=False`.
2. Se houver `function_call`, o arguments é parseado e executado apenas pelo executor controlado.
3. O resultado é anexado como `function_call_output` com o `call_id` original.
4. O histórico completo é reenviado até o modelo produzir uma mensagem final.
5. O limite de 6 rodadas evita loops infinitos.

## Ferramentas

| Ferramenta | Finalidade |
|---|---|
| `get_kpi` | Valor de uma métrica oficial, com filtros opcionais. |
| `get_ranking` | Ranking de métrica por dimensão permitida. |
| `compare_periods` | Comparação entre dois períodos com variação absoluta e percentual. |
| `get_trend` | Série por dia, mês, trimestre ou ano. |
| `get_filtered_data` | Linhas detalhadas de colunas permitidas. |

Nenhuma ferramenta aceita SQL arbitrário. Nomes de métricas, dimensões, colunas e operadores vêm de listas fixas da camada semântica; valores são enviados como parâmetros tipados do BigQuery.

## Configuração

Defina localmente, sem colar a chave no chat:

```powershell
$env:OPENAI_API_KEY = "sua-chave-nova"
$env:OPENAI_MODEL = "gpt-6-luna"
```

Ou preencha `.streamlit/secrets.toml`, que já está protegido pelo `.gitignore`, usando `.streamlit/secrets.toml.example` como modelo.

## Formato padrão da resposta

O agente deve encerrar toda resposta com um único objeto JSON válido, sem Markdown, com esta estrutura:

```json
{
  "resumo": "Storytelling do dado: qual pergunta de negócio ele responde, o destaque e por que isso importa.",
  "resposta": "Frase curta descrevendo o gráfico gerado automaticamente a partir das ferramentas.",
  "prova": "Frase curta descrevendo a tabela de referência gerada automaticamente a partir das ferramentas.",
  "sugestoes": [
    {
      "rotulo": "Texto do botão",
      "pergunta": "Pergunta completa que dispara uma nova busca ao ser clicada."
    }
  ]
}
```

O serviço aceita o JSON com ou sem cercas de código e mantém compatibilidade com respostas antigas em texto simples. Quando o modelo não fornece sugestões, o `ResponseService` cria sugestões padrão compatíveis com as ferramentas disponíveis.

## Testes

```powershell
.venv/Scripts/python -m pytest -q
```

Resultado: 26 testes aprovados.

Smoke test real, após configurar a chave rotacionada:

```powershell
.venv/Scripts/python scripts/smoke_test_openai.py
```

## Dependências

- `openai>=2.8,<4` adicionado a `requirements.txt`.
- SDK instalado no `.venv`: `openai 3.56.0`.

## Próxima etapa

Fase 5 implementada em `docs/fase5_interface_streamlit.md`, com quatro páginas do MVP e visualizações sobre as respostas do agente.
