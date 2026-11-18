from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine, text
from streamlit_autorefresh import st_autorefresh

from ceasa_sc_data import config

st.set_page_config(page_title="CEASA/SC — Cotações", layout="wide")

st_autorefresh(interval=30_000, key="ceasa_refresh")

# Ordem define a cascata: cada filtro é restrito pelos selecionados acima.
DIMENSOES = [
    "unidade",
    "produto",
    "variedade",
    "classificacao",
    "tipo",
    "origem",
    "embalagem",
]
ROTULOS = {
    "unidade": "Unidade",
    "produto": "Produto",
    "variedade": "Variedade",
    "classificacao": "Classificação",
    "tipo": "Tipo",
    "origem": "Origem",
    "embalagem": "Embalagem",
}
PRECOS = {
    "preco_min": "Preço mínimo",
    "preco_comum": "Preço comum",
    "preco_max": "Preço máximo",
    "preco_comum_kg": "Preço comum/kg",
}
NOMES_MES = [
    "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
]


@st.cache_resource
def _engine():
    return create_engine(config.DATABASE_URL)


@st.cache_data(ttl=30, show_spinner=False)
def _query(sql: str, params: tuple[tuple[str, object], ...] = ()) -> pd.DataFrame:
    with _engine().connect() as conn:
        return pd.read_sql_query(text(sql), conn, params=dict(params))


def _distinct(col: str, selecoes: dict[str, list]) -> pd.DataFrame:
    idx = DIMENSOES.index(col)
    wheres: list[str] = []
    params: dict[str, list] = {}
    for c in DIMENSOES[:idx]:
        vals = selecoes.get(c) or []
        if vals:
            wheres.append(f"{c} = ANY(:{c})")
            params[c] = list(vals)

    sql = f"SELECT DISTINCT {col} AS valor FROM silver.cotacoes"
    if wheres:
        sql += " WHERE " + " AND ".join(wheres)
    sql += " ORDER BY 1"
    return _query(sql, tuple(sorted(params.items())))


def _build_where(selecoes: dict[str, list], data_ini, data_fim) -> tuple[str, dict]:
    wheres: list[str] = []
    params: dict[str, object] = {}
    for c in DIMENSOES:
        vals = selecoes.get(c) or []
        if vals:
            wheres.append(f"{c} = ANY(:{c})")
            params[c] = list(vals)
    wheres.append("data >= :data_ini")
    wheres.append("data <= :data_fim")
    params["data_ini"] = data_ini
    params["data_fim"] = data_fim
    return " AND ".join(wheres), params


st.title("Cotações de Preços — CEASA/SC")

try:
    extremos = _query("SELECT min(data) AS dmin, max(data) AS dmax FROM silver.cotacoes")
    carregado = not extremos.empty and pd.notna(extremos["dmin"].iloc[0])
except Exception:
    carregado = False

if not carregado:
    st.warning(
        "Banco ainda em construção (backfill em andamento). "
        "Esta página atualiza sozinha a cada 30 s."
    )
    st.stop()

_dmin = pd.Timestamp(extremos["dmin"].iloc[0]).date()
_dmax = pd.Timestamp(extremos["dmax"].iloc[0]).date()

# --- Sidebar: filtros -------------------------------------------------------
st.sidebar.header("Filtros")

periodo = st.sidebar.date_input(
    "Período", value=(_dmin, _dmax), min_value=_dmin, max_value=_dmax
)
if isinstance(periodo, (tuple, list)) and len(periodo) == 2:
    data_ini, data_fim = periodo
else:
    data_ini = data_fim = periodo

selecoes: dict[str, list] = {}
for col in DIMENSOES:
    opcoes = _distinct(col, selecoes)["valor"].tolist()
    selecoes[col] = st.sidebar.multiselect(ROTULOS[col], opcoes)

col_preco = st.sidebar.selectbox("Preço a exibir", list(PRECOS), format_func=PRECOS.get)

# --- Dados filtrados --------------------------------------------------------
where, params = _build_where(selecoes, data_ini, data_fim)
df = _query(
    f"""
    SELECT data, unidade, produto, variedade, classificacao, tipo, origem,
           embalagem, peso_kg, preco_min, preco_comum, preco_max, preco_comum_kg
    FROM silver.cotacoes
    WHERE {where}
    """,
    tuple(sorted(params.items())),
)

if df.empty:
    st.info("Sem dados para os filtros selecionados.")
