import asyncio
import json
from pathlib import Path
from typing import Annotated, Optional
import typer
from rich.console import Console
from rich.table import Table

from brakstrony.models import CanonicalLead, CountryCode
from brakstrony.verticals import load_all_verticals, find_vertical
from brakstrony.pipeline import run_scan_pipeline
from brakstrony.export.writer import export_leads_to_csv, export_leads_to_json, ODBL_ATTRIBUTION
from brakstrony.audit.classifier import classify_website_kind
from brakstrony.audit.fetch import audit_website
from brakstrony.score.engine import calculate_lead_score
from brakstrony.score.hooks import generate_pitch_hooks

app = typer.Typer(
    name="brakstrony",
    help="Robin Hood for local web designers: find small businesses in Poland & Germany that need a website.",
    add_completion=False,
)
console = Console()


def determine_output_paths(out_arg: Optional[Path], default_stem: str = "leads") -> tuple[Path, Path]:
    """Determine JSON and CSV output paths based on --out parameter."""
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


@app.command()
def list_verticals():
    """List all supported business verticals and their local aliases."""
    verticals = load_all_verticals()
    table = Table(title="Available Verticals (Industries)", show_lines=True)
    table.add_column("Vertical ID", style="cyan", no_wrap=True)
    table.add_column("English Name", style="bold")
    table.add_column("PL Query & Aliases", style="green")
    table.add_column("DE Query & Aliases", style="yellow")

    for v in verticals.values():
        pl_aliases = ", ".join([v.pl.query] + v.aliases.pl)
        de_aliases = ", ".join([v.de.query] + v.aliases.de)
        table.add_row(v.id, v.name, pl_aliases, de_aliases)

    console.print(table)


