# Progresso do projeto — CEASA/SC Data

Pipeline de engenharia de dados e dashboards de cotações de preços da CEASA/SC.

## O que já foi feito

### 1. Ingestão (`ingest/`)
- Crawler navega a árvore ano → mês → PDF do portal (recursivo, lida com `Anos Anteriores`).
- Downloader baixa os PDFs de forma incremental (manifest CSV, pula o que já existe).
- CLI: `ceasa-sc-data ingest [--year X | --all] [--force]`.

### 2. Extração (`parse/`)
- Parser lê os PDFs (JasperReports, texto) mapeando colunas por coordenada-x.
- Extrai: produto, variedade, classificação, tipo, origem, embalagem, peso,
  preço mínimo/comum/máximo e preço por kg.
- Normaliza o formato numérico (vírgula vs ponto).

### 3. Armazenamento (`store/`)
- DuckDB com camadas:
  - `bronze` — linhas brutas extraídas;
  - `silver` — dados limpos, tipados e deduplicados;
  - `gold` — views agregadas para o dashboard.
- CLI: `ceasa-sc-data parse` (bronze → silver → gold, idempotente).

### 4. Dashboard (`dashboard/`)
- Streamlit com filtro por Unidade/Produto, KPIs (última cotação, mín/máx do
  período) e gráfico de série temporal de preço.
- CLI: `ceasa-sc-data dashboard`.

## Validação
- Parser extraiu 265 linhas corretas de um PDF real (31/01/2025, São José).
- Pipeline roda de ponta a ponta (ingestão → extração → carga).
- Dashboard abre sem erros (servidor + teste programático `AppTest`).

## Pendências conhecidas
- Separação semântica produto × variedade (nomes curtos como `Uva Benitaka`
  ficam com a variedade embutida em `produto`); resolver com lista-mestre de
  produtos na camada silver.
- `ingest` completo em volume real (todos os anos) ainda não foi rodado.
