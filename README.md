# CEASA/SC — Cotações de Preços

Pipeline de engenharia de dados + dashboards para os preços de hortifrúti da
[CEASA/SC](https://www.ceasa.sc.gov.br/index.php/cotacao-de-precos).

## Fonte de dados

O portal publica, por dia útil, um PDF com a cotação de cada unidade. A árvore
de navegação é: **ano → mês → PDF diário** (`{id}-{dd-mm-yyyy}/file`). O PDF é
gerado por JasperReports (texto, não imagem), com colunas fixas.

## Quickstart

```bash
uv sync
uv run ceasa-sc-data ingest          # baixa os PDFs (padrão 2020..2026)
uv run ceasa-sc-data parse           # extrai e carrega no DuckDB
uv run ceasa-sc-data dashboard       # abre o Streamlit
```

## Documentação

- **[Arquitetura](docs/arquitetura.md)** — stack, decisões, modelo de dados
  (bronze/silver/gold), fluxo do pipeline e roadmap.
- **[Guia de uso](docs/guia-de-uso.md)** — passo a passo completo, exemplos de
  comandos e solução de problemas.

## Stack

DuckDB + Python + Streamlit, seguindo a arquitetura Medallion (bronze → silver →
gold). Detalhes e justificativas em [docs/arquitetura.md](docs/arquitetura.md).
