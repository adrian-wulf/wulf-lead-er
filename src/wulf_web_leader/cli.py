import asyncio
import json
from pathlib import Path
from typing import Annotated, Optional
import typer
from rich.console import Console
from rich.table import Table

from wulf_web_leader.models import CanonicalLead, CountryCode
from wulf_web_leader.verticals import load_all_verticals, find_vertical, resolve_or_create_vertical
from wulf_web_leader.pipeline import run_scan_pipeline
from wulf_web_leader.export.writer import export_leads_to_csv, export_leads_to_json, ODBL_ATTRIBUTION
from wulf_web_leader.export.demo import generate_demo_html
from wulf_web_leader.export.report import generate_html_report
from wulf_web_leader.audit.cache import AuditCache
from wulf_web_leader.audit.classifier import classify_website_kind
from wulf_web_leader.audit.fetch import audit_website
from wulf_web_leader.score.engine import calculate_lead_score
from wulf_web_leader.score.hooks import generate_pitch_hooks

app = typer.Typer(
    name="lead.er",
    help="lead.er (wulf-web-leader): Lokalny skaner leadów dla web designerów (Polska i Niemcy). Bez spamu, bez konta, local-first.",
    add_completion=False,
)
console = Console()


def determine_output_paths(out_arg: Optional[Path], default_stem: str = "leads") -> tuple[Path, Path]:
    """Wyznacz ścieżki plików wyjściowych CSV i JSON na podstawie parametru --out."""
    if out_arg is None:
        return Path(f"{default_stem}.csv"), Path(f"{default_stem}.json")

    if out_arg.is_dir() or (not out_arg.suffix and not out_arg.exists()):
        out_arg.mkdir(parents=True, exist_ok=True)
        return out_arg / f"{default_stem}.csv", out_arg / f"{default_stem}.json"

    if out_arg.suffix.lower() == ".csv":
        return out_arg, out_arg.with_suffix(".json")
    if out_arg.suffix.lower() == ".json":
        return out_arg.with_suffix(".csv"), out_arg

    return out_arg.with_suffix(".csv"), out_arg.with_suffix(".json")


def load_leads_from_file(file_path: Path) -> list[CanonicalLead]:
    """Wczytaj listę leadów z pliku JSON i dokonaj walidacji modeli Pydantic."""
    if not file_path.is_file():
        console.print(f"[bold red]Błąd:[/bold red] Plik wejściowy '{file_path}' nie istnieje.")
        raise typer.Exit(code=1)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        console.print(f"[bold red]Błąd odczytu pliku JSON:[/bold red] {e}")
        raise typer.Exit(code=1)

    raw_leads = data.get("leads", []) if isinstance(data, dict) else data
    return [CanonicalLead.model_validate(item) for item in raw_leads]


@app.command(name="list-verticals")
def list_verticals():
    """Wyświetl listę dostępnych branż oraz ich polskich i niemieckich aliasów."""
    verticals = load_all_verticals()
    table = Table(title="Dostępne branże (Verticals)", show_lines=True)
    table.add_column("ID branży", style="cyan", no_wrap=True)
    table.add_column("Nazwa angielska", style="bold")
    table.add_column("Słowa kluczowe i aliasy (PL)", style="green")
    table.add_column("Słowa kluczowe i aliasy (DE)", style="yellow")

    for v in verticals.values():
        pl_aliases = ", ".join([v.pl.query] + v.aliases.pl)
        de_aliases = ", ".join([v.de.query] + v.aliases.de)
        table.add_row(v.id, v.name, pl_aliases, de_aliases)

    console.print(table)


