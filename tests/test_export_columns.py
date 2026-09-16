import csv
from pathlib import Path
from wulf_web_leader.models import CanonicalLead
from wulf_web_leader.export.writer import export_leads_to_csv, CSV_COLUMNS


def test_export_leads_to_csv_operational_columns(tmp_path: Path):
    out_file = tmp_path / "test_leads.csv"
    leads = [
        CanonicalLead(
            country="PL",
            name="Super Firma",
            city="Rzeszów",
            street="Rejtana 10",
            postcode="35-310",
            phone="+48178500000",
            website=None,
            website_kind="none",
            source="osm",
            source_id="node/1",
            industry_label="Hydraulik",
            score=70,
            verdict="hot",
            hooks=["Świetna oferta!"],
        )
    ]

    res_path = export_leads_to_csv(leads, out_file)
    assert res_path.is_file()

    # Verify utf-8-sig BOM
    with open(res_path, "rb") as f:
        header_bytes = f.read(3)
        assert header_bytes == b"\xef\xbb\xbf"

    # Verify columns
    with open(res_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        assert fieldnames is not None
        for col in [
            "street", "postcode", "phone", "email",
            "status_kontaktu", "notatki", "data_kontaktu",
            "owner_name", "nip", "regon", "phone_type", "whatsapp_url", "google_maps_url",
        ]:
            assert col in fieldnames

        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["name"] == "Super Firma"
        assert rows[0]["street"] == "Rejtana 10"
        assert rows[0]["postcode"] == "35-310"
        assert rows[0]["phone"] == "+48178500000"
        assert rows[0]["email"] == ""
        assert rows[0]["status_kontaktu"] == ""
        assert rows[0]["notatki"] == ""
        assert rows[0]["data_kontaktu"] == ""
        assert rows[0]["owner_name"] == ""
        assert rows[0]["nip"] == ""
        assert rows[0]["regon"] == ""
        assert rows[0]["phone_type"] == "unknown"
        assert rows[0]["whatsapp_url"] == ""
        assert rows[0]["google_maps_url"] == ""
