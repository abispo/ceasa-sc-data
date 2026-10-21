# Arquitetura

Este documento descreve a arquitetura do projeto, as decisões de tecnologia e o
modelo de dados. Para a visão geral e instalação rápida, veja o [README](../README.md).

## 1. Visão geral

O projeto consome os PDFs de cotação de preços do portal da CEASA/SC e entrega
um banco analítico consultável por um dashboard Streamlit.

```
portal CEASA/SC (Joomla + DOCman)
        │
        │  ingest — requests + BeautifulSoup (crawler recursivo + download incremental)
        ▼
data/raw/pdfs/{ano}/{mês}/{data}.pdf        ← landing zone
        │
        │  parse — pdfplumber (mapeamento de colunas por coordenada x)
        ▼
PostgreSQL (Render)
        │
        ├─ bronze.cotacoes_raw              ← linhas brutas por arquivo
        ├─ silver.cotacoes / dim_*          ← limpo, tipado, deduplicado
        └─ gold.*                           ← views agregadas
        │
        ▼
Streamlit (dashboard)
```

## 2. Decisões de tecnologia

| Componente   | Ferramenta     | Justificativa |
|--------------|----------------|---------------|
| Linguagem    | Python 3.12    | Ecossistema de dados, bibliotecas de scraping/parsing maduras |
| Gerenciador  | `uv`           | Rápido, lockfile determinístico (`uv.lock`) |
| Scraping     | `requests` + `beautifulsoup4` | Simples e suficiente; o portal é HTML estático (sem JS) |
| Parsing PDF  | `pdfplumber`   | PDFs são textuais (JasperReports/iText), com colunas em posições fixas |
| Banco        | `postgresql`   | Servidor relacional gerenciado no Render; persiste os dados entre deploys |
| CLI          | `typer` + `rich` | Interface amigável, progresso visual |
| Dashboard    | `streamlit` + `plotly` | Prototipagem rápida, Python puro |

### Por que não usar outra stack?

- **DuckDB (local)**: ótimo para exploração single-file, mas sem modo servidor e
  single-writer — não atende persistência compartilhada num deploy web. Por isso
  o projeto usa PostgreSQL.
- **Spark/Databricks**: superdimensionado — os dados cabem em memória.
- **OCR** (para os PDFs): desnecessário — os PDFs têm texto extraível.

## 3. Estrutura de diretórios

```
ceasa-sc-data/
├── pyproject.toml            # dependências + entry point da CLI
├── uv.lock                   # lockfile
├── README.md                 # visão geral + quickstart
├── PROGRESS.md               # registro do que já foi feito
├── docs/
│   ├── arquitetura.md        # este documento
│   └── guia-de-uso.md        # manual de uso
├── data/                     # gerado em runtime (gitignored)
│   ├── raw/pdfs/             # landing zone
│   └── raw/manifest.csv      # controle de download incremental
└── src/ceasa_sc_data/
    ├── __init__.py
    ├── config.py             # constantes (URLs, caminhos, anos padrão)
    ├── main.py               # CLI (typer)
    ├── ingest/
    │   ├── crawler.py        # descoberta recursiva (categorias/documentos)
    │   └── downloader.py     # download + manifest
    ├── parse/
    │   └── parser.py         # extração de tabelas por coordenada x
    ├── store/
    │   ├── db.py             # schema (bronze/silver/gold)
    │   └── build.py          # orquestração parse → carga
    └── dashboard/
        └── app.py            # app Streamlit
```

## 4. Fluxo do pipeline

### 4.1 Ingestão

O portal é estruturado como `ano → mês → PDF diário`. O crawler
(`ingest/crawler.py`) expõe duas primitivas:

- `list_categories(url)` → pastas (ano, mês ou anos aninhados);
- `list_documents(url)` → PDFs (`{id}-{dd-mm-yyyy}/file`).

O downloader (`ingest/downloader.py`) percorre a árvore recursivamente, o que
permite tratar o caso especial de `Anos Anteriores`, que contém anos aninhados
(2017, 2018, 2019) antes dos meses.

O **manifest** (`data/raw/manifest.csv`) registra cada arquivo por `id`, data,
caminho e status. Isso torna o download **incremental**: arquivos já baixados
são pulados, a menos que `--force` seja usado. Há `rate-limit` (delay entre
requisições) para não sobrecarregar o servidor.

### 4.2 Extração

Cada PDF é um relatório JasperReports com colunas em posições **x fixas**. O
parser (`parse/parser.py`) extrai as palavras com suas coordenadas
(`pdfplumber`) e as agrupa em linhas por `top`, atribuindo cada palavra à
coluna pela posição `x`.

Colunas mapeadas:

| Campo            | Descrição |
|------------------|-----------|
| `produto`        | Nome do produto |
| `variedade`      | Variedade (ex.: "Avocado", "Longa Vida") |
| `classificacao`  | Classificação/tamanho (ex.: "Grande", "Extra A", "Tipo 4") |
| `tipo`           | Convencional ou Orgânico |
| `origem`         | Nacional ou Importado |
| `embalagem`      | Caixa, Saco, Maço, Kilo, Unidade... |
| `peso_kg`        | Peso da embalagem |
| `preco_min`      | Preço mínimo (R$/embalagem) |
| `preco_comum`    | Preço comum (R$/embalagem) |
| `preco_max`      | Preço máximo (R$/embalagem) |
| `preco_comum_kg` | Preço comum por kg |

**Normalização numérica**: preços usam vírgula decimal (`150,00`) enquanto a
coluna `Comum/Kg` usa ponto (`15.00`). O parser converte ambos para `float`.

### 4.3 Armazenamento (Medallion)

| Camada  | Tabela/View | Conteúdo |
|---------|-------------|----------|
| bronze  | `bronze.cotacoes_raw` | Linhas brutas por arquivo (com `arquivo`, `data` e `unidade`) |
| silver  | `silver.cotacoes` | Limpo, tipado (`data` → `DATE`, preços → `DOUBLE`), com chave natural deduplicando |
| silver  | `silver.dim_unidade` | Dimensão de unidades (São José, Blumenau, Tubarão) |
| silver  | `silver.dim_produto` | Dimensão de produtos |
| gold    | `gold.preco_medio_mensal` | Preço médio mensal por produto/unidade |
| gold    | `gold.preco_por_produto` | Série completa por produto |

**Idempotência**: `parse` apaga e reconstrói `bronze` do zero; `silver` usa
`INSERT OR REPLACE` com chave natural
`(data, unidade, produto, variedade, classificacao, tipo, origem, embalagem)`,
portanto re-rodar não duplica registros.

### 4.4 Dashboard

O app Streamlit (`dashboard/app.py`) consulta o PostgreSQL (via SQLAlchemy),
permite filtrar por unidade e produto e exibe KPIs e a série temporal de preço.

## 5. Limitações e roadmap

- **Produto × variedade**: a separação é geométrica. Para produtos com nome
  curto (`Uva Benitaka`, `Milho Verde`), a variedade fica embutida em `produto`.
  A correção semântica deve usar a lista-mestre de produtos do portal
  (`/cotacao-de-precos/produtos-lista`) na camada silver.
- **Unidades**: o arquivo de exemplo traz apenas São José; é preciso validar o
  layout dos PDFs de Blumenau e Tubarão.
- **Orquestração**: hoje o pipeline é disparado via CLI. Se for necessário
  agendar, o próximo passo natural é Dagster/Prefect ou um cron simples.
- **Idempotência do bronze**: `bronze` é reconstruído a cada `parse`; para
  processamento incremental em larga escala, valeria rastrear arquivos já
  carregados.
