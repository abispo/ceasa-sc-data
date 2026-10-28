---
name: run-pipeline
description: Use when asked to rodar/executar o pipeline CEASA/SC (ingest, parse, dashboard), popular ou atualizar o banco de cotações, ou validar os dados em bronze/silver/gold. Cobre DATABASE_URL, docker compose db, ingest incremental, parse idempotente e verificação de contagem em silver.cotacoes.
---

# Rodar o pipeline CEASA/SC

Fluxo completo para baixar os PDFs, carregar no PostgreSQL (bronze → silver →
gold) e validar o resultado. O pipeline é **idempotente**: re-rodar não duplica.

## Pré-requisitos

1. **Banco de pé**. Para Postgres local (16 via Docker):

   ```bash
   docker compose up -d db
   ```

   Expõe `localhost:5432` (postgres/postgres, db `ceasa`).

2. **`DATABASE_URL`**. Default já usado pelo docker-compose:

   ```bash
   export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ceasa
   ```

   Sem ela, `parse` e `dashboard` falham. `ingest` não precisa de banco.

3. **Ambiente** (uma vez):

   ```bash
   uv sync
   ```

## Passo a passo

```bash
uv run ceasa-sc-data ingest     # 1. baixa os PDFs (incremental via manifest)
uv run ceasa-sc-data parse      # 2. extrai e carrega bronze → silver → gold
```

Variações úteis:

```bash
uv run ceasa-sc-data ingest --year 2025        # ano específico (repetível)
uv run ceasa-sc-data ingest --since 2026-10-01 # só a partir de uma data
uv run ceasa-sc-data ingest --all              # inclui "Anos Anteriores" (2017..2019)
uv run ceasa-sc-data ingest --force            # re-baixa arquivos já presentes
uv run ceasa-sc-data parse --full              # reconstrói o bronze do zero
```

## Verificação (sempre confirme após o parse)

Consultar as camadas e checar se há dados:

```bash
psql "$DATABASE_URL" -c "SELECT count(*) FROM bronze.cotacoes_raw"
psql "$DATABASE_URL" -c "SELECT count(*) FROM silver.cotacoes"
psql "$DATABASE_URL" -c "SELECT max(data) FROM silver.cotacoes"
```

Uma contagem `0` em `silver.cotacoes` costuma ser um destes casos:
- `parse` ainda não rodou;
- `DATABASE_URL` errado (aponta para outro banco);
- nenhum PDF baixado (`data/raw/pdfs/` vazio) — rode `ingest` antes.

## Subir o dashboard

```bash
uv run ceasa-sc-data dashboard   # Streamlit em http://localhost:8501
```

## Gotchas

- `ingest` pula arquivos já no manifest (`data/raw/manifest.csv`); para re-baixar,
  use `--force`.
- `parse` só processa PDFs cujo `arquivo` ainda não está em `bronze`; para
  re-processar tudo, use `--full`.
- A chave natural de `silver.cotacoes` deduplica por
  `(data, unidade, produto, variedade, classificacao, tipo, origem, embalagem)`,
  então re-rodar `parse` não duplica.
- Se as colunas do PDF mudarem, ajuste `COLUMNS` em `src/ceasa_sc_data/parse/parser.py`.
