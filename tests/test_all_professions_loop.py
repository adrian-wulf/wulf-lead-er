import pytest
from wulf_web_leader.verticals import resolve_or_create_vertical
from wulf_web_leader.adapters.osm import build_overpass_query


# Over 120 common and specialized professions across Polish, German, and English
ALL_PROFESSIONS_TEST_SET = [
    # --- 1. IT, Informatyka & Technologie (PL / DE / EN) ---
    "informatyk",
    "informatyka",
    "informatycy",
    "usługi informatyczne",
    "pomoc informatyczna",
    "pogotowie informatyczne",
    "it",
    "IT",
    "programista",
    "programiści",
    "programowanie",
    "software house",
    "tworzenie stron",
    "tworzenie stron www",
    "strony www",
    "webdeveloper",
    "web development",
    "web design",
    "serwis komputerowy",
    "naprawa komputerów",
    "pogotowie komputerowe",
    "sklep komputerowy",
    "komputery",
    "agencja interaktywna",
    "agencja marketingowa",
    "pozycjonowanie",
    "seo",
    # German IT
    "informatiker",
    "it-dienstleister",
    "softwareentwicklung",
    "webdesign",
    "edv",
    "systemhaus",
    "computer-reparatur",
    # English IT
    "software developer",
    "computer repair",
    "web developer",

    # --- 2. Budownictwo, Remonty, Wykończenia ---
    "budowlanka",
    "firma budowlana",
    "usługi budowlane",
    "budownictwo",
    "remonty",
    "remont",
    "usługi remontowe",
    "wykończenia",
    "wykończenia wnętrz",
    "glazurnik",
    "glazurnicy",
    "płytkarz",
    "płytkarze",
    "układanie płytek",
    "brukarz",
    "brukarze",
    "kostka brukowa",
    "murarz",
    "tynkarz",
    "posadzki",
    "ocieplenia",
    "elewacje",
    "spawacz",
    "spawalnictwo",
    "tapicer",
    "usługi tapicerskie",
    # German & English Construction
    "bauunternehmen",
    "handwerker",
    "renovierung",
    "fliesenleger",
    "builder",
    "tiler",

    # --- 3. Instalacje, HVAC, Fotowoltaika ---
    "hydraulik",
    "hydraulicy",
    "usługi hydrauliczne",
    "instalacje sanitarne",
    "wod-kan",
    "elektryk",
    "elektrycy",
    "usługi elektryczne",
    "elektroinstalacje",
    "klimatyzacja",
    "klima",
    "wentylacja",
    "chłodnictwo",
    "pompy ciepła",
    "pompa ciepła",
    "fotowoltaika",
    "panele słoneczne",
    "solary",
    # German & English HVAC/Solar
    "plumber",
    "electrician",
    "klimaanlage",
    "photovoltaik",
    "air conditioning",

    # --- 4. Motoryzacja & Serwis Pojazdów ---
    "mechanik",
    "mechanicy",
    "mechanik samochodowy",
    "warsztat samochodowy",
    "autonaprawa",
    "wulkanizacja",
    "opony",
    "wymiana opon",
    "serwis opon",
    "myjnia",
    "myjnia samochodowa",
    "autodetailing",
    "detailing",
    "pomoc drogowa",
    "holowanie",
    "laweta",
    "stacja kontroli pojazdów",
    "przeglądy rejestracyjne",
    # German & English Auto
    "autowerkstatt",
    "kfz-werkstatt",
    "reifendienst",
    "abschleppdienst",
    "car repair",
    "car wash",

    # --- 5. Zdrowie, Gabinety, Lekarze, Stomatologia ---
    "lekarz",
    "lekarze",
    "przychodnia",
    "przychodnia lekarska",
    "gabinet lekarski",
    "centrum medyczne",
    "doktor",
    "pediatra",
    "ginekolog",
    "okulista",
    "dermatolog",
    "kardiolog",
    "ortopeda",
    "psycholog",
    "psychiatra",
    "psychoterapia",
    "stomatolog",
    "stomatolodzy",
    "dentysta",
    "dentyści",
    "ortodonta",
    "protetyk",
    "fizjoterapia",
    "fizjoterapeuta",
    "fizjoterapeuci",
    "rehabilitacja",
    "masaż",
    "masażysta",
    "salon masażu",
    # German & English Medical
    "arzt",
    "arztpraxis",
    "zahnarzt",
    "physiotherapie",
    "doctor",
    "dentist",

    # --- 6. Prawo, Finanse, Nieruchomości, Edukacja ---
    "prawnik",
    "prawnicy",
    "adwokat",
    "adwokaci",
    "radca prawny",
    "radcy prawni",
    "kancelaria prawna",
    "notariusz",
    "kancelaria notarialna",
    "księgowy",
    "księgowa",
    "księgowi",
    "księgowość",
    "biuro rachunkowe",
    "doradca podatkowy",
    "ubezpieczenia",
    "agent ubezpieczeniowy",
    "agencja ubezpieczeniowa",
    "nieruchomości",
    "biuro nieruchomości",
    "pośrednik nieruchomości",
    "szkoła jazdy",
    "nauka jazdy",
    "kurs prawa jazdy",
    "instruktor jazdy",
    "osk",
    # German & English Legal/Finance
    "rechtsanwalt",
    "steuerberater",
    "immobilienmakler",
    "versicherung",
    "fahrschule",
    "lawyer",
    "accountant",
    "real estate",

    # --- 7. Uroda, Fryzjerstwo, Kosmetyka ---
    "fryzjer",
    "fryzjerzy",
    "salon fryzjerski",
    "barber",
    "barbershop",
    "kosmetyczka",
    "kosmetyczki",
    "salon kosmetyczny",
    "paznokcie",
    "manicure",
    "pedicure",
    "makijaż",
    "tatuaż",
    "studio tatuażu",
    # German & English Beauty
    "friseur",
    "kosmetikstudio",
    "nagelstudio",
    "hairdresser",
    "beauty salon",

    # --- 8. Czystość, Przeprowadzki, Geodezja ---
    "sprzątanie",
    "firma sprzątająca",
    "usługi sprzątające",
    "mycie okien",
    "przeprowadzki",
    "transport mebli",
    "geodeta",
    "usługi geodezyjne",
    "kominiarz",
    "architekt",
    "biuro architektoniczne",
    "tłumacz",
    "biuro tłumaczeń",
    # German & English Cleaning/Moving
    "gebaeudereinigung",
    "umzuege",
    "cleaning",
    "movers",

    # --- 9. Rzemiosło tradycyjne ---
    "szklarz",
    "usługi szklarskie",
    "stolarz",
    "meble na wymiar",
    "malarz",
    "usługi malarskie",
    "dekarz",
    "dachy",
    "ślusarz",
    "dorabianie kluczy",
    "krawiec",
    "poprawki krawieckie",
    "szewc",
    "naprawa butów",
    "zegarmistrz",
    "naprawa zegarków",
    "jubiler",
    "złotnik",
    "fotograf",
    "studio fotograficzne",
    "drukarnia",
    "poligrafia",
    "ogrodnik",
    "usługi ogrodnicze",
    "kwiaciarnia",
    "florystyka",
    "optyk",
    "salon optyczny",
    "apteka",
    # German & English Crafts
    "glaser",
    "tischler",
    "schlosser",
    "schneider",
    "uhrmacher",
    "juwelier",
    "fotograf",
    "druckerei",
    "carpenter",
    "locksmith",
    "tailor",
    "watchmaker",
    "jeweler",

    # --- 10. Gastronomia, Żywność, Noclegi ---
    "restauracja",
    "pizzeria",
    "pizza",
    "kebab",
    "sushi",
    "burger",
    "kawiarnia",
    "kawiarnia rzemieślnicza",
    "cukiernia",
    "piekarnia",
    "pieczywo",
    "catering",
    "dieta pudełkowa",
    "hotel",
    "hostel",
    "pensjonat",
    "noclegi",
    # German & English Food/Hotels
    "baeckerei",
    "konditorei",
    "cafe",
    "bakery",
    "restaurant",

    # --- 11. Edukacja, Zwierzęta, Sport ---
    "weterynarz",
    "lecznica dla zwierząt",
    "groomer",
    "strzyżenie psów",
    "szkoła językowa",
    "nauka angielskiego",
    "przedszkole",
    "żłobek",
    "siłownia",
    "klub fitness",
    "trener personalny",
    "basen",
    "pływalnia",
    # German & English
    "tierarzt",
    "hundesalon",
    "sprachschule",
    "kindergarten",
    "fitnessstudio",
    "gym",
    "veterinary",
]


