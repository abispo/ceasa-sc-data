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


def _loaded_arquivos(conn) -> set[str]:
    rows = conn.execute(text("SELECT DISTINCT arquivo FROM bronze.cotacoes_raw")).fetchall()
    return {r[0] for r in rows}


def build(full: bool = False) -> int:
    engine = db.connect()
    total = 0
    try:
        with engine.begin() as conn:
            if full:
                conn.execute(text("DELETE FROM bronze.cotacoes_raw"))
            loaded = _loaded_arquivos(conn)
            for path in track(_iter_pdfs(), description="Parse + carga"):
                if str(path) in loaded:
                    continue
                metadata = parser.extract_metadata(path)
                parsed = parser.parse_pdf(path)
                rows = [{**metadata, **r, "arquivo": str(path)} for r in parsed]
                db.insert_bronze(conn, rows)
                total += len(rows)
                loaded.add(str(path))

            db.build_silver(conn)
            db.build_gold(conn)
    finally:
        engine.dispose()
    return total
