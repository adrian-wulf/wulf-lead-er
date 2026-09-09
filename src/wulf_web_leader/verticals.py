from pathlib import Path
import yaml
from wulf_web_leader.models import VerticalDefinition


def get_verticals_dir() -> Path:
    """Return path to verticals directory."""
    # First check relative to repo root, then relative to package
    current = Path(__file__).resolve().parent
    candidates = [
        current.parent.parent / "verticals",
        current / "verticals",
        Path.cwd() / "verticals",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    # Fallback to repo root candidate
    return current.parent.parent / "verticals"


def load_vertical(file_path: Path) -> VerticalDefinition:
    """Load a single vertical YAML file."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return VerticalDefinition.model_validate(data)


def load_all_verticals(verticals_dir: Path | None = None) -> dict[str, VerticalDefinition]:
    """Load all verticals keyed by their primary ID."""
    v_dir = verticals_dir or get_verticals_dir()
    verticals: dict[str, VerticalDefinition] = {}
    if not v_dir.exists():
        return verticals

    for yaml_file in sorted(v_dir.glob("*.yaml")):
        try:
            v_def = load_vertical(yaml_file)
            verticals[v_def.id] = v_def
        except Exception as e:
            # Skip or log error in loading individual vertical
            continue
    return verticals


def find_vertical(query: str, verticals: dict[str, VerticalDefinition] | None = None) -> VerticalDefinition | None:
    """Find a vertical by ID or PL/DE alias (case-insensitive)."""
    if verticals is None:
        verticals = load_all_verticals()

    normalized = query.strip().lower()
    
    # 1. Exact ID match
    if normalized in verticals:
        return verticals[normalized]

    # 2. Check aliases and query keywords
    for v in verticals.values():
        if v.name.lower() == normalized:
            return v
        if normalized in [a.lower() for a in v.aliases.pl]:
            return v
        if normalized in [a.lower() for a in v.aliases.de]:
            return v
        if normalized == v.pl.query.lower():
            return v
        if normalized == v.de.query.lower():
            return v

    return None
