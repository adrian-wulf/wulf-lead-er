import json
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import patch
from wulf_web_leader.cli import app
from wulf_web_leader.models import CanonicalLead

runner = CliRunner()


def test_wulf_filter_cli_command(tmp_path: Path):
    """Test wulf filter command: reads local leads.json, filters with ZERO network calls, outputs CSV."""
    leads = [
        CanonicalLead(
            country="PL",
            name="Firma Hot z Telefonem",
            city="Rzeszów",
            phone="+48178500000",
            website=None,
            website_kind="none",
            source="osm",
            source_id="node/1",
            industry_label="Hydraulik",
            score=70,
            verdict="hot",
            hooks=["Świetna oferta!"],
        ),
        CanonicalLead(
            country="PL",
            name="Firma Hot Bez Telefonu",
            city="Rzeszów",
            phone=None,
            website=None,
            website_kind="none",
            source="osm",
            source_id="node/2",
            industry_label="Hydraulik",
            score=70,
            verdict="hot",
        ),
        CanonicalLead(
            country="PL",
            name="Firma Warm z Telefonem",
            city="Rzeszów",
            phone="+48178500001",
            website="https://fb.com/test",
            website_kind="facebook",
            source="osm",
            source_id="node/3",
            industry_label="Hydraulik",
            score=55,
            verdict="warm",
        ),
    ]

    input_json = tmp_path / "leads.json"
    data = {
        "_attribution": "OSM",
        "count": len(leads),
        "leads": [l.model_dump(mode="json") for l in leads],
    }
    input_json.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    out_csv = tmp_path / "dzis.csv"

    # Patch httpx to ensure ZERO network calls
    with patch("httpx.AsyncClient") as mock_http:
        result = runner.invoke(
            app,
            [
                "filter",
                str(input_json),
                "--min-score", "70",
                "--has-phone",
                "--out", str(out_csv),
            ],
        )
        assert result.exit_code == 0
        mock_http.assert_not_called()

    assert out_csv.is_file()
    content = out_csv.read_text(encoding="utf-8-sig")
    assert "Firma Hot z Telefonem" in content
    assert "Firma Hot Bez Telefonu" not in content
    assert "Firma Warm z Telefonem" not in content
