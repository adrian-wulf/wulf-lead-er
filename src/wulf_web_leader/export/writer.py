import csv
import json
from pathlib import Path
from typing import Sequence
from wulf_web_leader.models import CanonicalLead

ODBL_ATTRIBUTION = "Data © OpenStreetMap contributors under ODbL 1.0 (https://www.openstreetmap.org/copyright)"

CSV_COLUMNS = [
    "name",
    "city",
    "country",
    "phone",
    "website",
    "website_kind",
    "score",
    "verdict",
    "hook",
    "source",
    "lat",
    "lon",
]


def export_leads_to_csv(
    leads: Sequence[CanonicalLead],
    output_path: Path,
    delimiter: str = ",",
) -> Path:
    """Export leads to CSV with utf-8-sig encoding for seamless Excel compatibility."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, delimiter=delimiter)
        writer.writeheader()

        for lead in leads:
            primary_hook = lead.hooks[0] if lead.hooks else ""
            row = {
                "name": lead.name,
                "city": lead.city or "",
                "country": lead.country,
                "phone": lead.phone or "",
                "website": lead.website or "",
                "website_kind": lead.website_kind,
                "score": lead.score,
                "verdict": lead.verdict,
                "hook": primary_hook,
                "source": lead.source,
                "lat": lead.lat if lead.lat is not None else "",
                "lon": lead.lon if lead.lon is not None else "",
            }
            writer.writerow(row)

    return output_path


def export_leads_to_json(
    leads: Sequence[CanonicalLead],
    output_path: Path,
) -> Path:
    """Export leads to JSON with attribution metadata."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "_attribution": ODBL_ATTRIBUTION,
        "count": len(leads),
        "leads": [lead.model_dump(mode="json") for lead in leads],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return output_path
