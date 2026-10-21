import logging
import os
import subprocess
import sys
import threading
import time

from sqlalchemy import text

from ceasa_sc_data import config
from ceasa_sc_data.main import dashboard
from ceasa_sc_data.store import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("ceasa.deploy")


def _run(*args: str) -> None:
    cmd = [sys.executable, "-m", "ceasa_sc_data.main", *args]
    log.info("Rodando: %s", " ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        log.warning("Etapa falhou (exit %s): %s", result.returncode, " ".join(cmd))


def _latest_data():
    engine = db.connect()
    try:
        with engine.connect() as conn:
            return conn.execute(text("SELECT max(data) FROM silver.cotacoes")).scalar()
    finally:
        engine.dispose()


def run_pipeline() -> None:
    try:
        latest = _latest_data()
    except Exception as exc:
        log.warning("Falha ao ler watermark (%s); tentando backfill completo.", exc)
        latest = None

    if latest is None:
        log.info("Banco vazio: backfill completo (anos padrão).")
        _run("ingest")
    else:
        log.info("Ingestão incremental desde %s.", latest)
        _run("ingest", "--since", latest.isoformat())
    _run("parse")


def _pipeline_loop(interval_seconds: float) -> None:
    while True:
        run_pipeline()
        time.sleep(interval_seconds)


def main() -> None:
    interval_hours = float(os.environ.get("PIPELINE_INTERVAL_HOURS", "24"))
    log.info("Subindo dashboard; pipeline em background a cada %.1f h.", interval_hours)
    threading.Thread(target=_pipeline_loop, args=(interval_hours * 3600,), daemon=True).start()
    dashboard()


if __name__ == "__main__":
    main()
