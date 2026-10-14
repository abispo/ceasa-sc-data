import duckdb

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
    peso_kg DOUBLE,
    preco_min DOUBLE,
    preco_comum DOUBLE,
    preco_max DOUBLE,
    preco_comum_kg DOUBLE
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
    peso_kg DOUBLE,
    preco_min DOUBLE,
    preco_comum DOUBLE,
    preco_max DOUBLE,
    preco_comum_kg DOUBLE,
    PRIMARY KEY (data, unidade, produto, variedade, classificacao, tipo, origem, embalagem)
);

CREATE TABLE IF NOT EXISTS silver.dim_unidade (
    unidade VARCHAR PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS silver.dim_produto (
    produto VARCHAR PRIMARY KEY
);
"""


def connect() -> duckdb.DuckDBPyConnection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(config.DB_PATH))
    conn.execute(SCHEMA_BRONZE)
    conn.execute(SCHEMA_SILVER)
    return conn


def insert_bronze(conn: duckdb.DuckDBPyConnection, rows: list[dict]) -> None:
    if not rows:
        return
    conn.executemany(
        """
        INSERT INTO bronze.cotacoes_raw
        (arquivo, data, unidade, produto, variedade, classificacao, tipo,
         origem, embalagem, peso_kg, preco_min, preco_comum, preco_max, preco_comum_kg)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                r["arquivo"],
                r["data"],
                r["unidade"],
                r["produto"],
                r["variedade"],
                r["classificacao"],
                r["tipo"],
                r["origem"],
                r["embalagem"],
                r["peso_kg"],
                r["preco_min"],
                r["preco_comum"],
                r["preco_max"],
                r["preco_comum_kg"],
            )
            for r in rows
        ],
    )


def build_silver(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO silver.cotacoes
        SELECT
            CAST(strptime(data, '%d/%m/%Y') AS DATE),
            unidade,
            produto,
            variedade,
            classificacao,
            tipo,
            origem,
            embalagem,
            peso_kg,
            preco_min,
            preco_comum,
            preco_max,
            preco_comum_kg
        FROM bronze.cotacoes_raw
        WHERE data IS NOT NULL
        """
    )
    conn.execute(
        "INSERT OR REPLACE INTO silver.dim_unidade SELECT DISTINCT unidade FROM silver.cotacoes"
    )
    conn.execute(
        "INSERT OR REPLACE INTO silver.dim_produto SELECT DISTINCT produto FROM silver.cotacoes"
    )


def build_gold(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("CREATE SCHEMA IF NOT EXISTS gold")
    conn.execute(
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
    conn.execute(
        """
        CREATE OR REPLACE VIEW gold.preco_por_produto AS
        SELECT
            data,
            produto,
            unidade,
            variedade,
            classificacao,
            origem,
            embalagem,
            peso_kg,
            preco_min,
            preco_comum,
            preco_max,
            preco_comum_kg
        FROM silver.cotacoes
        """
    )
