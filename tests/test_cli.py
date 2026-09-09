from typer.testing import CliRunner
from unittest.mock import patch, AsyncMock
from wulf_web_leader.cli import app
from wulf_web_leader.models import CanonicalLead
from wulf_web_leader.adapters.nominatim import GeocodedLocation

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "wulf-web-leader" in result.output
    assert "scan" in result.output
    assert "audit" in result.output
    assert "export" in result.output
    assert "list-verticals" in result.output


def test_cli_scan_help():
    result = runner.invoke(app, ["scan", "--help"])
    assert result.exit_code == 0
    assert "--min-score" in result.output
    assert "--has-phone" in result.output
    assert "--no-cache" in result.output
    assert "--refresh-audit" in result.output
    assert "--miasto" in result.output


def test_cli_scan_with_filters(tmp_path):
    mock_leads = [
        CanonicalLead(
            country="PL",
            name="Super Firma",
            lat=50.0,
            lon=20.0,
            phone="+48 123 456 789",
            website="https://superfirma.pl",
            website_kind="own",
            source="osm",
            source_id="node/1",
            industry_label="Hydraulik",
            score=75,
            verdict="hot",
            hooks=["Świetna oferta!"],
        )
    ]
    mock_location = GeocodedLocation(lat=50.0, lon=20.0, display_name="Rzeszów", city="Rzeszów")

    with patch("wulf_web_leader.cli.run_scan_pipeline", new_callable=AsyncMock) as mock_pipeline:
        mock_pipeline.return_value = (mock_leads, mock_location)

        out_csv = tmp_path / "test_out.csv"
        result = runner.invoke(
            app,
            [
                "scan",
                "-c", "pl",
                "--miasto", "Rzeszów",
                "-v", "plumbers",
                "--min-score", "60",
                "--has-phone",
                "--no-cache",
                "-o", str(out_csv),
            ],
        )
        assert result.exit_code == 0
        assert "Super Firma" in result.output
        mock_pipeline.assert_called_once()
        kwargs = mock_pipeline.call_args.kwargs
        assert kwargs["min_score"] == 60
        assert kwargs["has_phone_only"] is True
        assert kwargs["no_cache"] is True
