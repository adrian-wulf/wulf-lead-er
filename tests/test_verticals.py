import pytest
from brakstrony.verticals import load_all_verticals, find_vertical


def test_load_all_verticals():
    verticals = load_all_verticals()
    # Must ship at least 8 required trades
    expected_ids = {
        "plumbers",
        "electricians",
        "hair",
        "auto_repair",
        "restaurant",
        "bakery",
        "veterinary",
        "gym",
    }
    for vid in expected_ids:
        assert vid in verticals, f"Vertical {vid} missing from verticals/"
        v = verticals[vid]
        assert len(v.pl.osm) > 0
        assert len(v.de.osm) > 0
        assert v.pl.query
        assert v.de.query


def test_find_vertical_by_id_and_alias():
    verticals = load_all_verticals()

    # Find by ID
    v1 = find_vertical("plumbers", verticals)
    assert v1 is not None
    assert v1.id == "plumbers"

    # Find by Polish alias
    v_pl = find_vertical("hydraulik", verticals)
    assert v_pl is not None
    assert v_pl.id == "plumbers"

    # Find by German alias
    v_de = find_vertical("klempner", verticals)
    assert v_de is not None
    assert v_de.id == "plumbers"

    # Find hair by German alias
    v_friseur = find_vertical("friseur", verticals)
    assert v_friseur is not None
    assert v_friseur.id == "hair"

    # Unknown
    assert find_vertical("space_rocket", verticals) is None
