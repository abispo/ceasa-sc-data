import csv
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ_SAO_PAULO = ZoneInfo("America/Sao_Paulo")

# Colunas de medição após "Data" e "Hora UTC" (índices 2..18 do CSV).
MEASURE_COLUMNS = [
    "precip_mm",
    "pressao_mb",
    "pressao_max_mb",
    "pressao_min_mb",
    "radiacao_kjm2",
    "temp_c",
    "temp_orvalho_c",
    "temp_max_c",
    "temp_min_c",
    "temp_orvalho_max_c",
    "temp_orvalho_min_c",
    "umidade_max_pct",
    "umidade_min_pct",
    "umidade_pct",
    "vento_direcao_graus",
    "vento_rajada_ms",
    "vento_velocidade_ms",
]

# Mapeamento dos metadados (linhas "CHAVE:;VALOR" no topo do CSV) para os
# campos da dimensão de estação.
META_FIELDS = {
    "REGIAO": "regiao",
    "UF": "uf",
    "ESTACAO": "nome",
    "CODIGO (WMO)": "estacao",
    "LATITUDE": "latitude",
    "LONGITUDE": "longitude",
    "ALTITUDE": "altitude",
    "DATA DE FUNDACAO": "data_fundacao",
}


def _parse_number(value: str | None) -> float | None:
    """Converte um valor numérico do CSV (vírgula decimal) em float."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None


def _parse_fundacao(value: str | None) -> str | None:
    """Normaliza a data de fundação (DD/MM/AA) para AAAA-MM-DD."""
    if not value:
        return None
    value = value.strip()
    for fmt in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_data_hora(data: str, hora_utc: str) -> datetime:
    """Converte 'AAAA/MM/DD' + 'HHMM UTC' para datetime local (America/Sao_Paulo)."""
    utc = datetime.strptime(f"{data} {hora_utc[:4]}", "%Y/%m/%d %H%M").replace(
        tzinfo=ZoneInfo("UTC")
    )
    return utc.astimezone(TZ_SAO_PAULO).replace(tzinfo=None)


def parse_csv(path: Path) -> tuple[dict, list[dict]]:
    """Lê um CSV de estação do INMET e retorna (metadados, linhas).

    O retorno de linhas traz um dict por hora com `data_hora` (datetime local),
    `estacao` e as colunas de medição normalizadas para float (None quando vazio).
    """
    metadata: dict[str, str] = {}
    rows: list[dict] = []
    with path.open(encoding="latin-1", newline="") as fh:
        reader = csv.reader(fh, delimiter=";")
        for line in reader:
            if not line:
                continue
            first = line[0].strip()
            # Metadados: "CHAVE:;VALOR" (2 campos, chave terminada em ':').
            if len(line) == 2 and first.endswith(":"):
                field = META_FIELDS.get(first[:-1].strip())
                if field:
                    metadata[field] = line[1].strip()
                continue
            if first.upper() == "DATA":
                continue
            if len(line) < 2:
                continue
            data = first
            hora = line[1].strip()
            if not data or not hora:
                continue
            try:
                data_hora = _parse_data_hora(data, hora)
            except ValueError:
                continue
            values = line[2:]
            row = {"data_hora": data_hora}
            for name, raw in zip(MEASURE_COLUMNS, values):
                row[name] = _parse_number(raw)
            if all(row[name] is None for name in MEASURE_COLUMNS):
                continue
            rows.append(row)

    estacao = metadata.get("estacao", "")
    return (
        {
            "estacao": estacao,
            "nome": metadata.get("nome", ""),
            "uf": metadata.get("uf", ""),
            "latitude": _parse_number(metadata.get("latitude")),
            "longitude": _parse_number(metadata.get("longitude")),
            "altitude": _parse_number(metadata.get("altitude")),
            "data_fundacao": _parse_fundacao(metadata.get("data_fundacao")),
        },
        [{**row, "estacao": estacao} for row in rows],
    )