@app.command()
def scan(
    country: Annotated[str, typer.Option("--country", "-c", help="Kod kraju: pl lub de")] = "pl",
    city: Annotated[str, typer.Option("--city", "--miasto", help="Docelowe miasto (np. Rzeszów, Dresden)")] = ...,
    vertical: Annotated[str, typer.Option("--vertical", "-v", help="Branża (np. plumbers, hair, hydraulik, fryzjer)")] = ...,
    radius: Annotated[float, typer.Option("--radius", "-r", help="Promień wyszukiwania w km")] = 15.0,
    lang: Annotated[str, typer.Option("--lang", "-l", help="Język hooków sprzedażowych (pl, de, en)")] = "pl",
    out: Annotated[Optional[Path], typer.Option("--out", "-o", help="Ścieżka docelowa pliku lub katalogu")] = None,
    format: Annotated[str, typer.Option("--format", "-f", help="Format eksportu (csv lub json)")] = "csv",
    min_score: Annotated[int, typer.Option("--min-score", help="Minimalny wynik leada (0-100)")] = 0,
    has_phone: Annotated[bool, typer.Option("--has-phone", help="Uwzględnij tylko firmy z publicznym numerem telefonu")] = False,
    quick: Annotated[bool, typer.Option("--quick", "--no-audit", help="Pomiń audyt sieciowy stron (błyskawiczny skan)")] = False,
    no_cache: Annotated[bool, typer.Option("--no-cache", "--refresh-audit", help="Pomiń cache dyskowy i wymuś świeży audyt stron www")] = False,
    delimiter: Annotated[str, typer.Option("--delimiter", help="Separator CSV (comma lub semicolon)")] = "comma",
):
    """Przeskanuj wybrane miasto i promień w poszukiwaniu firm potrzebujących strony www."""
    country_norm = country.strip().upper()
    if country_norm not in ("PL", "DE"):
        console.print(f"[bold red]Błąd:[/bold red] Kod kraju musi wynosić 'pl' lub 'de' (podano '{country}')")
        raise typer.Exit(code=1)

    target_lang = (lang or "pl").lower().strip()
    if target_lang not in ("pl", "de", "en"):
        target_lang = "pl"

    # Znajdź lub stwórz definicję wertykału (obsługa predefiniowanych oraz dowolnych wpisanych z ręki)
    v_def = resolve_or_create_vertical(vertical, country=country_norm)
    if not v_def:
        console.print(f"[bold red]Błąd:[/bold red] Nieznana branża '{vertical}'.")
        console.print("Uruchom [cyan]lead.er list-verticals[/cyan], aby zobaczyć obsługiwane branże.")
        raise typer.Exit(code=1)

    delim_char = ";" if delimiter.lower() in ("semicolon", ";") else ","

    csv_path, json_path = determine_output_paths(out, default_stem="leads")

    console.print(
        f"[bold blue]lead.er[/bold blue] - Skanowanie [bold cyan]{city}[/bold cyan] ({country_norm}) "
        f"dla branży [bold green]{v_def.name}[/bold green] (promień: {radius} km)..."
    )

    def on_progress(stage: str, msg: str):
        console.print(f"  [dim]•[/dim] {msg}")

    try:
        leads, location = asyncio.run(
            run_scan_pipeline(
                country=country_norm,  # type: ignore
                city=city,
                vertical=v_def,
                radius_km=radius,
                lang=target_lang,
                do_audit=not quick,
                no_cache=no_cache,
                min_score=min_score,
                has_phone_only=has_phone,
                progress_callback=on_progress,
            )
        )
    except Exception as e:
        console.print(f"[bold red]Błąd skanowania:[/bold red] {e}")
        raise typer.Exit(code=1)

    # Zapisz pliki wyjściowe
    export_leads_to_csv(leads, csv_path, delimiter=delim_char)
    export_leads_to_json(leads, json_path)

    if not leads:
        console.print(f"\n[yellow]Nie znaleziono firm spełniających kryteria w promieniu {radius} km od {city}.[/yellow]")
        console.print("[dim]Wskazówki: 1) Zwiększ promień (np. --radius 25)[/dim]")
        console.print("[dim]           2) Sprawdź alternatywne nazwy branży (lead.er list-verticals)[/dim]")
        console.print("[dim]           3) Upewnij się co do poprawnej pisowni miasta[/dim]\n")
        return

    # Tabela podsumowania leadów
    table = Table(title=f"Najwyżej ocenione leady - {city} (łącznie znaleziono: {len(leads)})", show_lines=True)
    table.add_column("Werdykt", style="bold", no_wrap=True)
    table.add_column("Wynik", justify="right")
    table.add_column("Nazwa firmy", style="cyan")
    table.add_column("Telefon", style="green")
    table.add_column("Status strony")
    table.add_column("Hook sprzedażowy", style="dim")

    for lead in leads[:8]:
        verdict_style = "bold red" if lead.verdict == "hot" else ("bold yellow" if lead.verdict == "warm" else "dim")
        hook_preview = lead.hooks[0] if lead.hooks else "-"
        table.add_row(
            f"[{verdict_style}]{lead.verdict.upper()}[/{verdict_style}]",
            str(lead.score),
            lead.name,
            lead.phone or "[dim]Brak telefonu[/dim]",
            lead.website_kind,
            hook_preview[:60] + ("..." if len(hook_preview) > 60 else ""),
        )

    console.print()
    console.print(table)
    console.print(f"[bold green]✔ Zakończono![/bold green] Wyeksportowano {len(leads)} leadów:")
    console.print(f"  [bold]CSV:[/bold]  {csv_path.resolve()}")
    console.print(f"  [bold]JSON:[/bold] {json_path.resolve()}")
    console.print(f"[dim]{ODBL_ATTRIBUTION}[/dim]\n")


