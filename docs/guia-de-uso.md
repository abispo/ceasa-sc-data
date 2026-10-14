# Guia de Uso

Passo a passo para rodar o pipeline, do zero até o dashboard.

## 1. Pré-requisitos

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) (instalador e gerenciador de ambiente)

## 2. Instalação

```bash
uv sync
```

Isso cria o ambiente virtual e instala as dependências a partir do `uv.lock`.

## 3. Comandos

A CLI tem três comandos:

```bash
uv run ceasa-sc-data --help
# ingest     Baixa os PDFs de cotação
# parse      Extrai e carrega no DuckDB (bronze -> silver -> gold)
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
```

O download é **incremental**: arquivos já baixados são pulados. O controle fica
em `data/raw/manifest.csv`. Os PDFs são salvos em
`data/raw/pdfs/{ano}/{mês}/{data}.pdf`.

### 3.2 Extrair e carregar (`parse`)

```bash
uv run ceasa-sc-data parse
```

Lê todos os PDFs de `data/raw/pdfs/`, extrai as tabelas e carrega no DuckDB
(`data/ceasa.db`) nas camadas bronze → silver → gold. O comando é idempotente.

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

O banco fica em `data/ceasa.db` e pode ser aberto com DuckDB/CLI ou Python:

```python
import duckdb
conn = duckdb.connect("data/ceasa.db", read_only=True)
df = conn.execute("SELECT * FROM silver.cotacoes LIMIT 10").fetchdf()
```

Tabelas disponíveis: `bronze.cotacoes_raw`, `silver.cotacoes`,
`silver.dim_unidade`, `silver.dim_produto`, `gold.preco_medio_mensal`,
`gold.preco_por_produto`.

## 6. Solução de problemas

| Sintoma | Causa provável | Solução |
|---------|----------------|---------|
| Dashboard mostra "Banco ainda não construído" | `parse` nunca rodou, ou `data/ceasa.db` não existe | Rode `uv run ceasa-sc-data parse` |
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
