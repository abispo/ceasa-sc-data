from pathlib import Path

from rich.progress import track
from sqlalchemy import text

from ceasa_sc_data import config
from ceasa_sc_data.inmet import parser
from ceasa_sc_data.store import db


def _iter_csvs() -> list[Path]:
    if not config.INMET_RAW_DIR.exists():
        return []
    return sorted(config.INMET_RAW_DIR.rglob("*.CSV"))


def _loaded_arquivos(conn) -> set[str]:
    rows = conn.execute(text("SELECT DISTINCT arquivo FROM bronze.clima_raw")).fetchall()
    return {r[0] for r in rows}


def build(full: bool = False) -> int:
    engine = db.connect()
    total = 0
    try:
        with engine.begin() as conn:
            if full:
                conn.execute(text("DELETE FROM bronze.clima_raw"))
            loaded = _loaded_arquivos(conn)
            for path in track(_iter_csvs(), description="Parse + carga clima"):
                if str(path) in loaded:
                    continue
                station, rows = parser.parse_csv(path)
                db.upsert_estacao(conn, station)
                db.insert_clima_bronze(conn, [{**r, "arquivo": str(path)} for r in rows])
                total += len(rows)
                loaded.add(str(path))

            db.build_clima_silver(conn)
            db.build_clima_gold(conn)
    finally:
        engine.dispose()
    return total
