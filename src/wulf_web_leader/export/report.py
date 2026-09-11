"""Interactive, self-contained HTML report generator for wulf-web-leader.

Generates a modern, single-file offline dashboard with dark theme,
card layout, vanilla JS filtering, and zero external CDN/tracker dependencies.
"""

from pathlib import Path
from datetime import datetime
import html
from typing import Sequence
import urllib.parse
from wulf_web_leader.models import CanonicalLead

ODBL_FOOTER = "Dane © OpenStreetMap contributors under ODbL 1.0 • Wygenerowano lokalnie przez wulf-web-leader"


def generate_html_report(
    leads: Sequence[CanonicalLead],
    output_path: Path,
    title_suffix: str = "",
) -> Path:
    """Generate a self-contained HTML report from leads."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Calculate summary metrics
    total_count = len(leads)
    hot_count = sum(1 for l in leads if l.verdict == "hot")
    warm_count = sum(1 for l in leads if l.verdict == "warm")
    skip_count = sum(1 for l in leads if l.verdict == "skip")
    phone_count = sum(1 for l in leads if l.phone and l.phone.strip())
    email_count = sum(1 for l in leads if l.email and l.email.strip())
    qa_verified_count = sum(1 for l in leads if l.qa_status == "verified")
    qa_placeholder_count = sum(1 for l in leads if l.qa_status == "placeholder")

    # Detect dominant city and industry label
    cities = [l.city for l in leads if l.city]
    dominant_city = max(set(cities), key=cities.count) if cities else "Lokalizacja nieokreślona"
    industries = [l.industry_label for l in leads if l.industry_label]
    dominant_industry = max(set(industries), key=industries.count) if industries else "Wszystkie branże"

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Build lead cards HTML
    cards_html = []
    for lead in leads:
        safe_name = html.escape(lead.name or "Nieznana firma")
        safe_city = html.escape(lead.city or "")
        street_val = lead.street or lead.address or ""
        safe_street = html.escape(street_val)
        safe_postcode = html.escape(lead.postcode or "")
        full_address = ", ".join(filter(bool, [safe_street, safe_postcode, safe_city])) or "Brak adresu w bazie"

        verdict_str = (lead.verdict or "skip").lower()
        badge_verdict_class = f"verdict-{verdict_str}"
        verdict_label = verdict_str.upper()

        # Primary hook
        primary_hook = lead.hooks[0] if lead.hooks else "Brak dedykowanego hooka"
        safe_hook = html.escape(primary_hook)

        phone_val = lead.phone or ""
        safe_phone = html.escape(phone_val)
        if phone_val:
            phone_html = f'<a href="tel:{safe_phone}" class="phone-link">📞 {safe_phone}</a>'
        else:
            phone_html = '<span class="text-muted">Brak telefonu</span>'

        email_val = lead.email or ""
        safe_email = html.escape(email_val)
        if email_val:
            if lead.country == "DE":
                subject_txt = f"Anfrage zur Website — {lead.name}"
                body_txt = (
                    f"Sehr geehrte Damen und Herren,\n\n"
                    f"ich habe Ihr Unternehmen {lead.name} in {lead.city or ''} bemerkt.\n"
                    f"{primary_hook}\n\n"
                    f"Gerne erstelle ich für Sie einen unverbindlichen Vorschlag bzw. Entwurf für einen zeitgemäßen Webauftritt.\n\n"
                    f"Mit freundlichen Grüßen"
                )
            else:
                subject_txt = f"Zapytanie o stronę internetową — {lead.name}"
                body_txt = (
                    f"Dzień dobry,\n\n"
                    f"Zauważyłem Państwa firmę {lead.name} w {lead.city or ''}.\n"
                    f"{primary_hook}\n\n"
                    f"Chętnie przygotuję dla Państwa propozycję / bezpłatny projekt strony www.\n\n"
                    f"Pozdrawiam"
                )
            subject_enc = urllib.parse.quote(subject_txt)
            body_enc = urllib.parse.quote(body_txt)
            email_html = (
                f'<div class="email-row">'
                f'<a href="mailto:{safe_email}?subject={subject_enc}&body={body_enc}" class="email-link" title="Napisz e-mail z gotowym tematem i hookiem">'
                f'✉️ {safe_email}</a>'
                f'<button type="button" class="btn-copy-email" onclick="copyEmail(\'{safe_email}\', this)" title="Kopiuj adres e-mail">📋</button>'
                f'</div>'
            )
        else:
            email_html = '<span class="text-muted">Brak adresu e-mail</span>'

        website_val = lead.website or ""
        safe_website = html.escape(website_val)
        kind = lead.website_kind or "none"
        opp_type = lead.opportunity_type
        primary_issue = lead.primary_issue

        if opp_type == "broken_website":
            opp_badge = '<span class="badge badge-broken">🔴 Awaria strony</span>'
        elif opp_type == "critical_redesign":
            opp_badge = '<span class="badge badge-redesign">🟠 Pilny redesign</span>'
        elif opp_type == "social_only":
            opp_badge = '<span class="badge badge-social">📱 Tylko Social Media</span>'
        elif opp_type == "directory_only":
            opp_badge = '<span class="badge badge-dir">📁 Katalog / Wizytówka</span>'
        elif opp_type == "suspect_unverified":
            opp_badge = '<span class="badge badge-suspect">⚠️ Spółka (do weryfikacji)</span>'
        elif opp_type == "modern_active":
            opp_badge = '<span class="badge badge-own">🌐 Aktywna witryna</span>'
        else:
            opp_badge = '<span class="badge badge-no-site">🟢 Brak strony w OSM</span>'

        if kind == "none":
            web_html = f'{opp_badge}'
        elif kind in ("facebook", "instagram"):
            web_html = f'<a href="{safe_website}" target="_blank" rel="noopener" class="web-link">📱 {safe_website}</a> {opp_badge}'
        elif kind == "directory":
            web_html = f'<a href="{safe_website}" target="_blank" rel="noopener" class="web-link">📁 {safe_website}</a> {opp_badge}'
        else:
            web_html = f'<a href="{safe_website}" target="_blank" rel="noopener" class="web-link">🌐 {safe_website}</a> {opp_badge}'

        # OSM map link
        if lead.lat is not None and lead.lon is not None:
            osm_url = f"https://www.openstreetmap.org/?mlat={lead.lat}&mlon={lead.lon}#map=17/{lead.lat}/{lead.lon}"
            osm_link = f'<a href="{osm_url}" target="_blank" rel="noopener" class="osm-link">🗺️ Pokaż w OpenStreetMap</a>'
        else:
            osm_link = ""

        # Contact notes
        notes_val = lead.notatki or lead.status_kontaktu or ""
        if notes_val:
            notes_html = f'<span class="notes-text">{html.escape(notes_val)}</span>'
        else:
            notes_html = '<span class="text-muted italic">do uzupełnienia w CSV</span>'

        # QA Verification badge
        qa_status = lead.qa_status
        qa_notes = lead.qa_notes or ""
        safe_qa_notes = html.escape(qa_notes)

        if qa_status == "verified":
            qa_badge = '<span class="badge badge-qa-verified">🟢 Zweryfikowano QA</span>'
        elif qa_status == "placeholder":
            qa_badge = '<span class="badge badge-qa-placeholder">🟡 Zaślepka / Parking</span>'
        elif qa_status == "mismatch":
            qa_badge = '<span class="badge badge-qa-mismatch">🔴 Mismatch tożsamości</span>'
        else:
            qa_badge = '<span class="badge badge-qa-unverified">⚪ Brak weryfikacji</span>'

        qa_html = f'<div class="card-row qa-row"><span class="qa-shield">🛡️ QA:</span> {qa_badge} {f"<span class=\"qa-notes-text\">{safe_qa_notes}</span>" if safe_qa_notes else ""}</div>'

        # Diagnostic issue HTML
        issue_html = f'<div class="issue-tag">⚙️ Diagnoza: {html.escape(primary_issue)}</div>' if primary_issue else ""

        # Google search link for unverified / suspect leads
        google_query = f'"{lead.name}" {lead.city or ""}'.strip()
        google_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(google_query)}"
        google_btn = (
            f'<a href="{google_url}" target="_blank" rel="noopener noreferrer" class="btn-google-check">'
            f'🔍 Sprawdź w Google</a>'
        )

        if opp_type == "suspect_unverified":
            caution_html = (
                f'<div class="alert-suspect">'
                f'<div class="alert-text">⚠️ <strong>Spółka prawa handlowego:</strong> '
                f'Strona prawdopodobnie istnieje poza danymi OSM. Sprawdź przed wykonaniem telefonu.</div>'
                f'<div class="alert-action">{google_btn}</div>'
                f'</div>'
            )
        elif qa_status in ("unverified", "mismatch") and not lead.website:
            caution_html = (
                f'<div class="alert-suspect alert-unverified">'
                f'<div class="alert-text">ℹ️ <strong>Brak witryny w rejestrze map:</strong> '
                f'Sprawdź obecność w wyszukiwarce.</div>'
                f'<div class="alert-action">{google_btn}</div>'
                f'</div>'
            )
        else:
            caution_html = ""

        source_info = f"{html.escape(lead.source)}: {html.escape(lead.source_id)}"

        card = f"""
        <article class="lead-card {badge_verdict_class}" 
                 data-verdict="{verdict_str}" 
                 data-opp="{opp_type}"
                 data-qa="{qa_status}"
                 data-has-phone="{'true' if phone_val else 'false'}"
                 data-has-email="{'true' if email_val else 'false'}"
                 data-search="{safe_name.lower()} {safe_city.lower()} {safe_street.lower()} {phone_val.lower()} {email_val.lower()}">
            <header class="card-header">
                <div class="card-title-wrap">
                    <h3 class="card-title">{safe_name}</h3>
                    <span class="card-industry">{html.escape(lead.industry_label or '')}</span>
                </div>
                <div class="card-score-badge {badge_verdict_class}">
                    <span class="score-num">{lead.score}</span>
                    <span class="verdict-tag">{verdict_label}</span>
                </div>
            </header>

            <div class="card-body">
                <div class="card-row contact-row">
                    <div class="contact-item">{phone_html}</div>
                    <div class="contact-item">{email_html}</div>
                    <div class="contact-item">{web_html}</div>
                </div>

                <div class="card-row address-row">
                    <span class="addr-icon">📍</span>
                    <span class="addr-text">{full_address}</span>
                    {f'<span class="osm-sep">•</span> {osm_link}' if osm_link else ''}
                </div>

                {qa_html}
                {issue_html}
                {caution_html}

                <div class="hook-box">
                    <div class="hook-header">💡 Pitch hook dla klienta:</div>
                    <p class="hook-text">{safe_hook}</p>
                </div>

                <div class="status-box">
                    <span class="status-label">Status kontaktu / Notatki:</span>
                    {notes_html}
                </div>
            </div>

            <footer class="card-footer">
                <span class="source-info">ID: {source_info}</span>
                <span class="country-pill">{html.escape(lead.country)}</span>
            </footer>
        </article>
        """
        cards_html.append(card)

    rendered_cards = "\n".join(cards_html)

    html_content = f"""<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Raport Leadów — wulf-web-leader {html.escape(title_suffix)}</title>
    <style>
        :root {{
            --bg-body: #090d16;
            --bg-surface: #111827;
            --bg-card: #1f2937;
            --bg-card-hover: #263345;
            --border-color: #374151;
            --text-main: #f9fafb;
            --text-muted: #9ca3af;
            --hot-color: #ef4444;
            --hot-bg: rgba(239, 68, 68, 0.15);
            --warm-color: #f59e0b;
            --warm-bg: rgba(245, 158, 11, 0.15);
            --skip-color: #6b7280;
            --skip-bg: rgba(107, 114, 128, 0.15);
            --primary: #3b82f6;
            --primary-hover: #2563eb;
            --accent-green: #10b981;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background-color: var(--bg-body);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.5;
            padding: 2rem 1.5rem;
        }}

        .container {{
            max-width: 1380px;
            margin: 0 auto;
        }}

        /* Header */
        header.main-header {{
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 20px rgba(0,0,0,0.4);
        }}

        .header-top {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            flex-wrap: wrap;
            gap: 1rem;
            margin-bottom: 1.5rem;
        }}

        .brand-title {{
            font-size: 1.85rem;
            font-weight: 800;
            letter-spacing: -0.025em;
            color: #ffffff;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .brand-pill {{
            background: var(--primary);
            font-size: 0.75rem;
            padding: 0.2rem 0.6rem;
            border-radius: 9999px;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .meta-info {{
            color: var(--text-muted);
            font-size: 0.95rem;
            margin-top: 0.25rem;
        }}

        .meta-info strong {{
            color: var(--text-main);
        }}

        /* Counters row */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1rem;
        }}

        .metric-card {{
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 8px;
            padding: 1rem;
            display: flex;
            flex-direction: column;
        }}

        .metric-label {{
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            font-weight: 600;
        }}

        .metric-value {{
            font-size: 1.8rem;
            font-weight: 800;
            margin-top: 0.25rem;
        }}

        .metric-card.hot .metric-value {{ color: var(--hot-color); }}
        .metric-card.warm .metric-value {{ color: var(--warm-color); }}
        .metric-card.skip .metric-value {{ color: var(--skip-color); }}
        .metric-card.phone .metric-value {{ color: var(--accent-green); }}
        .metric-card.email .metric-value {{ color: #38bdf8; }}
        .metric-card.qa-ver .metric-value {{ color: #10b981; }}
        .metric-card.qa-pl .metric-value {{ color: #f59e0b; }}

        .badge-qa-verified {{ background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 4px; font-weight: 600; }}
        .badge-qa-placeholder {{ background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 4px; font-weight: 600; }}
        .badge-qa-mismatch {{ background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 4px; font-weight: 600; }}
        .badge-qa-unverified {{ background: rgba(107, 114, 128, 0.2); color: #9ca3af; border: 1px solid rgba(107, 114, 128, 0.3); font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 4px; font-weight: 600; }}
        .qa-row {{ display: flex; align-items: center; gap: 0.5rem; font-size: 0.82rem; background: rgba(15, 23, 42, 0.5); padding: 0.4rem 0.6rem; border-radius: 4px; border: 1px solid rgba(255,255,255,0.05); }}
        .qa-shield {{ font-size: 0.9rem; }}
        .qa-notes-text {{ color: var(--text-muted); font-size: 0.8rem; font-style: italic; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 500px; }}

        /* Filters Bar */
        .controls-panel {{
            background: var(--bg-surface);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 1.25rem;
            margin-bottom: 2rem;
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            align-items: center;
            justify-content: space-between;
        }}

        .filter-buttons {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }}

        .filter-btn {{
            background: #1f2937;
            border: 1px solid var(--border-color);
            color: var(--text-main);
            padding: 0.5rem 1rem;
            border-radius: 6px;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
        }}

        .filter-btn:hover {{
            background: #374151;
        }}

        .filter-btn.active {{
            background: var(--primary);
            border-color: var(--primary-hover);
            color: #ffffff;
        }}

        .checkbox-label {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.9rem;
            font-weight: 600;
            color: var(--text-main);
            cursor: pointer;
            background: #1f2937;
            border: 1px solid var(--border-color);
            padding: 0.5rem 1rem;
            border-radius: 6px;
            user-select: none;
        }}

        .checkbox-label input {{
            accent-color: var(--primary);
            cursor: pointer;
        }}

        .search-wrap {{
            flex: 1;
            min-width: 250px;
        }}

        .search-input {{
            width: 100%;
            background: #0f172a;
            border: 1px solid var(--border-color);
            color: #ffffff;
            padding: 0.55rem 1rem;
            border-radius: 6px;
            font-size: 0.95rem;
            outline: none;
        }}

        .search-input:focus {{
            border-color: var(--primary);
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3);
        }}

        .status-counter {{
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-top: 0.5rem;
            width: 100%;
        }}

        /* Cards Grid */
        .cards-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
            gap: 1.5rem;
        }}

        .lead-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
        }}

        .lead-card:hover {{
            background: var(--bg-card-hover);
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.3);
        }}

        .lead-card.verdict-hot {{
            border-left: 5px solid var(--hot-color);
        }}

        .lead-card.verdict-warm {{
            border-left: 5px solid var(--warm-color);
        }}

        .lead-card.verdict-skip {{
            border-left: 5px solid var(--skip-color);
            opacity: 0.85;
        }}

        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 1rem;
            margin-bottom: 1rem;
            padding-bottom: 0.75rem;
            border-bottom: 1px solid rgba(255,255,255,0.07);
        }}

        .card-title {{
            font-size: 1.25rem;
            font-weight: 700;
            color: #ffffff;
            line-height: 1.3;
        }}

        .card-industry {{
            font-size: 0.8rem;
            color: var(--text-muted);
            text-transform: uppercase;
            font-weight: 600;
        }}

        .card-score-badge {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 0.4rem 0.75rem;
            border-radius: 8px;
            min-width: 65px;
            text-align: center;
        }}

        .card-score-badge.verdict-hot {{
            background: var(--hot-bg);
            color: var(--hot-color);
            border: 1px solid rgba(239, 68, 68, 0.3);
        }}

        .card-score-badge.verdict-warm {{
            background: var(--warm-bg);
            color: var(--warm-color);
            border: 1px solid rgba(245, 158, 11, 0.3);
        }}

        .card-score-badge.verdict-skip {{
            background: var(--skip-bg);
            color: var(--skip-color);
            border: 1px solid rgba(107, 114, 128, 0.3);
        }}

        .score-num {{
            font-size: 1.4rem;
            font-weight: 800;
            line-height: 1;
        }}

        .verdict-tag {{
            font-size: 0.7rem;
            font-weight: 700;
            text-transform: uppercase;
            margin-top: 0.2rem;
        }}

        .card-body {{
            display: flex;
            flex-direction: column;
            gap: 0.85rem;
            margin-bottom: 1.25rem;
        }}

        .card-row {{
            font-size: 0.92rem;
        }}

        .contact-row {{
            display: flex;
            flex-direction: column;
            gap: 0.4rem;
        }}

        .phone-link {{
            color: #38bdf8;
            text-decoration: none;
            font-weight: 700;
            font-size: 1.05rem;
        }}

        .phone-link:hover {{
            text-decoration: underline;
        }}

        .email-row {{
            display: flex;
            align-items: center;
            gap: 0.45rem;
            flex-wrap: wrap;
        }}

        .email-link {{
            color: #38bdf8;
            text-decoration: none;
            font-weight: 600;
            font-size: 0.92rem;
            word-break: break-all;
        }}

        .email-link:hover {{
            text-decoration: underline;
        }}

        .btn-copy-email {{
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.18);
            color: var(--text-muted);
            border-radius: 4px;
            padding: 0.15rem 0.45rem;
            font-size: 0.72rem;
            cursor: pointer;
            transition: all 0.15s ease;
            line-height: 1;
        }}

        .btn-copy-email:hover {{
            background: rgba(59, 130, 246, 0.3);
            color: #ffffff;
            border-color: #3b82f6;
        }}

        .web-link {{
            color: #93c5fd;
            text-decoration: none;
            word-break: break-all;
            font-size: 0.9rem;
        }}

        .web-link:hover {{
            text-decoration: underline;
        }}

        .badge {{
            display: inline-block;
            font-size: 0.75rem;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-weight: 600;
            margin-left: 0.35rem;
        }}

        .badge-no-site {{
            background: rgba(239, 68, 68, 0.2);
            color: #fca5a5;
        }}

        .badge-broken {{
            background: rgba(239, 68, 68, 0.35);
            color: #fca5a5;
            border: 1px solid rgba(239, 68, 68, 0.4);
        }}

        .badge-redesign {{
            background: rgba(249, 115, 22, 0.3);
            color: #fdba74;
            border: 1px solid rgba(249, 115, 22, 0.4);
        }}

        .badge-suspect {{
            background: rgba(234, 179, 8, 0.25);
            color: #fef08a;
            border: 1px solid rgba(234, 179, 8, 0.4);
        }}

        .badge-social {{
            background: rgba(59, 130, 246, 0.2);
            color: #93c5fd;
        }}

        .badge-dir {{
            background: rgba(245, 158, 11, 0.2);
            color: #fde68a;
        }}

        .badge-own {{
            background: rgba(16, 185, 129, 0.2);
            color: #6ee7b7;
        }}

        .issue-tag {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 0.4rem 0.65rem;
            border-radius: 6px;
            font-size: 0.83rem;
            color: #e2e8f0;
        }}

        .alert-suspect {{
            background: rgba(234, 179, 8, 0.12);
            border: 1px solid rgba(234, 179, 8, 0.35);
            color: #fef08a;
            padding: 0.6rem 0.8rem;
            border-radius: 6px;
            font-size: 0.82rem;
            line-height: 1.4;
            display: flex;
            flex-direction: column;
            gap: 0.45rem;
        }}

        .alert-suspect.alert-unverified {{
            background: rgba(148, 163, 184, 0.08);
            border-color: rgba(148, 163, 184, 0.25);
            color: #cbd5e1;
        }}

        .btn-google-check {{
            display: inline-flex;
            align-items: center;
            align-self: flex-start;
            gap: 0.35rem;
            background: #2563eb;
            color: #ffffff;
            font-size: 0.78rem;
            font-weight: 600;
            padding: 0.35rem 0.75rem;
            border-radius: 4px;
            text-decoration: none;
            transition: background 0.15s ease;
        }}

        .btn-google-check:hover {{
            background: #1d4ed8;
            text-decoration: none;
            color: #ffffff;
        }}

        .address-row {{
            color: var(--text-muted);
            display: flex;
            align-items: flex-start;
            gap: 0.4rem;
            font-size: 0.88rem;
        }}

        .osm-sep {{
            color: var(--border-color);
            margin: 0 0.25rem;
        }}

        .osm-link {{
            color: #38bdf8;
            text-decoration: none;
            font-size: 0.82rem;
            white-space: nowrap;
        }}

        .osm-link:hover {{
            text-decoration: underline;
        }}

        .hook-box {{
            background: rgba(15, 23, 42, 0.75);
            border-left: 3px solid #38bdf8;
            padding: 0.75rem;
            border-radius: 4px;
            font-size: 0.88rem;
        }}

        .hook-header {{
            font-size: 0.75rem;
            font-weight: 700;
            color: #38bdf8;
            text-transform: uppercase;
            margin-bottom: 0.25rem;
        }}

        .hook-text {{
            color: #e2e8f0;
            font-style: italic;
        }}

        .status-box {{
            background: rgba(0, 0, 0, 0.25);
            padding: 0.6rem 0.75rem;
            border-radius: 4px;
            font-size: 0.82rem;
            display: flex;
            gap: 0.4rem;
            flex-wrap: wrap;
        }}

        .status-label {{
            font-weight: 600;
            color: var(--text-muted);
        }}

        .italic {{ font-style: italic; }}
        .text-muted {{ color: var(--text-muted); }}

        .card-footer {{
            padding-top: 0.75rem;
            border-top: 1px solid rgba(255,255,255,0.06);
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.75rem;
            color: #6b7280;
        }}

        .country-pill {{
            background: rgba(255,255,255,0.06);
            padding: 0.15rem 0.45rem;
            border-radius: 4px;
            font-weight: 700;
        }}

        /* Footer */
        footer.main-footer {{
            margin-top: 3rem;
            padding-top: 1.5rem;
            border-top: 1px solid var(--border-color);
            text-align: center;
            font-size: 0.85rem;
            color: var(--text-muted);
        }}

        .hidden {{
            display: none !important;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header class="main-header">
            <div class="header-top">
                <div>
                    <h1 class="brand-title">
                        wulf-web-leader
                        <span class="brand-pill">Raport</span>
                    </h1>
                    <div class="meta-info">
                        Miasto: <strong>{html.escape(dominant_city)}</strong> • 
                        Branża: <strong>{html.escape(dominant_industry)}</strong> • 
                        Wygenerowano: <strong>{date_str}</strong>
                    </div>
                </div>
            </div>

            <div class="metrics-grid">
                <div class="metric-card">
                    <span class="metric-label">Wszystkie leady</span>
                    <span class="metric-value">{total_count}</span>
                </div>
                <div class="metric-card hot">
                    <span class="metric-label">Gorące (HOT)</span>
                    <span class="metric-value">{hot_count}</span>
                </div>
                <div class="metric-card warm">
                    <span class="metric-label">Ciepłe (WARM)</span>
                    <span class="metric-value">{warm_count}</span>
                </div>
                <div class="metric-card skip">
                    <span class="metric-label">Pomiń (SKIP)</span>
                    <span class="metric-value">{skip_count}</span>
                </div>
                <div class="metric-card phone">
                    <span class="metric-label">Z telefonem</span>
                    <span class="metric-value">{phone_count}</span>
                </div>
                <div class="metric-card email">
                    <span class="metric-label">Z e-mailem</span>
                    <span class="metric-value">{email_count}</span>
                </div>
                <div class="metric-card qa-ver">
                    <span class="metric-label">Zweryfikowane QA</span>
                    <span class="metric-value">{qa_verified_count}</span>
                </div>
                <div class="metric-card qa-pl">
                    <span class="metric-label">Zaślepki / Parking</span>
                    <span class="metric-value">{qa_placeholder_count}</span>
                </div>
            </div>
        </header>

        <section class="controls-panel">
            <div class="filter-buttons">
                <button class="filter-btn active" data-filter="all">Wszystkie ({total_count})</button>
                <button class="filter-btn" data-filter="hot">HOT ({hot_count})</button>
                <button class="filter-btn" data-filter="warm">WARM ({warm_count})</button>
                <button class="filter-btn" data-filter="skip">SKIP ({skip_count})</button>
                <button class="filter-btn" data-filter="qa-verified">🟢 QA ({qa_verified_count})</button>
                <button class="filter-btn" data-filter="qa-placeholder">🟡 Zaślepki ({qa_placeholder_count})</button>
            </div>

            <label class="checkbox-label">
                <input type="checkbox" id="phone-only-checkbox">
                📞 Tylko z telefonem
            </label>

            <label class="checkbox-label">
                <input type="checkbox" id="email-only-checkbox">
                ✉️ Tylko z e-mailem
            </label>

            <div class="search-wrap">
                <input type="text" id="search-input" class="search-input" placeholder="Szukaj po nazwie firmy, ulicy, telefonie, emailu...">
            </div>

            <div class="status-counter" id="status-counter">
                Wyświetlono: <strong id="visible-count">{total_count}</strong> z {total_count} leadów
            </div>
        </section>

        <main class="cards-grid" id="leads-grid">
            {rendered_cards}
        </main>

        <footer class="main-footer">
            <p>{ODBL_FOOTER}</p>
        </footer>
    </div>

    <script>
        function copyEmail(email, btn) {{
            if (!navigator.clipboard) {{
                const ta = document.createElement('textarea');
                ta.value = email;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
            }} else {{
                navigator.clipboard.writeText(email);
            }}
            const orig = btn.textContent;
            btn.textContent = '✓';
            setTimeout(() => {{
                btn.textContent = orig;
            }}, 1500);
        }}

        (function() {{
            const cards = Array.from(document.querySelectorAll('.lead-card'));
            const filterButtons = document.querySelectorAll('.filter-btn');
            const phoneCheckbox = document.getElementById('phone-only-checkbox');
            const emailCheckbox = document.getElementById('email-only-checkbox');
            const searchInput = document.getElementById('search-input');
            const visibleCountEl = document.getElementById('visible-count');

            let currentFilter = 'all';
            let currentPhoneOnly = false;
            let currentEmailOnly = false;
            let currentQuery = '';

            function applyFilters() {{
                let count = 0;
                cards.forEach(card => {{
                    const verdict = card.dataset.verdict;
                    const qa = card.dataset.qa;
                    const hasPhone = card.dataset.hasPhone === 'true';
                    const hasEmail = card.dataset.hasEmail === 'true';
                    const searchText = card.dataset.search || '';

                    let matchesFilter = false;
                    if (currentFilter === 'all') {{
                        matchesFilter = true;
                    }} else if (currentFilter === 'qa-verified') {{
                        matchesFilter = (qa === 'verified');
                    }} else if (currentFilter === 'qa-placeholder') {{
                        matchesFilter = (qa === 'placeholder');
                    }} else {{
                        matchesFilter = (verdict === currentFilter);
                    }}

                    const matchesPhone = (!currentPhoneOnly || hasPhone);
                    const matchesEmail = (!currentEmailOnly || hasEmail);
                    const matchesQuery = (!currentQuery || searchText.includes(currentQuery));

                    if (matchesFilter && matchesPhone && matchesEmail && matchesQuery) {{
                        card.classList.remove('hidden');
                        count++;
                    }} else {{
                        card.classList.add('hidden');
                    }}
                }});
                visibleCountEl.textContent = count;
            }}

            filterButtons.forEach(btn => {{
                btn.addEventListener('click', () => {{
                    filterButtons.forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    currentFilter = btn.dataset.filter;
                    applyFilters();
                }});
            }});

            phoneCheckbox.addEventListener('change', (e) => {{
                currentPhoneOnly = e.target.checked;
                applyFilters();
            }});

            emailCheckbox.addEventListener('change', (e) => {{
                currentEmailOnly = e.target.checked;
                applyFilters();
            }});

            searchInput.addEventListener('input', (e) => {{
                currentQuery = e.target.value.toLowerCase().trim();
                applyFilters();
            }});
        }})();
    </script>
</body>
</html>
"""

    output_path.write_text(html_content, encoding="utf-8")
    return output_path