@app.command()
def audit(
    file_path: Annotated[Path, typer.Argument(help="Ścieżka do istniejącego pliku leads.json")],
    lang: Annotated[str, typer.Option("--lang", "-l", help="Język hooków (pl, de, en)")] = "pl",
    out: Annotated[Optional[Path], typer.Option("--out", "-o", help="Ścieżka docelowa pliku lub katalogu")] = None,
    no_cache: Annotated[bool, typer.Option("--no-cache", "--refresh-audit", help="Pomiń cache dyskowy i wymuś świeży audyt stron www")] = False,
):
    """Przeprowadź ponowny audyt stron www dla leadów z pliku JSON i zaktualizuj punktację."""
    leads = load_leads_from_file(file_path)

    console.print(f"Audytowanie {len(leads)} leadów z pliku {file_path}...")

    async def audit_all():
        cache = AuditCache()
        for lead in leads:
            if not lead.website_kind or lead.website_kind in ("none", "other"):
                lead.website_kind = classify_website_kind(lead.website)
            if lead.website_kind == "own" and lead.website:
                cached_res = None if no_cache else cache.get(lead.website)
                if cached_res is not None:
                    lead.audit = cached_res
                else:
                    lead.audit = await audit_website(lead.website)
                    cache.set(lead.website, lead.audit)
                if not lead.phone and lead.audit.extracted_phones:
                    lead.phone = lead.audit.extracted_phones[0]
                if not lead.email and lead.audit.extracted_emails:
                    lead.email = lead.audit.extracted_emails[0]
            score, verdict = calculate_lead_score(lead)
            lead.score = score
            lead.verdict = verdict
            lead.hooks = generate_pitch_hooks(lead, lang=lang)
        cache.flush()

    asyncio.run(audit_all())

    leads.sort(key=lambda l: l.score, reverse=True)
    csv_path, json_path = determine_output_paths(out or file_path.parent / "leads_audited")
    export_leads_to_csv(leads, csv_path)
    export_leads_to_json(leads, json_path)

    console.print(f"[bold green]✔ Audyt zakończony![/bold green] Wyniki zapisano do {csv_path} i {json_path}")


@app.command()
def export(
    file_path: Annotated[Path, typer.Argument(help="Ścieżka do pliku leads.json")] = Path("leads.json"),
    min_score: Annotated[int, typer.Option("--min-score", help="Minimalny wynik leada do eksportu")] = 0,
    lang: Annotated[str, typer.Option("--lang", "-l", help="Język hooków sprzedażowych (pl, de, en)")] = "pl",
    format: Annotated[str, typer.Option("--format", "-f", help="Format wyjściowy: csv lub json")] = "csv",
    out: Annotated[Optional[Path], typer.Option("--out", "-o", help="Ścieżka docelowa")] = None,
    delimiter: Annotated[str, typer.Option("--delimiter", help="Separator CSV (comma lub semicolon)")] = "comma",
):
    """Filtruj i eksportuj zapisane leady do pliku CSV lub JSON."""
    leads = load_leads_from_file(file_path)

    # Ponowne przeliczenie języka hooków i filtr po minimalnym wyniku
    filtered = []
    for lead in leads:
        if lead.score >= min_score:
            lead.hooks = generate_pitch_hooks(lead, lang=lang)
            filtered.append(lead)

    csv_path, json_path = determine_output_paths(out or Path(f"leads_export_{min_score}"))
    delim_char = ";" if delimiter.lower() in ("semicolon", ";") else ","

    if format.lower() == "json":
        export_leads_to_json(filtered, json_path)
        console.print(f"[bold green]✔ Wyeksportowano {len(filtered)} leadów do JSON:[/bold green] {json_path}")
    else:
        export_leads_to_csv(filtered, csv_path, delimiter=delim_char)
        console.print(f"[bold green]✔ Wyeksportowano {len(filtered)} leadów do CSV:[/bold green] {csv_path}")


