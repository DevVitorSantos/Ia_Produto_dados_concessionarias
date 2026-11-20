import streamlit as st

from ui.profile_popup import render_profile_popup

st.set_page_config(
    page_title="AI Analytics Assistant — Concessionárias",
    page_icon="A",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_profile_popup()

st.title("AI Analytics Assistant — Concessionárias")
st.subheader("Análise de vendas com linguagem natural sobre a camada Gold do BigQuery")

st.markdown(
    """
    Use o menu lateral para navegar:

    - **Chat IA** — pergunte em português e receba respostas com números, tabelas e gráficos.
    - **Indicadores** — veja os KPIs oficiais com filtros de período.
    - **Histórico** — acompanhe as perguntas e respostas da sessão.
    - **Qualidade** — veja buscas repetidas e notas de satisfatória, dúvidas ou resultado errado.
    """
)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Período analisado", "2025-01-01 a 2026-07-02")
with col2:
    st.metric("Métricas oficiais", "9")
with col3:
    st.metric("Dimensões", "28")

st.info(
    "Os dados de clientes podem conter rótulos sintéticos 'Cliente #' quando não houve correspondência em dim_cliente. "
    "Metas e previsões não fazem parte da base Gold."
)

with st.sidebar:
    st.header("Configuração")
    st.caption(
        "Credenciais BigQuery e OpenAI devem ser configuradas via variáveis de ambiente ou "
        "`.streamlit/secrets.toml`. Nunca compartilhe chaves."
    )
