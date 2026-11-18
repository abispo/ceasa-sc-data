from sqlalchemy import create_engine, text

from ceasa_sc_data import config

SCHEMA_BRONZE = """
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE TABLE IF NOT EXISTS bronze.cotacoes_raw (
    arquivo VARCHAR,
    data VARCHAR,
    unidade VARCHAR,
    produto VARCHAR,
    variedade VARCHAR,
    classificacao VARCHAR,
    tipo VARCHAR,
    origem VARCHAR,
    embalagem VARCHAR,
    peso_kg DOUBLE PRECISION,
    preco_min DOUBLE PRECISION,
    preco_comum DOUBLE PRECISION,
    preco_max DOUBLE PRECISION,
    preco_comum_kg DOUBLE PRECISION
);
"""

SCHEMA_SILVER = """
CREATE SCHEMA IF NOT EXISTS silver;

CREATE TABLE IF NOT EXISTS silver.cotacoes (
    data DATE,
    unidade VARCHAR,
    produto VARCHAR,
    variedade VARCHAR,
    classificacao VARCHAR,
    tipo VARCHAR,
    origem VARCHAR,
    embalagem VARCHAR,
    peso_kg DOUBLE PRECISION,
    preco_min DOUBLE PRECISION,
    preco_comum DOUBLE PRECISION,
    preco_max DOUBLE PRECISION,
    preco_comum_kg DOUBLE PRECISION,
    PRIMARY KEY (data, unidade, produto, variedade, classificacao, tipo, origem, embalagem)
);

CREATE TABLE IF NOT EXISTS silver.dim_unidade (
    unidade VARCHAR PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS silver.dim_produto (
    produto VARCHAR PRIMARY KEY
);
"""


def connect():
    engine = create_engine(config.DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text(SCHEMA_BRONZE))
        conn.execute(text(SCHEMA_SILVER))
        conn.execute(text(SCHEMA_CLIMA_BRONZE))
        conn.execute(text(SCHEMA_CLIMA_SILVER))
    return engine


def insert_bronze(conn, rows: list[dict]) -> None:
    if not rows:
        return
    conn.execute(
        text(
            """
            INSERT INTO bronze.cotacoes_raw
            (arquivo, data, unidade, produto, variedade, classificacao, tipo,
             origem, embalagem, peso_kg, preco_min, preco_comum, preco_max, preco_comum_kg)
            VALUES (:arquivo, :data, :unidade, :produto, :variedade, :classificacao,
                    :tipo, :origem, :embalagem, :peso_kg, :preco_min, :preco_comum,
                    :preco_max, :preco_comum_kg)
            """
        ),
        rows,
    )


def build_silver(conn) -> None:
    conn.execute(
        text(
            """
            INSERT INTO silver.cotacoes
            (data, unidade, produto, variedade, classificacao, tipo, origem, embalagem,
             peso_kg, preco_min, preco_comum, preco_max, preco_comum_kg)
            SELECT
                TO_DATE(data, 'DD/MM/YYYY'),
                unidade, produto, variedade, classificacao, tipo, origem, embalagem,
                peso_kg, preco_min, preco_comum, preco_max, preco_comum_kg
            FROM (
                SELECT DISTINCT ON (data, unidade, produto, variedade, classificacao, tipo, origem, embalagem)
                    data, unidade, produto, variedade, classificacao, tipo, origem, embalagem,
                    peso_kg, preco_min, preco_comum, preco_max, preco_comum_kg
                FROM bronze.cotacoes_raw
                WHERE data IS NOT NULL
                ORDER BY data, unidade, produto, variedade, classificacao, tipo, origem, embalagem
            ) t
            ON CONFLICT (data, unidade, produto, variedade, classificacao, tipo, origem, embalagem)
            DO UPDATE SET
                peso_kg = EXCLUDED.peso_kg,
                preco_min = EXCLUDED.preco_min,
                preco_comum = EXCLUDED.preco_comum,
                preco_max = EXCLUDED.preco_max,
                preco_comum_kg = EXCLUDED.preco_comum_kg
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO silver.dim_unidade (unidade)
            SELECT DISTINCT unidade FROM silver.cotacoes
            ON CONFLICT (unidade) DO NOTHING
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO silver.dim_produto (produto)
            SELECT DISTINCT produto FROM silver.cotacoes
            ON CONFLICT (produto) DO NOTHING
            """
        )
    )


