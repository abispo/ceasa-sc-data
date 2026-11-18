from datetime import datetime
from pathlib import Path

from ceasa_sc_data.inmet import parser

HEADER = (
    "Data;Hora UTC;PRECIPITAÇÃO TOTAL, HORÁRIO (mm);"
    "PRESSAO ATMOSFERICA AO NIVEL DA ESTACAO, HORARIA (mB);"
    "PRESSAO ATMOSFERICA MAX.NA HORA ANT. (AUT) (mB);"
    "PRESSAO ATMOSFERICA MIN. NA HORA ANT. (AUT) (mB);"
    "RADIACAO GLOBAL (Kj/m²);TEMPERATURA DO AR - BULBO SECO, HORARIA (°C);"
    "TEMPERATURA DO PONTO DE ORVALHO (°C);"
    "TEMPERATURA MÁXIMA NA HORA ANT. (AUT) (°C);"
    "TEMPERATURA MÍNIMA NA HORA ANT. (AUT) (°C);"
    "TEMPERATURA ORVALHO MAX. NA HORA ANT. (AUT) (°C);"
    "TEMPERATURA ORVALHO MIN. NA HORA ANT. (AUT) (°C);"
    "UMIDADE REL. MAX. NA HORA ANT. (AUT) (%);"
    "UMIDADE REL. MIN. NA HORA ANT. (AUT) (%);"
    "UMIDADE RELATIVA DO AR, HORARIA (%);"
    "VENTO, DIREÇÃO HORARIA (gr);VENTO, RAJADA MAXIMA (m/s);"
    "VENTO, VELOCIDADE HORARIA (m/s);"
)

META = (
    "REGIAO:;S\n"
    "UF:;SC\n"
    "ESTACAO:;FLORIANOPOLIS\n"
    "CODIGO (WMO):;A806\n"
    "LATITUDE:;-27,6025\n"
    "LONGITUDE:;-48,61999999\n"
    "ALTITUDE:;4,87\n"
    "DATA DE FUNDACAO:;22/01/03\n"
)

SAMPLE = "\n".join(
    [
        "2026/01/01;0000 UTC;;;;;;;;;;;;;;;;;;",
        "2026/02/11;1500 UTC;0;1009,7;1010,4;1009,7;840,3;33,2;20,1;33,2;31,9;20,7;19,6;50;45;46;30;;2;",
    ]
)


def _write_sample(path: Path) -> Path:
    path.write_text(META + HEADER + "\n" + SAMPLE + "\n", encoding="latin-1")
    return path


def test_parse_number():
    assert parser._parse_number("33,2") == 33.2
    assert parser._parse_number("0") == 0.0
    assert parser._parse_number("") is None
    assert parser._parse_number(None) is None


def test_parse_data_hora_local():
    assert parser._parse_data_hora("2026/02/11", "1500 UTC") == datetime(2026, 2, 11, 12, 0)


def test_parse_csv_metadata(tmp_path):
    path = _write_sample(tmp_path / "estacao.CSV")
    station, _ = parser.parse_csv(path)
    assert station["estacao"] == "A806"
    assert station["nome"] == "FLORIANOPOLIS"
    assert station["uf"] == "SC"
    assert station["latitude"] == -27.6025
    assert station["altitude"] == 4.87
    assert station["data_fundacao"] == "2003-01-22"


def test_parse_csv_rows(tmp_path):
    path = _write_sample(tmp_path / "estacao.CSV")
    _, rows = parser.parse_csv(path)
    assert len(rows) == 1
    row = rows[0]
    assert row["estacao"] == "A806"
    assert row["data_hora"] == datetime(2026, 2, 11, 12, 0)
    assert row["precip_mm"] == 0.0
    assert row["pressao_mb"] == 1009.7
    assert row["temp_c"] == 33.2
    assert row["umidade_pct"] == 46.0
    assert row["vento_rajada_ms"] is None
    assert row["vento_velocidade_ms"] == 2.0
