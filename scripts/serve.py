import logging
import os
import subprocess
import sys
import threading
import time

from ceasa_sc_data.main import dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("ceasa.deploy")


def _run_pipeline_stage(*args: str) -> None:
    cmd = [sys.executable, "-m", "ceasa_sc_data.main", *args]
    log.info("Rodando: %s", " ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        log.warning("Etapa falhou (exit %s): %s", result.returncode, " ".join(cmd))


def run_pipeline() -> None:
    _run_pipeline_stage("ingest")
    _run_pipeline_stage("parse")


def _scheduler(interval_seconds: float) -> None:
    while True:
        time.sleep(interval_seconds)
        run_pipeline()


def main() -> None:
    interval_hours = float(os.environ.get("PIPELINE_INTERVAL_HOURS", "24"))
    log.info("Build inicial do pipeline (ingest + parse)...")
    run_pipeline()
    log.info("Agendando refresh a cada %.1f h", interval_hours)
    threading.Thread(target=_scheduler, args=(interval_hours * 3600,), daemon=True).start()
    log.info("Subindo dashboard...")
    dashboard()


if __name__ == "__main__":
    main()
