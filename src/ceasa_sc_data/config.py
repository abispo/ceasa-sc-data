from pathlib import Path

BASE_URL = "https://www.ceasa.sc.gov.br"
COTACOES_PATH = "/index.php/cotacao-de-precos"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw" / "pdfs"
MANIFEST_PATH = DATA_DIR / "raw" / "manifest.csv"
DB_PATH = DATA_DIR / "ceasa.db"

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) ceasa-sc-data/0.1"

DEFAULT_YEARS = ("2026", "2025", "2024", "2023", "2022", "2021", "2020")

HTTP_TIMEOUT = 60
DOWNLOAD_DELAY = 0.5
