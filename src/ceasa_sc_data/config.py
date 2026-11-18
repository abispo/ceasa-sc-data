import os
from pathlib import Path

BASE_URL = "https://www.ceasa.sc.gov.br"
COTACOES_PATH = "/index.php/cotacao-de-precos"

INMET_BASE_URL = "https://portal.inmet.gov.br"
INMET_HISTORICO_URL = INMET_BASE_URL + "/uploads/dadoshistoricos/{ano}.zip"
INMET_ESTACOES_URL = "https://apitempo.inmet.gov.br/estacoes/T"
INMET_UF = "SC"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw" / "pdfs"
MANIFEST_PATH = DATA_DIR / "raw" / "manifest.csv"
INMET_RAW_DIR = DATA_DIR / "raw" / "inmet"
INMET_MANIFEST_PATH = DATA_DIR / "raw" / "inmet_manifest.csv"


def _pg_url(url: str) -> str:
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


DATABASE_URL = _pg_url(
    os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ceasa")
)

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) ceasa-sc-data/0.1"

DEFAULT_YEARS = ("2026", "2025", "2024", "2023", "2022", "2021", "2020")

INMET_DEFAULT_YEARS = ("2026", "2025", "2024", "2023", "2022", "2021", "2020")

HTTP_TIMEOUT = 60
DOWNLOAD_DELAY = 0.5
