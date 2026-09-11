from pathlib import Path
from typer.testing import CliRunner
from wulf_web_leader.cli import app
from wulf_web_leader.export.demo import generate_demo_html

runner = CliRunner()


def test_generate_demo_html_function(tmp_path: Path):
    out_file = tmp_path / "index.html"
    generate_demo_html(
        name="Hydraulik Jan Kowalski",
        industry="Usługi hydrauliczne",
        phone="+48 17 850 00 00",
        city="Rzeszów",
        output_path=out_file,
    )
    assert out_file.is_file()
    html = out_file.read_text(encoding="utf-8")
    assert "Hydraulik Jan Kowalski" in html
    assert "Usługi hydrauliczne" in html
    assert "+48 17 850 00 00" in html
    assert "tel:+48 17 850 00 00" in html or "tel:+48178500000" in html
    assert "viewport" in html


def test_wulf_demo_template_cli(tmp_path: Path):
    out_file = tmp_path / "demo.html"
    result = runner.invoke(
        app,
        [
            "demo-template",
            "--name", "Auto Serwis Marfin",
            "--industry", "Mechanika pojazdowa",
            "--phone", "+48 600 666 175",
            "--city", "Rzeszów",
            "--out", str(out_file),
        ],
    )
    assert result.exit_code == 0
    assert out_file.is_file()
    html = out_file.read_text(encoding="utf-8")
    assert "Auto Serwis Marfin" in html
    assert "Mechanika pojazdowa" in html
    assert "Zadzwoń teraz" in html


def test_wulf_demo_template_cli_default_index_html(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        [
            "demo-template",
            "--name", "Hydraulik Express",
            "--phone", "+48 17 800 00 00",
        ],
    )
    assert result.exit_code == 0
    default_file = tmp_path / "index.html"
    assert default_file.is_file()
    html = default_file.read_text(encoding="utf-8")
    assert "Hydraulik Express" in html
    assert "+48 17 800 00 00" in html