@app.command(name="filter")
def filter_leads(
    file_path: Annotated[Path, typer.Argument(help="Ścieżka do pliku leads.json")] = Path("leads.json"),
    min_score: Annotated[int, typer.Option("--min-score", help="Minimalny wynik leada")] = 0,
    has_phone: Annotated[bool, typer.Option("--has-phone", help="Uwzględnij tylko firmy z publicznym numerem telefonu")] = False,
    out: Annotated[Optional[Path], typer.Option("--out", "-o", help="Ścieżka docelowa")] = None,
    format: Annotated[str, typer.Option("--format", "-f", help="Format wyjściowy: csv lub json")] = "csv",
    delimiter: Annotated[str, typer.Option("--delimiter", help="Separator CSV (comma lub semicolon)")] = "comma",
):
    """Lokalne filtrowanie i segregacja zapisanych leadów (BEZ odpytywania sieci)."""
    leads = load_leads_from_file(file_path)

    filtered = []
    for lead in leads:
        if lead.score < min_score:
            continue
        if has_phone and not lead.phone:
            continue
        filtered.append(lead)

    csv_path, json_path = determine_output_paths(out or Path("filtered_leads.csv"))
    delim_char = ";" if delimiter.lower() in ("semicolon", ";") else ","

    if format.lower() == "json" or (out and out.suffix.lower() == ".json"):
        export_leads_to_json(filtered, json_path)
        console.print(f"[bold green]✔ Przefiltrowano {len(filtered)} leadów do JSON:[/bold green] {json_path}")
    else:
        export_leads_to_csv(filtered, csv_path, delimiter=delim_char)
        console.print(f"[bold green]✔ Przefiltrowano {len(filtered)} leadów do CSV:[/bold green] {csv_path}")


@app.command(name="demo-template")
def demo_template_cmd(
    name: Annotated[str, typer.Option("--name", "-n", help="Nazwa firmy")] = ...,
    phone: Annotated[str, typer.Option("--phone", "-p", help="Numer telefonu do kontaktu")] = ...,
    industry: Annotated[str, typer.Option("--industry", "-i", help="Branża")] = "Usługi lokalne",
    city: Annotated[Optional[str], typer.Option("--city", "--miasto", help="Miasto działalności")] = None,
    out: Annotated[Path, typer.Option("--out", "-o", help="Ścieżka pliku wyjściowego")] = Path("index.html"),
):
    """Wygeneruj lekki, responsywny plik HTML one-pager jako demo dla klienta."""
    generate_demo_html(
        name=name,
        industry=industry,
        phone=phone,
        city=city,
        output_path=out,
    )
    console.print(f"[bold green]✔ Wygenerowano szablon demo HTML:[/bold green] {out.resolve()}")


@app.command(name="report")
def report_cmd(
    file_path: Annotated[Path, typer.Argument(help="Ścieżka do pliku leads.json")] = Path("leads.json"),
    out: Annotated[Path, typer.Option("--out", "-o", help="Ścieżka do wyjściowego pliku HTML")] = Path("report.html"),
):
    """Wygeneruj interaktywny, samodzielny raport HTML z kartami leadów do przeglądarki."""
    leads = load_leads_from_file(file_path)

    res_path = generate_html_report(leads, out)
    console.print(f"[bold green]✔ Wygenerowano raport HTML ({len(leads)} leadów):[/bold green] {res_path.resolve()}")
    console.print(f"[dim]Aby otworzyć w przeglądarce: xdg-open {res_path}  (lub kliknij dwukrotnie w plik)[/dim]")


@app.command(name="web")
def web_cmd(
    host: Annotated[str, typer.Option("--host", "-h", help="Host do nasłuchiwania serwera Web GUI")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", "-p", help="Port serwera Web GUI")] = 8000,
    open_browser: Annotated[bool, typer.Option("--open-browser/--no-browser", help="Automatycznie otwórz przeglądarkę internetową")] = True,
):
    """Uruchom interaktywny pulpit Web GUI (FastAPI + Uvicorn) w przeglądarce."""
    try:
        import uvicorn
    except ImportError:
        console.print("[bold red]Błąd:[/bold red] Brakuje pakietu 'uvicorn'. Zainstaluj go przez: pip install uvicorn")
        raise typer.Exit(code=1)

    def _is_port_available(h: str, p: int) -> bool:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((h, p))
                return True
            except OSError:
                return False

    actual_port = port
    if not _is_port_available(host, actual_port):
        for candidate in range(actual_port + 1, actual_port + 100):
            if _is_port_available(host, candidate):
                console.print(f"[bold yellow]Uwaga:[/bold yellow] Port {actual_port} jest zajęty przez inny proces. Przełączono na wolny port [bold cyan]{candidate}[/bold cyan].")
                actual_port = candidate
                break

    url = f"http://{host}:{actual_port}"
    console.print(f"[bold cyan]Wulf Web Leader — Uruchamianie Web GUI...[/bold cyan]")
    console.print(f"[bold green]✔ Adres:[/bold green] [underline]{url}[/underline]")
    console.print("[dim]Naciśnij Ctrl+C, aby zatrzymać serwer.[/dim]")

    if open_browser:
        import threading
        import time
        import webbrowser

        def _open():
            time.sleep(1.2)
            try:
                webbrowser.open(url)
            except Exception:
                pass

        threading.Thread(target=_open, daemon=True).start()

    from wulf_web_leader.web.app import app as fastapi_app

    uvicorn.run(fastapi_app, host=host, port=actual_port, log_level="info")


if __name__ == "__main__":
    app()
