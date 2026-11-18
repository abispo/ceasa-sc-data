import csv
import shutil
import time
import zipfile
from pathlib import Path

import requests
from rich.progress import track

from ceasa_sc_data import config


def _load_manifest() -> dict[str, dict]:
    config.INMET_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not config.INMET_MANIFEST_PATH.exists():
        return {}
    with config.INMET_MANIFEST_PATH.open(newline="") as fh:
        return {row["year"]: row for row in csv.DictReader(fh)}


def _save_manifest(manifest: dict[str, dict]) -> None:
    fieldnames = ["year", "url", "files", "status"]
    with config.INMET_MANIFEST_PATH.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in manifest.values():
            writer.writerow(row)


def _download_year(year: str, manifest: dict[str, dict], force: bool) -> int:
    """Baixa o ZIP anual do INMET e extrai apenas os CSVs de estações de SC."""
    url = config.INMET_HISTORICO_URL.format(ano=year)
    dest_dir = config.INMET_RAW_DIR / year
    if year in manifest and manifest[year].get("status") == "ok" and not force:
        if dest_dir.exists():
            return 0

    tmp_zip = config.INMET_RAW_DIR / f"{year}.zip"
    extracted = 0
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": config.USER_AGENT},
            timeout=config.HTTP_TIMEOUT,
            stream=True,
        )
        resp.raise_for_status()
        tmp_zip.parent.mkdir(parents=True, exist_ok=True)
        with tmp_zip.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                fh.write(chunk)

        dest_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(tmp_zip) as zf:
            for name in zf.namelist():
                base = Path(name).name
                if not base.endswith(".CSV") or f"_{config.INMET_UF}_A" not in base:
                    continue
                target = dest_dir / base
                with zf.open(name) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                extracted += 1

        manifest[year] = {"year": year, "url": url, "files": str(extracted), "status": "ok"}
        time.sleep(config.DOWNLOAD_DELAY)
        return extracted
    except requests.RequestException as exc:
        manifest[year] = {"year": year, "url": url, "files": "0", "status": f"error: {exc}"}
        return 0
    finally:
        tmp_zip.unlink(missing_ok=True)


def download(years: list[str] | None = None, force: bool = False) -> int:
    """Baixa os históricos anuais do INMET filtrando por UF (padrão: SC)."""
    config.INMET_RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest()
    selected = set(years) if years else set(config.INMET_DEFAULT_YEARS)
    total = 0
    for year in track(sorted(selected, reverse=True), description="Baixando INMET"):
        total += _download_year(year, manifest, force)
    _save_manifest(manifest)
    return total
