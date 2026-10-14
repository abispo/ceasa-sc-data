from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ceasa_sc_data import config


def _get(url: str) -> requests.Response:
    resp = requests.get(
        url,
        headers={"User-Agent": config.USER_AGENT},
        timeout=config.HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return resp


def list_categories(url: str) -> list[tuple[str, str]]:
    html = _get(url).text
    soup = BeautifulSoup(html, "html.parser")
    links: list[tuple[str, str]] = []
    for anchor in soup.select(
        ".docman_categories .koowa_header__item:not(.koowa_header__item--image_container) a.koowa_header__link"
    ):
        label = anchor.get_text(strip=True)
        href = urljoin(config.BASE_URL, anchor["href"])
        links.append((label, href))
    return links


def list_documents(url: str) -> list[dict]:
    html = _get(url).text
    soup = BeautifulSoup(html, "html.parser")
    documents: list[dict] = []
    for block in soup.select(".docman_document"):
        anchor = block.select_one("a.docman_track_download")
        if anchor is None:
            continue
        documents.append(
            {
                "date": anchor.get("data-title", ""),
                "id": anchor.get("data-id", ""),
                "url": urljoin(config.BASE_URL, anchor["href"]),
            }
        )
    return documents


def discover_years() -> list[tuple[str, str]]:
    return list_categories(config.BASE_URL + config.COTACOES_PATH)


def discover_months(year_url: str) -> list[tuple[str, str]]:
    return list_categories(year_url)


def discover_documents(month_url: str) -> list[dict]:
    return list_documents(month_url)
