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


def latest_data():
    engine = connect()
    try:
        with engine.connect() as conn:
            return conn.execute(text("SELECT max(data) FROM silver.cotacoes")).scalar()
    finally:
        engine.dispose()
