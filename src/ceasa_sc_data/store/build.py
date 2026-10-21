from pathlib import Path

from rich.progress import track
from sqlalchemy import text

from ceasa_sc_data import config
from ceasa_sc_data.parse import parser
from ceasa_sc_data.store import db


def _iter_pdfs() -> list[Path]:
    if not config.RAW_DIR.exists():
        return []
    return sorted(config.RAW_DIR.rglob("*.pdf"))


def build() -> int:
    engine = db.connect()
    total = 0
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM bronze.cotacoes_raw"))
            pdfs = _iter_pdfs()
            for path in track(pdfs, description="Parse + carga"):
                metadata = parser.extract_metadata(path)
                parsed = parser.parse_pdf(path)
                rows = [{**metadata, **r, "arquivo": str(path)} for r in parsed]
                db.insert_bronze(conn, rows)
                total += len(rows)

            db.build_silver(conn)
            db.build_gold(conn)
    finally:
        engine.dispose()
    return total