@app.command()
def scan(
    country: Annotated[str, typer.Option("--country", "-c", help="Country code: pl or de")] = "pl",
    city: Annotated[str, typer.Option("--city", help="Target city name (e.g. Rzeszów, Dresden)")] = ...,
    vertical: Annotated[str, typer.Option("--vertical", "-v", help="Industry or trade (e.g. plumbers, hair, hydraulik)")] = ...,
    radius: Annotated[float, typer.Option("--radius", "-r", help="Search radius around city center in km")] = 15.0,
    lang: Annotated[Optional[str], typer.Option("--lang", "-l", help="Language for pitch hooks (pl, de, en)")] = None,
    out: Annotated[Optional[Path], typer.Option("--out", "-o", help="Output file or directory")] = None,
    format: Annotated[str, typer.Option("--format", "-f", help="Primary export format (csv or json)")] = "csv",
    min_score: Annotated[int, typer.Option("--min-score", help="Minimum lead score to include (0-100)")] = 0,
    has_phone: Annotated[bool, typer.Option("--has-phone", help="Include only leads with verified phone numbers")] = False,
    quick: Annotated[bool, typer.Option("--quick", "--no-audit", help="Skip website network audit for fast scanning")] = False,
    delimiter: Annotated[str, typer.Option("--delimiter", help="CSV delimiter (comma or semicolon)")] = "comma",
):
    """Scan a city and radius for businesses needing a website."""
    country_norm = country.strip().upper()
    if country_norm not in ("PL", "DE"):
        console.print(f"[bold red]Error:[/bold red] Country must be 'pl' or 'de' (received '{country}')")
        raise typer.Exit(code=1)

    target_lang = (lang or country_norm.lower()).lower()
    if target_lang not in ("pl", "de", "en"):
        target_lang = "pl" if country_norm == "PL" else "de"

    # Find vertical definition
    v_def = find_vertical(vertical)
    if not v_def:
        console.print(f"[bold red]Error:[/bold red] Unknown vertical '{vertical}'.")
        console.print("Run [cyan]brakstrony list-verticals[/cyan] to see supported industries.")
        raise typer.Exit(code=1)

    delim_char = ";" if delimiter.lower() in ("semicolon", ";") else ","

    csv_path, json_path = determine_output_paths(out, default_stem="leads")

    console.print(
        f"[bold blue]brakstrony[/bold blue] - Scanning [bold cyan]{city}[/bold cyan] ({country_norm}) "
        f"for [bold green]{v_def.name}[/bold green] (radius: {radius} km)..."
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
        console.print(f"[bold red]Pipeline Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    # Export files
    export_leads_to_csv(leads, csv_path, delimiter=delim_char)
    export_leads_to_json(leads, json_path)

    if not leads:
        console.print(f"\n[yellow]No leads found within {radius} km of {city}.[/yellow]")
        console.print("[dim]Tips: 1) Increase --radius (e.g. --radius 25)[/dim]")
        console.print("[dim]      2) Check alternative trade names (brakstrony list-verticals)[/dim]")
        console.print("[dim]      3) Verify city spelling[/dim]\n")
        return

    # Render summary table
    table = Table(title=f"Top Scored Leads - {city} ({len(leads)} total leads found)", show_lines=True)
    table.add_column("Verdict", style="bold", no_wrap=True)
    table.add_column("Score", justify="right")
    table.add_column("Business Name", style="cyan")
    table.add_column("Phone", style="green")
    table.add_column("Website Status")
    table.add_column("Pitch Hook", style="dim")

    for lead in leads[:8]:
        verdict_style = "bold red" if lead.verdict == "hot" else ("bold yellow" if lead.verdict == "warm" else "dim")
        hook_preview = lead.hooks[0] if lead.hooks else "-"
        table.add_row(
            f"[{verdict_style}]{lead.verdict.upper()}[/{verdict_style}]",
            str(lead.score),
            lead.name,
            lead.phone or "[dim]No phone[/dim]",
            lead.website_kind,
            hook_preview[:60] + ("..." if len(hook_preview) > 60 else ""),
        )

    console.print()
    console.print(table)
    console.print(f"[bold green]✔ Done![/bold green] Exported {len(leads)} leads:")
    console.print(f"  [bold]CSV:[/bold]  {csv_path.resolve()}")
    console.print(f"  [bold]JSON:[/bold] {json_path.resolve()}")
    console.print(f"[dim]{ODBL_ATTRIBUTION}[/dim]\n")


@app.command()
def audit(
    file_path: Annotated[Path, typer.Argument(help="Path to existing leads.json file")],
    lang: Annotated[str, typer.Option("--lang", "-l", help="Language for hooks (pl, de, en)")] = "pl",
    out: Annotated[Optional[Path], typer.Option("--out", "-o", help="Output file or directory")] = None,
):
    """Audit websites for existing leads in a JSON file and update scores."""
    if not file_path.is_file():
        console.print(f"[bold red]Error:[/bold red] File '{file_path}' not found.")
        raise typer.Exit(code=1)

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_leads = data.get("leads", []) if isinstance(data, dict) else data
    leads: list[CanonicalLead] = [CanonicalLead.model_validate(item) for item in raw_leads]

    console.print(f"Auditing {len(leads)} leads from {file_path}...")

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

    console.print(f"[bold green]✔ Audit completed![/bold green] Results saved to {csv_path} and {json_path}")


@app.command()
def export(
    file_path: Annotated[Path, typer.Argument(help="Path to leads.json file")] = Path("leads.json"),
    min_score: Annotated[int, typer.Option("--min-score", help="Minimum lead score to export")] = 0,
    lang: Annotated[str, typer.Option("--lang", "-l", help="Language for pitch hooks (pl, de, en)")] = "pl",
    format: Annotated[str, typer.Option("--format", "-f", help="Output format: csv or json")] = "csv",
    out: Annotated[Optional[Path], typer.Option("--out", "-o", help="Output destination path")] = None,
    delimiter: Annotated[str, typer.Option("--delimiter", help="CSV delimiter (comma or semicolon)")] = "comma",
):
    """Filter and export existing leads."""
    if not file_path.is_file():
        console.print(f"[bold red]Error:[/bold red] Input leads file '{file_path}' not found.")
        raise typer.Exit(code=1)

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_leads = data.get("leads", []) if isinstance(data, dict) else data
    leads: list[CanonicalLead] = [CanonicalLead.model_validate(item) for item in raw_leads]

    # Re-apply language hooks and score filter
    filtered = []
    for lead in leads:
        if lead.score >= min_score:
            lead.hooks = generate_pitch_hooks(lead, lang=lang)
            filtered.append(lead)

    csv_path, json_path = determine_output_paths(out or Path(f"leads_export_{min_score}"))
    delim_char = ";" if delimiter.lower() in ("semicolon", ";") else ","

    if format.lower() == "json":
        export_leads_to_json(filtered, json_path)
        console.print(f"[bold green]✔ Exported {len(filtered)} leads to JSON:[/bold green] {json_path}")
    else:
        export_leads_to_csv(filtered, csv_path, delimiter=delim_char)
        console.print(f"[bold green]✔ Exported {len(filtered)} leads to CSV:[/bold green] {csv_path}")


if __name__ == "__main__":
    app()
