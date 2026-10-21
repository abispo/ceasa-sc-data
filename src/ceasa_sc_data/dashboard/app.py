import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine, text
from streamlit_autorefresh import st_autorefresh

from ceasa_sc_data import config

st.set_page_config(page_title="CEASA/SC — Cotações", layout="wide")

st_autorefresh(interval=30_000, key="ceasa_refresh")


@st.cache_resource
def _engine():
    return create_engine(config.DATABASE_URL)


def _query(sql: str, params: dict | None = None) -> pd.DataFrame:
    with _engine().connect() as conn:
        return pd.read_sql_query(text(sql), conn, params=params or {})


st.title("Cotações de Preços — CEASA/SC")

try:
    unidades = _query("SELECT DISTINCT unidade FROM silver.cotacoes ORDER BY 1")
    produtos = _query("SELECT DISTINCT produto FROM silver.cotacoes ORDER BY 1")
    carregado = not unidades.empty and not produtos.empty
except Exception:
    carregado = False

if not carregado:
    st.warning(
        "Banco ainda em construção (backfill em andamento). "
        "Esta página atualiza sozinha a cada 30 s."
    )
    st.stop()

col1, col2 = st.columns(2)
unidade = col1.selectbox("Unidade", unidades["unidade"].tolist())
produto = col2.selectbox("Produto", produtos["produto"].tolist())

df = _query(
    """
    SELECT data, produto, variedade, classificacao, tipo, origem,
           embalagem, peso_kg, preco_min, preco_comum, preco_max, preco_comum_kg
    FROM silver.cotacoes
    WHERE unidade = :unidade AND produto = :produto
    ORDER BY data
    """,
    {"unidade": unidade, "produto": produto},
)

if df.empty:
    st.info("Sem dados para o filtro selecionado.")
else:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Última cotação", f"R$ {df['preco_comum'].iloc[-1]:,.2f}")
    c2.metric("Mín. período", f"R$ {df['preco_comum'].min():,.2f}")
    c3.metric("Máx. período", f"R$ {df['preco_comum'].max():,.2f}")
    c4.metric("Observações", f"{len(df)}")

    fig = px.line(df, x="data", y="preco_comum", color="variedade", title="Preço comum ao longo do tempo")
    st.plotly_chart(fig, width="stretch")

    st.subheader("Dados")
    st.dataframe(df, width="stretch")