else:
    df["data"] = pd.to_datetime(df["data"])

    # --- KPIs -------------------------------------------------------------------
    ultima_data = df["data"].max()
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Última cotação", f"R$ {df.loc[df['data'] == ultima_data, col_preco].mean():,.2f}")
    k2.metric("Média do período", f"R$ {df[col_preco].mean():,.2f}")
    k3.metric("Mínimo", f"R$ {df[col_preco].min():,.2f}")
    k4.metric("Máximo", f"R$ {df[col_preco].max():,.2f}")
    k5.metric("Observações", f"{len(df):,}")

    tab_serie, tab_ranking, tab_unidades, tab_sazonalidade, tab_dados = st.tabs(
        ["Série temporal", "Ranking", "Unidades", "Sazonalidade", "Dados"]
    )

    # --- Série temporal ---------------------------------------------------------
    with tab_serie:
        c1, c2 = st.columns(2)
        granularidade = c1.selectbox(
            "Granularidade", ["Dia", "Semana", "Mês"], key="granularidade"
        )
        agrupar_por = c2.selectbox(
            "Agrupar por", DIMENSOES, index=1, format_func=ROTULOS.get
        )

        freq = {"Dia": "D", "Semana": "W", "Mês": "ME"}[granularidade]
        serie = df.dropna(subset=[col_preco]).copy()
        serie["periodo"] = serie["data"].dt.to_period(freq).dt.to_timestamp()
        agg = (
            serie.groupby(["periodo", agrupar_por], as_index=False)[col_preco]
            .mean()
            .rename(columns={col_preco: "preco"})
        )

        fig = px.line(
            agg,
            x="periodo",
            y="preco",
            color=agrupar_por,
            title=f"{PRECOS[col_preco]} ao longo do tempo",
            labels={"periodo": "Data", "preco": PRECOS[col_preco]},
        )
        st.plotly_chart(fig, width="stretch")

    # --- Ranking ----------------------------------------------------------------
    with tab_ranking:
        top_n = st.slider("Top produtos", 5, 50, 20, key="top_n")
        ranking = (
            df.dropna(subset=[col_preco])
            .groupby("produto", as_index=False)[col_preco]
            .mean()
            .sort_values(col_preco, ascending=False)
            .head(top_n)
        )
        fig = px.bar(
            ranking,
            x=col_preco,
            y="produto",
            orientation="h",
            title=f"Top {top_n} produtos por {PRECOS[col_preco].lower()}",
            labels={col_preco: PRECOS[col_preco]},
        )
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, width="stretch")

    # --- Unidades ---------------------------------------------------------------
    with tab_unidades:
        fig = px.box(
            df.dropna(subset=[col_preco]),
            x="unidade",
            y=col_preco,
            points="outliers",
            title=f"Distribuição de {PRECOS[col_preco].lower()} por unidade",
            labels={"unidade": "Unidade", col_preco: PRECOS[col_preco]},
        )
        st.plotly_chart(fig, width="stretch")

    # --- Sazonalidade -----------------------------------------------------------
    with tab_sazonalidade:
        saz = df.dropna(subset=[col_preco]).copy()
        saz["mes"] = saz["data"].dt.month
        mensal = saz.groupby("mes", as_index=False)[col_preco].mean()
        mensal["mes_nome"] = mensal["mes"].map(lambda m: NOMES_MES[m - 1])

        fig = px.line(
            mensal,
            x="mes_nome",
            y=col_preco,
            markers=True,
            title=f"Sazonalidade — {PRECOS[col_preco].lower()} médio por mês",
            labels={"mes_nome": "Mês", col_preco: PRECOS[col_preco]},
        )
        st.plotly_chart(fig, width="stretch")

        st.markdown("#### Média móvel")
        janela = st.slider("Janela (dias)", 3, 60, 30, key="janela_mm")
        diario = (
            saz.groupby("data", as_index=False)[col_preco]
            .mean()
            .sort_values("data")
        )
        diario["média móvel"] = diario[col_preco].rolling(janela, min_periods=1).mean()
        fig = px.line(
            diario,
            x="data",
            y=[col_preco, "média móvel"],
            title="Série diária e média móvel",
            labels={"data": "Data", "value": PRECOS[col_preco]},
        )
        st.plotly_chart(fig, width="stretch")

    # --- Dados ------------------------------------------------------------------
    with tab_dados:
        st.dataframe(df, width="stretch")
        st.download_button(
            "Baixar CSV",
            df.to_csv(index=False).encode("utf-8"),
            file_name="cotacoes_ceasa.csv",
            mime="text/csv",
        )

