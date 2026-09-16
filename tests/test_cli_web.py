from unittest.mock import patch
from typer.testing import CliRunner

from wulf_web_leader.cli import app

runner = CliRunner()


def test_cli_web_help():
    result = runner.invoke(app, ["web", "--help"])
    assert result.exit_code == 0
    assert "Uruchom interaktywny pulpit Web GUI" in result.output
    assert "--host" in result.output
    assert "--port" in result.output
    assert "--open-browser" in result.output


def test_cli_web_invokes_uvicorn():
    with patch("uvicorn.run") as mock_uvicorn_run:
        result = runner.invoke(
            app,
            ["web", "--host", "0.0.0.0", "--port", "9090", "--no-browser"],
        )
        assert result.exit_code == 0
        assert "Wulf Web Leader — Uruchamianie Web GUI..." in result.output
        mock_uvicorn_run.assert_called_once()
        args, kwargs = mock_uvicorn_run.call_args
        assert kwargs["host"] == "0.0.0.0"
        assert kwargs["port"] == 9090


def test_cli_web_port_conflict_fallback():
    with patch("uvicorn.run") as mock_uvicorn_run, \
         patch("socket.socket") as mock_socket:
        # First bind fails (port in use), second succeeds
        instance = mock_socket.return_value.__enter__.return_value
        instance.bind.side_effect = [OSError("Address in use"), None]

        result = runner.invoke(
            app,
            ["web", "--host", "127.0.0.1", "--port", "8000", "--no-browser"],
        )
        assert result.exit_code == 0
        assert "Port 8000 jest zajęty" in result.output
        mock_uvicorn_run.assert_called_once()
        args, kwargs = mock_uvicorn_run.call_args
        assert kwargs["port"] == 8001
