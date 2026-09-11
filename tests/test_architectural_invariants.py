import re
from pathlib import Path
import tomllib


def test_no_server_dependencies_in_pyproject():
    """WF.2: W pyproject.toml brak ciężkich frameworków chmurowych, baz danych i brokerów."""
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    deps = data.get("project", {}).get("dependencies", [])
    forbidden_deps = [
        "flask",
        "django",
        "celery",
        "sqlalchemy",
        "pymongo",
        "redis",
        "boto3",
        "supabase",
        "firebase",
    ]
    for dep in deps:
        dep_name = re.split(r"[><=~]", dep)[0].strip().lower()
        assert dep_name not in forbidden_deps, f"Forbidden server dependency detected: {dep}"


def test_no_email_sending_or_smtp_modules_in_src():
    """WF.1: Brak modułów wysyłki maili (smtplib, aiosmtplib itp.) w kodzie źródłowym src/."""
    src_path = Path(__file__).resolve().parent.parent / "src"
    forbidden_terms = ["smtplib", "aiosmtplib", "sendgrid", "mailgun"]

    for py_file in src_path.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8").lower()
        for term in forbidden_terms:
            assert term not in content, f"Forbidden mail module '{term}' detected in {py_file}"


def test_no_google_maps_scraping_in_src():
    """WF.1: Brak adresów Google Maps scrapera w kodzie źródłowym src/."""
    src_path = Path(__file__).resolve().parent.parent / "src"
    for py_file in src_path.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8").lower()
        assert "google.com/maps" not in content, f"Google Maps URL found in {py_file}"


def test_frozen_to_eight_verticals():
    """WF.2: Zamrożenie na dokładnie 8 bazowych branżach."""
    verticals_dir = Path(__file__).resolve().parent.parent / "verticals"
    yaml_files = list(verticals_dir.glob("*.yaml"))
    assert len(yaml_files) == 8, f"Expected 8 verticals, found {len(yaml_files)}: {[f.name for f in yaml_files]}"
