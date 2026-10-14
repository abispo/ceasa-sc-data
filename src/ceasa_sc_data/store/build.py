from pathlib import Path

from rich.progress import track

from ceasa_sc_data import config
from ceasa_sc_data.parse import parser
from ceasa_sc_data.store import db


def _iter_pdfs() -> list[Path]:
    if not config.RAW_DIR.exists():
        return []
    return sorted(config.RAW_DIR.rglob("*.pdf"))


def build() -> int:
    conn = db.connect()
    conn.execute("DELETE FROM bronze.cotacoes_raw")
    pdfs = _iter_pdfs()
    total = 0

    for path in track(pdfs, description="Parse + carga"):
        metadata = parser.extract_metadata(path)
        parsed = parser.parse_pdf(path)
        rows = [{**metadata, **r, "arquivo": str(path)} for r in parsed]
        db.insert_bronze(conn, rows)
        total += len(rows)

    db.build_silver(conn)
    db.build_gold(conn)
    conn.close()
    return total
