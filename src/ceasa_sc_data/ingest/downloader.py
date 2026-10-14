import csv
import time
from pathlib import Path

import requests
from rich.progress import track

from ceasa_sc_data import config
from ceasa_sc_data.ingest import crawler


def _load_manifest() -> dict[str, dict]:
    config.MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not config.MANIFEST_PATH.exists():
        return {}
    with config.MANIFEST_PATH.open(newline="") as fh:
        reader = csv.DictReader(fh)
        return {row["id"]: row for row in reader}


def _save_manifest(manifest: dict[str, dict]) -> None:
    fieldnames = ["date", "id", "year", "month", "url", "path", "status"]
    with config.MANIFEST_PATH.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in manifest.values():
            writer.writerow(row)


def _slug(value: str) -> str:
    return value.strip().lower().replace(" ", "-").replace("/", "-")


def _download_doc(doc: dict, folder: list[str], manifest: dict[str, dict], force: bool) -> bool:
    doc_id = doc["id"]
    dest = config.RAW_DIR.joinpath(*[_slug(p) for p in folder], f"{doc['date']}.pdf")

    if doc_id in manifest and not force and dest.exists():
        return False

    try:
        resp = requests.get(
            doc["url"],
            headers={"User-Agent": config.USER_AGENT},
            timeout=config.HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)
        manifest[doc_id] = {
            "date": doc["date"],
            "id": doc_id,
            "year": folder[-2] if len(folder) >= 2 else "",
            "month": folder[-1] if folder else "",
            "url": doc["url"],
            "path": str(dest),
            "status": "ok",
        }
        time.sleep(config.DOWNLOAD_DELAY)
        return True
    except requests.RequestException as exc:
        manifest[doc_id] = {
            "date": doc["date"],
            "id": doc_id,
            "year": folder[-2] if len(folder) >= 2 else "",
            "month": folder[-1] if folder else "",
            "url": doc["url"],
            "path": "",
            "status": f"error: {exc}",
        }
        return False


def _walk(url: str, folder: list[str], manifest: dict[str, dict], force: bool) -> int:
    downloaded = 0
    for doc in track(
        crawler.list_documents(url),
        description="  ".join(folder) or "raiz",
    ):
        downloaded += _download_doc(doc, folder, manifest, force)
    for label, cat_url in crawler.list_categories(url):
        downloaded += _walk(cat_url, folder + [label], manifest, force)
    return downloaded


def download(
    years: list[str] | None = None,
    force: bool = False,
    all_years: bool = False,
) -> int:
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest()
    root = config.BASE_URL + config.COTACOES_PATH

    if all_years:
        downloaded = _walk(root, [], manifest, force)
    else:
        selected = years or list(config.DEFAULT_YEARS)
        downloaded = 0
        for year_label, year_url in crawler.discover_years():
            if year_label not in selected:
                continue
            downloaded += _walk(year_url, [year_label], manifest, force)

    _save_manifest(manifest)
    return downloaded
