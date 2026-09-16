import re
from pathlib import Path


def clean_phone_for_tel(phone: str) -> str:
    """Normalize phone string for tel: link."""
    return re.sub(r"[^\d+]", "", phone)


def generate_demo_html(
    name: str,
    industry: str,
    phone: str,
    city: str | None = None,
    output_path: Path = Path("index.html"),
) -> Path:
    """Generate a clean, responsive single-page HTML demo site for sales outreach."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tel_link = clean_phone_for_tel(phone)
    city_str = f" • {city}" if city else ""

    html_content = f"""<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{name} — {industry}{city_str}</title>
  <style>
    :root {{
      --primary: #0284c7;
      --primary-hover: #0369a1;
      --bg: #f8fafc;
      --text: #0f172a;
      --card-bg: #ffffff;
      --muted: #64748b;
    }}
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}
    body {{
      background: var(--bg);
      color: var(--text);
      line-height: 1.6;
      padding: 24px 16px;
    }}
    .container {{
      max-width: 640px;
      margin: 0 auto;
      background: var(--card-bg);
      border-radius: 16px;
      padding: 32px 24px;
      box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
      text-align: center;
    }}
    .badge {{
      display: inline-block;
      background: #e0f2fe;
      color: #0369a1;
      font-size: 14px;
      font-weight: 600;
      padding: 4px 12px;
      border-radius: 9999px;
      margin-bottom: 16px;
    }}
    h1 {{
      font-size: 28px;
      font-weight: 800;
      color: var(--text);
      margin-bottom: 12px;
    }}
    p.lead {{
      font-size: 16px;
      color: var(--muted);
      margin-bottom: 28px;
    }}
    .cta-box {{
      background: #f1f5f9;
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 28px;
    }}
    .cta-btn {{
      display: inline-block;
      background: var(--primary);
      color: #ffffff;
      font-size: 18px;
      font-weight: 700;
      text-decoration: none;
      padding: 14px 28px;
      border-radius: 10px;
      box-shadow: 0 4px 12px rgba(2, 132, 199, 0.3);
      transition: background 0.2s ease;
    }}
    .cta-btn:hover {{
      background: var(--primary-hover);
    }}
    .phone-display {{
      display: block;
      margin-top: 10px;
      font-size: 15px;
      color: var(--muted);
    }}
    .features {{
      text-align: left;
      margin-top: 24px;
      border-top: 1px solid #e2e8f0;
      padding-top: 24px;
    }}
    .feature-item {{
      display: flex;
      align-items: center;
      margin-bottom: 12px;
      font-size: 15px;
    }}
    .feature-item svg {{
      width: 20px;
      height: 20px;
      color: #10b981;
      margin-right: 10px;
      flex-shrink: 0;
    }}
    footer {{
      margin-top: 32px;
      font-size: 13px;
      color: #94a3b8;
    }}
  </style>
</head>
<body>
  <div class="container">
    <span class="badge">{industry}</span>
    <h1>{name}</h1>
    <p class="lead">Profesjonalne usługi dla klientów lokalnych{city_str}. Szybki kontakt i gwarancja solidności.</p>

    <div class="cta-box">
      <a href="tel:{tel_link}" class="cta-btn">📞 Zadzwoń teraz</a>
      <span class="phone-display">{phone}</span>
    </div>

    <div class="features">
      <div class="feature-item">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
        Dostępność na smartfonach i szybkie wybieranie numeru jednym kliknięciem
      </div>
      <div class="feature-item">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
        Zoptymalizowana widoczność w wyszukiwarce dla klientów z okolicy
      </div>
      <div class="feature-item">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
        Błyskawiczne ładowanie bez zbędnego kodu i reklam
      </div>
    </div>

    <footer>
      Wersja demonstracyjna strony przygotowana dla {name}.
    </footer>
  </div>
</body>
</html>
"""
    output_path.write_text(html_content, encoding="utf-8")
    return output_path
