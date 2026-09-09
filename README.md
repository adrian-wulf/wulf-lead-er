# brakstrony (keinweb)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Local First](https://img.shields.io/badge/cloud-zero%20required-green.svg)](#mission)

> **Robin Hood for local web designers:** find small businesses in Poland and Germany that need a modern website. Free, local-first, zero SaaS, no account, zero cloud required.

---

## Mission

Local freelancers and boutique web design agencies often struggle to find nearby businesses that genuinely need web design services. Most small business owners don't have the time to build a site, or they rely exclusively on Facebook, Instagram, or outdated directory listings.

`brakstrony` (German alias: `keinweb`) scans public listings within your target radius, detects businesses with missing, broken, or mobile-unfriendly websites, calculates an outreach qualification score, and outputs ready-to-use CSV and JSON lead lists complete with localized pitch hooks in Polish or German.

This tool outputs a scored lead list for human contact, **not email spam**.

---

## Ethics & Acceptable Use

- **Human-to-Human Outreach**: This tool discovers public business directory records and public websites so a local designer can walk in or make a personal phone call like a human.
- **NO Spam**: It does **NOT** send bulk emails, sequence cold email campaigns, or facilitate spam.
- **Zero Cloud / Zero Telemetry**: Operates 100% on your local machine. No telemetry, no usage tracking, no remote databases.
- **Respect Rate Limits**:
  - Nominatim is strictly queried with a rate limit (≥ 1.0 second between requests) and identifiable User-Agent headers.
  - Overpass queries are lightweight, bounded in size/timeout, and distributed across public European mirrors.
  - Do not hammer servers. Results are cached locally in `~/.cache/brakstrony/`.
- **Security & Secrets**: Never commit private API tokens or credentials.

---

## Installation

Using `uv` (recommended):
```bash
# Clone the repository
git clone https://github.com/wulf-org/brakstrony.git
cd brakstrony

# Create virtual environment and install
uv venv
uv pip install -e .
```

Or using standard `pip`:
```bash
pip install -e .
```

---

## Quickstart & Demo Commands

### Demo 1: Plumbers in Rzeszów, Poland (15 km radius)
```bash
brakstrony scan --country pl --city Rzeszów --vertical plumbers --radius 15
```
Or use the Polish trade alias:
```bash
brakstrony scan --country pl --city Rzeszów --vertical hydraulik --radius 15
```

### Demo 2: Hair Salons in Dresden, Germany (15 km radius)
```bash
keinweb scan --country de --city Dresden --vertical hair --radius 15 --lang de
```
Or use the German trade alias:
```bash
keinweb scan --country de --city Dresden --vertical friseur --radius 15 --lang de
```

### Quick Territory Scouting (without website HTTP audits)
To instantly scan a region for business counts without waiting for website audits, add `--quick`:
```bash
brakstrony scan --country pl --city Kraków --vertical electricians --radius 20 --quick
```

### Filtering Contactable Leads Only
To only include businesses with a public phone number:
```bash
brakstrony scan --country pl --city Rzeszów --vertical plumbers --radius 15 --has-phone
```

---

## Available Verticals

Run the following command to list all bundled industries and their PL/DE aliases:
```bash
brakstrony list-verticals
```

Shipped verticals:
- `plumbers` (`hydraulik`, `klempner`)
- `electricians` (`elektryk`, `elektriker`)
- `hair` (`fryzjer`, `friseur`, `barber`)
- `auto_repair` (`mechanik`, `autowerkstatt`)
- `restaurant` (`restauracja`, `restaurant`, `gastronomie`)
- `bakery` (`piekarnia`, `bäckerei`, `cukiernia`)
- `veterinary` (`weterynarz`, `tierarzt`)
- `gym` (`siłownia`, `fitnessstudio`)

Custom verticals can be added as YAML files in the `verticals/` folder.

---

## CLI Reference

### `scan`
Scan a geographic area for target businesses.
```bash
brakstrony scan \
  --country pl \
  --city "Rzeszów" \
  --vertical plumbers \
  --radius 15 \
  --lang pl \
  --out ./output/ \
  --min-score 50 \
  --has-phone \
  --delimiter comma
```

### `audit`
Re-audit an existing `leads.json` file to refresh website status and recalculate scores:
```bash
brakstrony audit path/to/leads.json --lang pl
```

### `export`
Filter and re-export leads from an existing JSON file:
```bash
brakstrony export path/to/leads.json --min-score 60 --format csv --out leads_hot.csv
```

---

## Scoring Model

Scores range from 0 to 100:
- `+50` No website (`website_kind == "none"`)
- `+35` Social media or directory listing only (`facebook`, `instagram`, `directory`)
- `+20` Public phone number available (actionable contact)
- `+40` Registered website is completely unreachable (dead/abandoned site)
- `+15` Website is not mobile-friendly (missing viewport)
- `+10` Insecure connection (HTTP-only, no HTTPS)
- `+10` Outdated CMS or generator technology
- `-100` Inactive or dissolved business

**Verdicts**:
- `HOT` (Score ≥ 70): Prime prospect (e.g. no website + phone number available).
- `WARM` (Score ≥ 45): Good prospect (e.g. social-only with phone or missing website without listed phone).
- `SKIP` (Score < 45): Has working, responsive website.

---

## Data License & Attribution

Data is sourced from **OpenStreetMap** contributors via Nominatim and the Overpass API.  
Data is licensed under the [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/).

© OpenStreetMap contributors.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
