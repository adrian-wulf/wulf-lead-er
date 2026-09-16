import pytest
from wulf_web_leader.verticals import (
    load_all_verticals,
    find_vertical,
    create_custom_vertical,
    resolve_or_create_vertical,
    _strip_diacritics,
)


def test_strip_diacritics():
    assert _strip_diacritics("ślusarz") == "slusarz"
    assert _strip_diacritics("kawiarnia") == "kawiarnia"
    assert _strip_diacritics("tłumacz") == "tlumacz"
    assert _strip_diacritics("Księgowa") == "Ksiegowa"


def test_resolve_existing_verticals_by_id_and_alias():
    # ID
    v1 = resolve_or_create_vertical("plumbers", country="PL")
    assert v1.id == "plumbers"

    # Polish alias
    v_pl = resolve_or_create_vertical("hydraulik", country="PL")
    assert v_pl.id == "plumbers"

    # German alias
    v_de = resolve_or_create_vertical("klempner", country="DE")
    assert v_de.id == "plumbers"


def test_resolve_known_custom_trades():
    # Szklarz
    v_szk = resolve_or_create_vertical("szklarz", country="PL")
    assert "craft=glazier" in v_szk.pl.osm
    assert "shop=glaziery" in v_szk.pl.osm
    assert "43.34.Z" in v_szk.pl.pkd
    assert "Glaser" in v_szk.de.label

    # Stolarz
    v_sto = resolve_or_create_vertical("stolarz", country="PL")
    assert any("carpenter" in tag for tag in v_sto.pl.osm)

    # Malarz
    v_mal = resolve_or_create_vertical("malarz", country="PL")
    assert "craft=painter" in v_mal.pl.osm

    # Ślusarz with diacritics
    v_slu = resolve_or_create_vertical("ślusarz", country="PL")
    assert "craft=locksmith" in v_slu.pl.osm

    # Slusarz without diacritics
    v_slu_ascii = resolve_or_create_vertical("slusarz", country="PL")
    assert "craft=locksmith" in v_slu_ascii.pl.osm

    # Fotograf
    v_foto = resolve_or_create_vertical("fotograf", country="PL")
    assert "craft=photographer" in v_foto.pl.osm

    # Kawiarnia
    v_kaw = resolve_or_create_vertical("kawiarnia", country="PL")
    assert "amenity=cafe" in v_kaw.pl.osm

    # Klimatyzacja / HVAC
    v_hvac = resolve_or_create_vertical("klimatyzacja", country="PL")
    assert "craft=hvac" in v_hvac.pl.osm or "craft=air_conditioning" in v_hvac.pl.osm

    # Stomatolog / Dentysta
    v_dent = resolve_or_create_vertical("stomatolog", country="PL")
    assert "amenity=dentist" in v_dent.pl.osm
    assert "86.23.Z" in v_dent.pl.pkd

    # Prawnik
    v_prawnik = resolve_or_create_vertical("prawnik", country="PL")
    assert "office=lawyer" in v_prawnik.pl.osm

    # Księgowy
    v_ksiegowy = resolve_or_create_vertical("księgowy", country="PL")
    assert "office=accountant" in v_ksiegowy.pl.osm


def test_resolve_direct_osm_tag():
    # Direct craft tag
    v_direct = resolve_or_create_vertical("craft=glazier", country="PL")
    assert v_direct.pl.osm == ["craft=glazier"]
    assert v_direct.de.osm == ["craft=glazier"]
    assert "Glazier" in v_direct.name

    # Direct shop tag
    v_shop = resolve_or_create_vertical("shop=cheese", country="PL")
    assert v_shop.pl.osm == ["shop=cheese"]
    assert "Cheese" in v_shop.name


def test_resolve_arbitrary_unseen_trade():
    # Completely arbitrary trade, e.g. "browar" or "sauna"
    v_custom = resolve_or_create_vertical("sauna", country="PL")
    assert v_custom.id == "custom_sauna"
    assert "craft=sauna" in v_custom.pl.osm
    assert "shop=sauna" in v_custom.pl.osm
    assert "amenity=sauna" in v_custom.pl.osm
    assert "office=sauna" in v_custom.pl.osm
    assert v_custom.pl.query == "sauna"


def test_blank_query_fallback():
    # Empty query should fall back to plumbers
    v_empty = resolve_or_create_vertical("", country="PL")
    assert v_empty.id == "plumbers"

    v_spaces = resolve_or_create_vertical("   ", country="PL")
    assert v_spaces.id == "plumbers"


def test_find_vertical_preserves_none_for_unknown():
    # Strict check: find_vertical returns None when not in curated yaml
    assert find_vertical("space_rocket") is None
    assert find_vertical("szklarz") is None