def build_gold(conn) -> None:
    conn.execute(text("CREATE SCHEMA IF NOT EXISTS gold"))
    conn.execute(
        text(
            """
            CREATE OR REPLACE VIEW gold.preco_medio_mensal AS
            SELECT
                date_trunc('month', data) AS mes,
                produto,
                unidade,
                avg(preco_comum) AS preco_medio,
                count(*) AS n_observacoes
            FROM silver.cotacoes
            WHERE preco_comum IS NOT NULL
            GROUP BY 1, 2, 3
            """
        )
    )
    conn.execute(
        text(
            """
            CREATE OR REPLACE VIEW gold.preco_por_produto AS
            SELECT
                data, produto, unidade, variedade, classificacao, origem, embalagem,
                peso_kg, preco_min, preco_comum, preco_max, preco_comum_kg
            FROM silver.cotacoes
            """
        )
    )


CLIMA_NUMERIC_COLUMNS = [
    "precip_mm",
    "pressao_mb",
    "pressao_max_mb",
    "pressao_min_mb",
    "radiacao_kjm2",
    "temp_c",
    "temp_orvalho_c",
    "temp_max_c",
    "temp_min_c",
    "temp_orvalho_max_c",
    "temp_orvalho_min_c",
    "umidade_max_pct",
    "umidade_min_pct",
    "umidade_pct",
    "vento_direcao_graus",
    "vento_rajada_ms",
    "vento_velocidade_ms",
]


def _clima_col_defs() -> str:
    return ",\n    ".join(f"{c} DOUBLE PRECISION" for c in CLIMA_NUMERIC_COLUMNS)


SCHEMA_CLIMA_BRONZE = f"""
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE TABLE IF NOT EXISTS bronze.clima_raw (
    arquivo VARCHAR,
    estacao VARCHAR,
    data_hora TIMESTAMP,
    {_clima_col_defs()}
);
"""

SCHEMA_CLIMA_SILVER = f"""
CREATE SCHEMA IF NOT EXISTS silver;
CREATE TABLE IF NOT EXISTS silver.clima (
    data_hora TIMESTAMP,
    estacao VARCHAR,
    {_clima_col_defs()},
    PRIMARY KEY (data_hora, estacao)
);
CREATE TABLE IF NOT EXISTS silver.dim_estacao (
    estacao VARCHAR PRIMARY KEY,
    nome VARCHAR,
    uf VARCHAR,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    altitude DOUBLE PRECISION,
    data_fundacao DATE
);
"""


def insert_clima_bronze(conn, rows: list[dict]) -> None:
    if not rows:
        return
    cols = ["arquivo", "estacao", "data_hora", *CLIMA_NUMERIC_COLUMNS]
    sql = (
        f"INSERT INTO bronze.clima_raw ({', '.join(cols)}) "
        f"VALUES ({', '.join(':' + c for c in cols)})"
    )
    conn.execute(text(sql), rows)


def upsert_estacao(conn, station: dict) -> None:
    if not station.get("estacao"):
        return
    conn.execute(
        text(
            """
            INSERT INTO silver.dim_estacao
            (estacao, nome, uf, latitude, longitude, altitude, data_fundacao)
            VALUES (:estacao, :nome, :uf, :latitude, :longitude, :altitude, :data_fundacao)
            ON CONFLICT (estacao) DO UPDATE SET
                nome = EXCLUDED.nome,
                uf = EXCLUDED.uf,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                altitude = EXCLUDED.altitude,
                data_fundacao = EXCLUDED.data_fundacao
            """
        ),
        station,
    )


def build_clima_silver(conn) -> None:
    cols = ["data_hora", "estacao", *CLIMA_NUMERIC_COLUMNS]
    col_list = ", ".join(cols)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in CLIMA_NUMERIC_COLUMNS)
    conn.execute(
        text(
            f"""
            INSERT INTO silver.clima ({col_list})
            SELECT DISTINCT ON (data_hora, estacao) {col_list}
            FROM bronze.clima_raw
            WHERE data_hora IS NOT NULL
            ORDER BY data_hora, estacao
            ON CONFLICT (data_hora, estacao)
            DO UPDATE SET {updates}
            """
        )
    )


def build_clima_gold(conn) -> None:
    conn.execute(text("CREATE SCHEMA IF NOT EXISTS gold"))
    conn.execute(
        text(
            """
            CREATE OR REPLACE VIEW gold.clima_diario AS
            SELECT
                e.estacao,
                e.nome AS municipio,
                date_trunc('day', c.data_hora)::date AS data,
                sum(c.precip_mm) AS precip_mm,
                min(c.temp_min_c) AS temp_min_c,
                max(c.temp_max_c) AS temp_max_c,
                avg(c.temp_c) AS temp_media_c,
                avg(c.umidade_pct) AS umidade_media_pct
            FROM silver.clima c
            JOIN silver.dim_estacao e ON e.estacao = c.estacao
            GROUP BY 1, 2, 3
            """
        )
    )


def latest_data():
    engine = connect()
    try:
        with engine.connect() as conn:
            return conn.execute(text("SELECT max(data) FROM silver.cotacoes")).scalar()
    finally:
        engine.dispose()
