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
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ceasa
uv run ceasa-sc-data ingest          # baixa os PDFs (padrão 2020..2026)
uv run ceasa-sc-data parse           # extrai e carrega no PostgreSQL
uv run ceasa-sc-data dashboard       # abre o Streamlit
```

`parse` e `dashboard` precisam de um PostgreSQL acessível via `DATABASE_URL`
(no Render ele é injetado automaticamente pelo Blueprint).

## Documentação

- **[Arquitetura](docs/arquitetura.md)** — stack, decisões, modelo de dados
  (bronze/silver/gold), fluxo do pipeline e roadmap.
- **[Guia de uso](docs/guia-de-uso.md)** — passo a passo completo, exemplos de
  comandos e solução de problemas.

## Deploy no Render

O repositório traz um [Blueprint](render.yaml) + `Dockerfile` para publicar no
[Render](https://render.com). No plano **Free**:

- O dashboard Streamlit sobe **imediatamente**; o pipeline (`ingest` + `parse`)
  roda em **segundo plano** e usa ingestão incremental: baixa apenas PDFs a
  partir da última data já presente no PostgreSQL (watermark). Se o banco
  estiver vazio, faz o backfill completo (anos padrão).
- Um scheduler interno re-roda o pipeline a cada `PIPELINE_INTERVAL_HOURS`
  (padrão 24 h) enquanto a instância estiver acordada.
- Os dados persistem no **PostgreSQL** (definido no Blueprint), independente do
  disco efêmero do serviço.
- Atenção: o Postgres **Free** do Render expira em **30 dias** (exige upgrade
  para um plano pago após esse prazo).

Para publicar: no Render, **New → Blueprint** e aponte para este repositório.

## Stack

PostgreSQL + Python + Streamlit, seguindo a arquitetura Medallion (bronze →
silver → gold). Detalhes e justificativas em [docs/arquitetura.md](docs/arquitetura.md).
