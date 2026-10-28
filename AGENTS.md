# AGENTS.md — Guia para agentes de IA

Instruções para assistentes de IA (e desenvolvedores) trabalharem neste repositório.

## O que é este projeto

Pipeline de engenharia de dados que consome os PDFs de cotação de preços da
CEASA/SC e entrega um banco analítico (PostgreSQL) consultado por um dashboard
Streamlit. Arquitetura Medallion: bronze → silver → gold.

- Stack: Python 3.12 + `uv` + PostgreSQL + Streamlit + Plotly.
- Documentação de referência: `docs/arquitetura.md` (stack, modelo de dados,
  decisões) e `docs/guia-de-uso.md` (uso e troubleshooting).

## Comandos essenciais

Gerenciamento de ambiente e dependências:

```bash
uv sync                 # cria o ambiente e instala as dependências
uv run pytest           # roda a suíte de testes
```

Banco local (PostgreSQL 16 via Docker):

```bash
docker compose up -d db # expõe localhost:5432 (postgres/postgres, db ceasa)
```

CLI do pipeline (`uv run ceasa-sc-data <comando>`):

```bash
uv run ceasa-sc-data ingest     # baixa os PDFs (anos padrão 2020..2026)
uv run ceasa-sc-data parse      # extrai e carrega no PostgreSQL (bronze → silver → gold)
uv run ceasa-sc-data dashboard  # sobe o Streamlit em :8501
```

`parse` e `dashboard` exigem `DATABASE_URL` apontando para um PostgreSQL. O
default (usado pelo docker-compose) é
`postgresql://postgres:postgres@localhost:5432/ceasa`.

## Estrutura do código

```
src/ceasa_sc_data/
├── config.py       # constantes (URLs, caminhos, anos padrão, DATABASE_URL)
├── main.py         # CLI (typer): ingest / parse / dashboard
├── ingest/         # crawler.py (descoberta ano → mês → PDF) + downloader.py (manifest incremental)
├── parse/          # parser.py (extração de colunas por coordenada-x via pdfplumber)
├── store/          # db.py (schema bronze/silver/gold) + build.py (orquestração parse → carga)
└── dashboard/      # app.py (Streamlit)
```

- `data/` é gerado em runtime e está no `.gitignore`.
- O ponto de entrada da CLI é `src/ceasa_sc_data/main.py:app`.

## Convenções de código

- Python 3.12, tipagem (`from __future__`/type hints) e docstrings em português.
- Não adicione dependências sem passar pelo `pyproject.toml` + `uv.lock`
  (use `uv add <pkg>`).
- O pipeline deve permanecer **idempotente**: `ingest` é incremental via
  `data/raw/manifest.csv`; `parse` só processa PDFs ainda não carregados
  (`--full` reconstrói o bronze do zero).
- Formatação numérica: PDFs usam vírgula decimal (`150,00`); a coluna
  `Comum/Kg` usa ponto (`15.00`). Ambos devem virar `float`.

## Gotchas

- Separação produto × variedade é geométrica; nomes curtos (`Uva Benitaka`)
  deixam a variedade embutida em `produto`. Correção semântica pendente na
  camada silver (lista-mestre do portal).
- Se as colunas do PDF mudarem, ajuste as coordenadas em `parse/parser.py`
  (`COLUMNS`).
- Sempre rode `uv run pytest` após alterações; não há lint/typecheck configurado.
