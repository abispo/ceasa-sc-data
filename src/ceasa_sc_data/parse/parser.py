import re
from pathlib import Path

import pdfplumber

COLUMNS = [
    ("produto", 20.0, 53.8),
    ("variedade", 53.8, 162.0),
    ("classificacao", 162.0, 220.0),
    ("tipo", 220.0, 273.0),
    ("origem", 273.0, 326.0),
    ("embalagem", 326.0, 380.0),
    ("peso_kg", 380.0, 418.0),
    ("preco_min", 418.0, 458.0),
    ("preco_comum", 458.0, 500.0),
    ("preco_max", 500.0, 539.0),
    ("preco_comum_kg", 539.0, 590.0),
]

_NUMERIC_COLUMNS = {"peso_kg", "preco_min", "preco_comum", "preco_max", "preco_comum_kg"}


def _parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if "." in value and "," in value:
        value = value.replace(".", "").replace(",", ".")
    elif "," in value:
        value = value.replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return None


def _group_rows(words: list[dict]) -> list[list[dict]]:
    rows: list[list[dict]] = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if rows and abs(word["top"] - rows[-1][0]["top"]) < 2.5:
            rows[-1].append(word)
        else:
            rows.append([word])
    return rows


def _assign_columns(row_words: list[dict]) -> dict[str, str]:
    cells = {name: "" for name, _, _ in COLUMNS}
    for word in row_words:
        cx = word["x0"]
        for name, lo, hi in COLUMNS:
            if lo <= cx < hi:
                cells[name] = f"{cells[name]} {word['text']}".strip()
                break
    return cells


def _is_data_row(cells: dict[str, str]) -> bool:
    if not cells["produto"]:
        return False
    if _parse_number(cells["preco_comum"]) is None and _parse_number(cells["preco_min"]) is None:
        return False
    return True


def parse_pdf(path: Path) -> list[dict]:
    rows: list[dict] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            for row_words in _group_rows(words):
                cells = _assign_columns(row_words)
                if not _is_data_row(cells):
                    continue
                rows.append(
                    {
                        "produto": cells["produto"],
                        "variedade": cells["variedade"],
                        "classificacao": cells["classificacao"],
                        "tipo": cells["tipo"],
                        "origem": cells["origem"],
                        "embalagem": cells["embalagem"],
                        "peso_kg": _parse_number(cells["peso_kg"]),
                        "preco_min": _parse_number(cells["preco_min"]),
                        "preco_comum": _parse_number(cells["preco_comum"]),
                        "preco_max": _parse_number(cells["preco_max"]),
                        "preco_comum_kg": _parse_number(cells["preco_comum_kg"]),
                    }
                )
    return rows


def extract_metadata(path: Path) -> dict:
    with pdfplumber.open(path) as pdf:
        text = pdf.pages[0].extract_text() or ""
    data_match = re.search(r"Cotações do dia\s*:\s*(\d{2}/\d{2}/\d{4})", text)
    unit_match = re.search(r"Unidade\s*:\s*([A-Za-zÀ-ú ]+)", text)
    return {
        "data": data_match.group(1) if data_match else None,
        "unidade": unit_match.group(1).strip() if unit_match else None,
    }