# --- Clima ------------------------------------------------------------------
st.divider()
st.header("Clima — INMET (Santa Catarina)")

try:
    clima_extremos = _query(
        "SELECT min(data) AS dmin, max(data) AS dmax FROM gold.clima_diario"
    )
    clima_ok = not clima_extremos.empty and pd.notna(clima_extremos["dmin"].iloc[0])
except Exception:
    clima_ok = False

if not clima_ok:
    st.info(
        "Dados de clima ainda não carregados. Rode `ceasa-sc-data clima ingest` "
        "e `ceasa-sc-data clima parse`."
    )
else:
    _cmin = pd.Timestamp(clima_extremos["dmin"].iloc[0]).date()
    _cmax = pd.Timestamp(clima_extremos["dmax"].iloc[0]).date()

    municipios = _query(
        "SELECT DISTINCT municipio FROM gold.clima_diario ORDER BY municipio"
    )["municipio"].tolist()

    c1, c2 = st.columns([1, 2])
    sel_municipios = c1.multiselect("Municípios", municipios, key="clima_municipios")
    clima_periodo = c2.date_input(
        "Período",
        value=(_cmin, _cmax),
        min_value=_cmin,
        max_value=_cmax,
        key="clima_periodo",
    )
    if isinstance(clima_periodo, (tuple, list)) and len(clima_periodo) == 2:
        c_ini, c_fim = clima_periodo
    else:
        c_ini = c_fim = clima_periodo

    clima_where: list[str] = []
    clima_params: dict[str, object] = {}
    if sel_municipios:
        clima_where.append("municipio = ANY(:municipios)")
        clima_params["municipios"] = list(sel_municipios)
    clima_where.append("data >= :data_ini")
    clima_where.append("data <= :data_fim")
    clima_params["data_ini"] = c_ini
    clima_params["data_fim"] = c_fim

    clima_df = _query(
        f"""
        SELECT municipio, estacao, data, precip_mm, temp_min_c, temp_max_c,
               temp_media_c, umidade_media_pct
        FROM gold.clima_diario
        WHERE {' AND '.join(clima_where)}
        ORDER BY data
        """,
        tuple(sorted(clima_params.items())),
    )

    if clima_df.empty:
        st.info("Sem dados de clima para os filtros selecionados.")
    else:
        clima_df["data"] = pd.to_datetime(clima_df["data"])

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Precipitação acumulada", f"{clima_df['precip_mm'].sum():,.1f} mm")
        k2.metric("Temp. mínima", f"{clima_df['temp_min_c'].min():,.1f} °C")
        k3.metric("Temp. máxima", f"{clima_df['temp_max_c'].max():,.1f} °C")
        k4.metric("Temp. média", f"{clima_df['temp_media_c'].mean():,.1f} °C")
        k5.metric("Umidade média", f"{clima_df['umidade_media_pct'].mean():,.1f} %")

        col_temp, col_chuva = st.columns(2)
        with col_temp:
            temp = (
                clima_df.groupby("data", as_index=False)
                .agg(
                    temp_min=("temp_min_c", "min"),
                    temp_media=("temp_media_c", "mean"),
                    temp_max=("temp_max_c", "max"),
                )
            )
            fig = px.line(
                temp,
                x="data",
                y=["temp_min", "temp_media", "temp_max"],
                title="Temperatura diária (mín / média / máx)",
                labels={"data": "Data", "value": "°C", "variable": "Série"},
            )
            st.plotly_chart(fig, width="stretch")
        with col_chuva:
            chuva = clima_df.groupby("data", as_index=False)["precip_mm"].sum()
            fig = px.bar(
                chuva,
                x="data",
                y="precip_mm",
                title="Precipitação diária",
                labels={"data": "Data", "precip_mm": "mm"},
            )
            st.plotly_chart(fig, width="stretch")

        col_umid, col_tabela = st.columns([2, 3])
        with col_umid:
            umid = clima_df.groupby("data", as_index=False)["umidade_media_pct"].mean()
            fig = px.line(
                umid,
                x="data",
                y="umidade_media_pct",
                title="Umidade relativa média",
                labels={"data": "Data", "umidade_media_pct": "%"},
            )
            st.plotly_chart(fig, width="stretch")
        with col_tabela:
            st.markdown("#### Dados por município")
            st.dataframe(clima_df, width="stretch")
