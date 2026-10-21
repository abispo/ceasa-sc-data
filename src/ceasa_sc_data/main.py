import typer

from ceasa_sc_data.ingest import downloader
from ceasa_sc_data.store import build

app = typer.Typer(
    name="ceasa-sc-data",
    help="Pipeline de dados e dashboards de cotações da CEASA/SC.",
)


@app.command()
def ingest(
    years: list[str] = typer.Option(None, "--year", "-y", help="Ano a baixar (pode repetir)."),
    force: bool = typer.Option(False, "--force", "-f", help="Re-baixa arquivos já presentes."),
    all_years: bool = typer.Option(
        False, "--all", help="Baixa todas as pastas encontradas, incluindo 'Anos Anteriores'."
    ),
    since: str | None = typer.Option(
        None, "--since", help="Baixa apenas PDFs a partir desta data (AAAA-MM-DD)."
    ),
) -> None:
    """Baixa os PDFs de cotação do portal CEASA/SC."""
    n = downloader.download(years, force=force, all_years=all_years, since=since)
    typer.echo(f"{n} PDFs baixados.")


@app.command()
def parse() -> None:
    """Extrai os dados dos PDFs e carrega no PostgreSQL (bronze -> silver -> gold)."""
    n = build.build()
    typer.echo(f"{n} linhas processadas.")


@app.command()
def dashboard() -> None:
    """Sobe o dashboard Streamlit."""
    import os
    import sys

    import streamlit.web.cli as stcli

    from ceasa_sc_data import config

    app_path = config.PROJECT_ROOT / "src" / "ceasa_sc_data" / "dashboard" / "app.py"
    port = os.environ.get("PORT", "8501")
    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--server.headless=true",
        "--server.address=0.0.0.0",
        "--server.port",
        port,
    ]
    stcli.main()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