@pytest.mark.parametrize("profession", ALL_PROFESSIONS_TEST_SET)
def test_all_professions_loop_resolution(profession: str):
    """Loop through every searchable profession and verify resolution, OSM tags, PKD/WZ, and Overpass syntax."""
    # 1. Resolve for PL
    v_pl = resolve_or_create_vertical(profession, country="PL")
    assert v_pl is not None, f"Failed to resolve vertical for '{profession}'"
    assert v_pl.id.strip(), f"Vertical ID is empty for '{profession}'"
    assert len(v_pl.pl.osm) > 0, f"OSM tags empty for '{profession}'"

    # Strict check: NEVER generate fake OSM tags containing raw unmapped Polish words
    # e.g. "craft=informatyk" or "shop=informatyk"
    for tag in v_pl.pl.osm:
        assert "=" in tag, f"Invalid OSM tag format: {tag} in {profession}"
        key, val = tag.split("=", 1)
        assert key in [
            "craft", "shop", "amenity", "office", "healthcare",
            "healthcare:speciality", "leisure", "tourism", "catering", "cuisine", "trade"
        ], f"Unexpected OSM key '{key}' in tag '{tag}' for '{profession}'"

        # The value must be valid English/OSM standard, not the raw Polish noun with spaces or polish letters
        assert " " not in val, f"OSM tag value contains spaces: '{tag}' in '{profession}'"
        assert not any(c in val for c in "ąćęłńóśźż"), f"OSM tag value contains Polish diacritics: '{tag}' in '{profession}'"

    # PKD check: when populated, should follow standard PKD format (e.g. 62.01.Z or 43.33.Z)
    for pkd in v_pl.pl.pkd:
        assert len(pkd) >= 4, f"Suspicious PKD code '{pkd}' for '{profession}'"

    # 2. Resolve for DE
    v_de = resolve_or_create_vertical(profession, country="DE")
    assert v_de is not None
    assert len(v_de.de.osm) > 0

    # 3. Overpass QL Query Generation Test
    # Verify that build_overpass_query creates a valid Overpass QL string that can be parsed
    query_ql = build_overpass_query(
        lat=50.0647,
        lon=19.9450,
        radius_km=15.0,
        osm_tags=v_pl.pl.osm,
    )
    assert "[out:json]" in query_ql
    assert "around:15000,50.0647,19.945" in query_ql
    assert "node" in query_ql and "way" in query_ql and "relation" in query_ql
    assert "out center tags qt;" in query_ql
