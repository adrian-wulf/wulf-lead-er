import csv
import json
from pathlib import Path
from typing import Sequence
from wulf_web_leader.models import CanonicalLead

ODBL_ATTRIBUTION = "Data © OpenStreetMap contributors under ODbL 1.0 (https://www.openstreetmap.org/copyright)"

CSV_COLUMNS = [
    "name",
    "city",
    "street",
    "postcode",
    "country",
    "phone",
    "email",
    "website",
    "website_kind",
    "opportunity_type",
    "primary_issue",
    "confidence",
    "qa_status",
    "qa_notes",
    "score",
    "verdict",
    "hook",
    "status_kontaktu",
    "notatki",
    "data_kontaktu",
    "source",
    "lat",
    "lon",
    "owner_name",
    "nip",
    "regon",
    "phone_type",
    "whatsapp_url",
    "google_maps_url",
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
                "street": lead.street or lead.address or "",
                "postcode": lead.postcode or "",
                "country": lead.country,
                "phone": lead.phone or "",
                "email": lead.email or "",
                "website": lead.website or "",
                "website_kind": lead.website_kind,
                "opportunity_type": lead.opportunity_type,
                "primary_issue": lead.primary_issue or "",
                "confidence": lead.confidence,
                "qa_status": lead.qa_status,
                "qa_notes": lead.qa_notes or "",
                "score": lead.score,
                "verdict": lead.verdict,
                "hook": primary_hook,
                "status_kontaktu": lead.status_kontaktu or "",
                "notatki": lead.notatki or "",
                "data_kontaktu": lead.data_kontaktu or "",
                "source": lead.source,
                "lat": lead.lat if lead.lat is not None else "",
                "lon": lead.lon if lead.lon is not None else "",
                "owner_name": lead.owner_name or "",
                "nip": lead.nip or "",
                "regon": lead.regon or "",
                "phone_type": lead.phone_type,
                "whatsapp_url": lead.whatsapp_url or "",
                "google_maps_url": lead.google_maps_url or "",
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
