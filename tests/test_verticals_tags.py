from pathlib import Path
from wulf_web_leader.verticals import load_all_verticals, find_vertical


def test_verticals_strict_tag_hygiene():
    """Verify strict OSM tag hygiene across all verticals: no shop=car, no shop=beauty."""
    verticals = load_all_verticals()
    assert len(verticals) >= 8

    for v_id, v in verticals.items():
        # 1. No vertical is allowed to have shop=beauty
        for tag in v.pl.osm + v.de.osm:
            assert tag != "shop=beauty", f"Vertical '{v_id}' contains forbidden tag 'shop=beauty'"

        # 2. auto_repair must never have broad car sales tags
        if v_id == "auto_repair":
            for tag in v.pl.osm + v.de.osm:
                assert tag != "shop=car", "auto_repair vertical contains forbidden tag 'shop=car'"
                assert not tag.startswith("shop=car;"), "auto_repair contains composite car sales tag"
            assert "shop=car_repair" in v.pl.osm
            assert "shop=car_repair" in v.de.osm

        # 3. hair must strictly be shop=hairdresser
        if v_id == "hair":
            assert v.pl.osm == ["shop=hairdresser"]
            assert v.de.osm == ["shop=hairdresser"]

        # 4. Labels and queries must be non-empty
        assert v.pl.label.strip()
        assert v.de.label.strip()
        assert v.pl.query.strip()
        assert v.de.query.strip()
