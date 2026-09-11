from typer.testing import CliRunner
from unittest.mock import patch, AsyncMock
from wulf_web_leader.cli import app
from wulf_web_leader.adapters.nominatim import GeocodedLocation

runner = CliRunner()


def test_cli_error_invalid_city():
    """Ścieżka 1: Złe miasto (brak geokodowania) -> czytelny polski komunikat bez tracebacku."""
    with patch("wulf_web_leader.pipeline.NominatimClient.geocode", new_callable=AsyncMock) as mock_geo:
        mock_geo.return_value = None

        result = runner.invoke(
            app,
            ["scan", "-c", "pl", "--miasto", "ZmysloneMiasto123", "-v", "plumbers"],
        )
        assert result.exit_code == 1
        assert "Nie znaleziono miasta" in result.output
        assert "Traceback" not in result.output


def test_cli_error_overpass_timeout():
    """Ścieżka 2: Błąd/timeout Overpass -> polski komunikat o serwerach bez tracebacku."""
    with patch("wulf_web_leader.pipeline.NominatimClient.geocode", new_callable=AsyncMock) as mock_geo:
        mock_geo.return_value = GeocodedLocation(lat=50.0, lon=20.0, display_name="Rzeszów", city="Rzeszów")
        with patch("wulf_web_leader.pipeline.OverpassClient.execute_query", new_callable=AsyncMock) as mock_op:
            mock_op.side_effect = RuntimeError("Wszystkie serwery Overpass API nie odpowiedziały z powodu przekroczenia limitu czasu (timeout).")

            result = runner.invoke(
                app,
                ["scan", "-c", "pl", "--miasto", "Rzeszów", "-v", "plumbers"],
            )
            assert result.exit_code == 1
            assert "Błąd skanowania:" in result.output
            assert "Overpass" in result.output
            assert "Traceback" not in result.output


def test_cli_zero_results():
    """Ścieżka 3: 0 firm spełniających kryteria -> polski komunikat i wskazówki dla użytkownika."""
    with patch("wulf_web_leader.pipeline.NominatimClient.geocode", new_callable=AsyncMock) as mock_geo:
        mock_geo.return_value = GeocodedLocation(lat=50.0, lon=20.0, display_name="Rzeszów", city="Rzeszów")
        with patch("wulf_web_leader.pipeline.OverpassClient.execute_query", new_callable=AsyncMock) as mock_op:
            mock_op.return_value = []

            result = runner.invoke(
                app,
                ["scan", "-c", "pl", "--miasto", "Rzeszów", "-v", "plumbers"],
            )
            assert result.exit_code == 0
            assert "Nie znaleziono firm" in result.output
            assert "Zwiększ promień" in result.output
            assert "Traceback" not in result.output
