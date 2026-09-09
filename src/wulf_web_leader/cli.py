import asyncio
import json
from pathlib import Path
from typing import Annotated, Optional
import typer
from rich.console import Console
from rich.table import Table

from wulf_web_leader.models import CanonicalLead, CountryCode
from wulf_web_leader.verticals import load_all_verticals, find_vertical
from wulf_web_leader.pipeline import run_scan_pipeline
from wulf_web_leader.export.writer import export_leads_to_csv, export_leads_to_json, ODBL_ATTRIBUTION
from wulf_web_leader.audit.classifier import classify_website_kind
from wulf_web_leader.audit.fetch import audit_website
from wulf_web_leader.score.engine import calculate_lead_score
from wulf_web_leader.score.hooks import generate_pitch_hooks

app = typer.Typer(
    name="wulf",
    help="wulf-web-leader: Lokalny skaner leadów dla web designerów (Polska i Niemcy). Bez spamu, bez konta, local-first.",
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

    # Znajdź definicję wertykału
    v_def = find_vertical(vertical)
    if not v_def:
        console.print(f"[bold red]Błąd:[/bold red] Nieznana branża '{vertical}'.")
        console.print("Uruchom [cyan]wulf list-verticals[/cyan], aby zobaczyć obsługiwane branże.")
        raise typer.Exit(code=1)

    delim_char = ";" if delimiter.lower() in ("semicolon", ";") else ","

    csv_path, json_path = determine_output_paths(out, default_stem="leads")

    console.print(
        f"[bold blue]wulf[/bold blue] - Skanowanie [bold cyan]{city}[/bold cyan] ({country_norm}) "
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
        console.print("[dim]           2) Sprawdź alternatywne nazwy branży (wulf list-verticals)[/dim]")
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
):
    """Przeprowadź ponowny audyt stron www dla leadów z pliku JSON i zaktualizuj punktację."""
    if not file_path.is_file():
        console.print(f"[bold red]Błąd:[/bold red] Plik '{file_path}' nie istnieje.")
        raise typer.Exit(code=1)

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_leads = data.get("leads", []) if isinstance(data, dict) else data
    leads: list[CanonicalLead] = [CanonicalLead.model_validate(item) for item in raw_leads]

    console.print(f"Audytowanie {len(leads)} leadów z pliku {file_path}...")

    async def audit_all():
        for lead in leads:
            lead.website_kind = classify_website_kind(lead.website)
            if lead.website_kind == "own" and lead.website:
                lead.audit = await audit_website(lead.website)
                if not lead.phone and lead.audit.extracted_phones:
                    lead.phone = lead.audit.extracted_phones[0]
            score, verdict = calculate_lead_score(lead)
            lead.score = score
            lead.verdict = verdict
            lead.hooks = generate_pitch_hooks(lead, lang=lang)

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
    if not file_path.is_file():
        console.print(f"[bold red]Błąd:[/bold red] Plik wejściowy '{file_path}' nie istnieje.")
        raise typer.Exit(code=1)

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_leads = data.get("leads", []) if isinstance(data, dict) else data
    leads: list[CanonicalLead] = [CanonicalLead.model_validate(item) for item in raw_leads]

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


if __name__ == "__main__":
    app()
