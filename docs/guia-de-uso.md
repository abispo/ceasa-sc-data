# Guia de Uso

Passo a passo para rodar o pipeline, do zero até o dashboard.

## 1. Pré-requisitos

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) (instalador e gerenciador de ambiente)
- PostgreSQL acessível (defina `DATABASE_URL`)

## 2. Instalação

```bash
uv sync
```

Isso cria o ambiente virtual e instala as dependências a partir do `uv.lock`.

Para um PostgreSQL local (teste do `parse`/dashboard), use o `docker-compose.yml`:

```bash
docker compose up -d db
```

Ele expõe o banco em `localhost:5432` (user/pass `postgres`, db `ceasa`), que é
o padrão de `DATABASE_URL`. Se o seu banco for outro, exporte a variável:

```bash
export DATABASE_URL=postgresql://usuario:senha@host:5432/ceasa
```

## 3. Comandos

A CLI tem três comandos:

```bash
uv run ceasa-sc-data --help
# ingest     Baixa os PDFs de cotação
# parse      Extrai e carrega no PostgreSQL (bronze -> silver -> gold)
# dashboard  Sobe o dashboard Streamlit
```

### 3.1 Baixar os dados (`ingest`)

```bash
# anos padrão (2020..2026)
uv run ceasa-sc-data ingest

# anos específicos
uv run ceasa-sc-data ingest --year 2025 --year 2024

# tudo, incluindo "Anos Anteriores" (2017..2019)
uv run ceasa-sc-data ingest --all

# re-baixar arquivos já presentes
uv run ceasa-sc-data ingest --force

# apenas PDFs a partir de uma data (ingestão incremental via watermark)
uv run ceasa-sc-data ingest --since 2026-10-01
```

O download é **incremental**: arquivos já baixados são pulados. O controle fica
em `data/raw/manifest.csv`. Os PDFs são salvos em
`data/raw/pdfs/{ano}/{mês}/{data}.pdf`.

### 3.2 Extrair e carregar (`parse`)

```bash
uv run ceasa-sc-data parse
```

Lê todos os PDFs de `data/raw/pdfs/`, extrai as tabelas e carrega no PostgreSQL
(apontado por `DATABASE_URL`) nas camadas bronze → silver → gold. O comando é
**incremental** (só processa PDFs ainda não carregados) e idempotente. Para
re-processar tudo do zero:

```bash
uv run ceasa-sc-data parse --full
```

### 3.3 Dashboard (`dashboard`)

```bash
uv run ceasa-sc-data dashboard
```

Abre o Streamlit em `http://localhost:8501`. Use os filtros de *Unidade* e
*Produto* para navegar; o gráfico mostra a série de preço comum ao longo do
tempo.

## 4. Fluxo completo de exemplo

```bash
uv sync
uv run ceasa-sc-data ingest --year 2025
uv run ceasa-sc-data parse
uv run ceasa-sc-data dashboard
```

## 5. Consultando o banco direto

O banco é o PostgreSQL apontado por `DATABASE_URL`. Com `psql`:

```bash
psql "$DATABASE_URL" -c "SELECT * FROM silver.cotacoes LIMIT 10"
```

Ou em Python:

```python
import os
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine(os.environ["DATABASE_URL"])
df = pd.read_sql("SELECT * FROM silver.cotacoes LIMIT 10", engine)
```

Tabelas disponíveis: `bronze.cotacoes_raw`, `silver.cotacoes`,
`silver.dim_unidade`, `silver.dim_produto`, `gold.preco_medio_mensal`,
`gold.preco_por_produto`.

## 6. Solução de problemas

| Sintoma | Causa provável | Solução |
|---------|----------------|---------|
| Dashboard mostra "Banco ainda não construído" | `parse` nunca rodou, ou `DATABASE_URL` inválido | Rode `uv run ceasa-sc-data parse` com o `DATABASE_URL` correto |
| `ingest` não baixa nada | Arquivos já estão no manifest e no disco | Use `--force` para re-baixar |
| Erro de rede ao baixar | Instabilidade do servidor | Rode novamente; o manifest registra o erro e re-tenta os pendentes |
| Nenhum PDF encontrado para um ano | Ano não existe no portal ou rótulo divergente | Verifique com `--all`; o rótulo deve bater com o portal (ex.: "2026") |
| Colunas trocadas no parse | Mudança de layout do PDF | Ajuste as coordenadas em `parse/parser.py` (`COLUMNS`) |

## 7. Desenvolvimento

Validar o parser manualmente:

```bash
uv run python -c "from ceasa_sc_data.parse import parser; from pathlib import Path; print(parser.parse_pdf(Path('data/raw/pdfs/2025/01-janeiro/31-01-2025.pdf'))[:2])"
```

Testar o dashboard sem subir o servidor:

```bash
uv run python -c "from streamlit.testing.v1 import AppTest; at=AppTest.from_file('src/ceasa_sc_data/dashboard/app.py'); at.run(); print(len(at.exception))"
```
