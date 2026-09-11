import re
import unicodedata
from pathlib import Path
from typing import Any
import yaml
from wulf_web_leader.models import VerticalDefinition, CountryVerticalConfig, VerticalAliases


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


def _strip_diacritics(text: str) -> str:
    """Strip Polish and other European diacritics for resilient keyword normalization."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).replace("ł", "l").replace("Ł", "L")


# Comprehensive dictionary of trade synonyms, professions, and their corresponding OSM tags
KNOWN_CUSTOM_TRADES: dict[str, dict[str, Any]] = {
    # Szklarstwo
    "szklarz": {
        "label_pl": "Szklarz / Usługi szklarskie",
        "label_de": "Glaser / Glaserei",
        "osm": ["craft=glazier", "shop=glaziery"],
        "pkd": ["43.34.Z"],
        "wz": ["43.34"],
    },
    "glazier": {
        "label_pl": "Szklarz / Usługi szklarskie",
        "label_de": "Glaser / Glaserei",
        "osm": ["craft=glazier", "shop=glaziery"],
        "pkd": ["43.34.Z"],
        "wz": ["43.34"],
    },
    "glaser": {
        "label_pl": "Szklarz / Usługi szklarskie",
        "label_de": "Glaser / Glaserei",
        "osm": ["craft=glazier", "shop=glaziery"],
        "pkd": ["43.34.Z"],
        "wz": ["43.34"],
    },
    # Stolarstwo / Meble
    "stolarz": {
        "label_pl": "Stolarz / Usługi stolarskie & Meble",
        "label_de": "Tischler / Schreiner / Möbelbau",
        "osm": ["craft=carpenter", "craft=joiner", "craft=furniture"],
        "pkd": ["16.23.Z", "31.09.Z"],
        "wz": ["16.23", "31.09"],
    },
    "carpenter": {
        "label_pl": "Stolarz / Usługi stolarskie",
        "label_de": "Tischler / Schreiner",
        "osm": ["craft=carpenter", "craft=joiner"],
        "pkd": ["16.23.Z"],
        "wz": ["16.23"],
    },
    "schreiner": {
        "label_pl": "Stolarz / Usługi stolarskie",
        "label_de": "Tischler / Schreiner",
        "osm": ["craft=carpenter", "craft=joiner"],
        "pkd": ["16.23.Z"],
        "wz": ["16.23"],
    },
    "tischler": {
        "label_pl": "Stolarz / Usługi stolarskie",
        "label_de": "Tischler / Schreiner",
        "osm": ["craft=carpenter", "craft=joiner"],
        "pkd": ["16.23.Z"],
        "wz": ["16.23"],
    },
    # Malarstwo
    "malarz": {
        "label_pl": "Malarz / Usługi malarskie",
        "label_de": "Malerbetrieb / Lackierer",
        "osm": ["craft=painter"],
        "pkd": ["43.34.Z"],
        "wz": ["43.34"],
    },
    "maler": {
        "label_pl": "Malarz / Usługi malarskie",
        "label_de": "Malerbetrieb / Lackierer",
        "osm": ["craft=painter"],
        "pkd": ["43.34.Z"],
        "wz": ["43.34"],
    },
    "painter": {
        "label_pl": "Malarz / Usługi malarskie",
        "label_de": "Malerbetrieb / Lackierer",
        "osm": ["craft=painter"],
        "pkd": ["43.34.Z"],
        "wz": ["43.34"],
    },
    # Dekarstwo
    "dekarz": {
        "label_pl": "Dekarz / Usługi dekarskie & Dachy",
        "label_de": "Dachdecker / Bedachungen",
        "osm": ["craft=roofer"],
        "pkd": ["43.91.Z"],
        "wz": ["43.91"],
    },
    "dachdecker": {
        "label_pl": "Dekarz / Usługi dekarskie & Dachy",
        "label_de": "Dachdecker / Bedachungen",
        "osm": ["craft=roofer"],
        "pkd": ["43.91.Z"],
        "wz": ["43.91"],
    },
    "roofer": {
        "label_pl": "Dekarz / Usługi dekarskie & Dachy",
        "label_de": "Dachdecker / Bedachungen",
        "osm": ["craft=roofer"],
        "pkd": ["43.91.Z"],
        "wz": ["43.91"],
    },
    # Fotografia
    "fotograf": {
        "label_pl": "Fotograf / Studio fotograficzne",
        "label_de": "Fotograf / Fotostudio",
        "osm": ["craft=photographer", "shop=photo"],
        "pkd": ["74.20.Z"],
        "wz": ["74.20"],
    },
    "photographer": {
        "label_pl": "Fotograf / Studio fotograficzne",
        "label_de": "Fotograf / Fotostudio",
        "osm": ["craft=photographer", "shop=photo"],
        "pkd": ["74.20.Z"],
        "wz": ["74.20"],
    },
    # Kwiaciarnie
    "kwiaciarnia": {
        "label_pl": "Kwiaciarnia / Florystyka",
        "label_de": "Blumengeschäft / Floristik",
        "osm": ["shop=florist"],
        "pkd": ["47.76.Z"],
        "wz": ["47.76"],
    },
    "florist": {
        "label_pl": "Kwiaciarnia / Florystyka",
        "label_de": "Blumengeschäft / Floristik",
        "osm": ["shop=florist"],
        "pkd": ["47.76.Z"],
        "wz": ["47.76"],
    },
    # Cukiernie & Kawiarnie
    "cukiernia": {
        "label_pl": "Cukiernia / Wyroby cukiernicze",
        "label_de": "Konditorei / Patisserie",
        "osm": ["shop=confectionery", "shop=pastry"],
        "pkd": ["10.71.Z"],
        "wz": ["10.71"],
    },
    "kawiarnia": {
        "label_pl": "Kawiarnia / Kawiarnia rzemieślnicza",
        "label_de": "Café / Kaffeerösterei",
        "osm": ["amenity=cafe"],
        "pkd": ["56.30.Z"],
        "wz": ["56.30"],
    },
    "cafe": {
        "label_pl": "Kawiarnia",
        "label_de": "Café",
        "osm": ["amenity=cafe"],
        "pkd": ["56.30.Z"],
        "wz": ["56.30"],
    },
    # Hotele & Noclegi
    "hotel": {
        "label_pl": "Hotel / Obiekt noclegowy",
        "label_de": "Hotel / Pension / Unterkunft",
        "osm": ["tourism=hotel", "tourism=guest_house", "tourism=motel"],
        "pkd": ["55.10.Z"],
        "wz": ["55.10"],
    },
    # Ogrodnictwo
    "ogrodnik": {
        "label_pl": "Ogrodnik / Usługi ogrodnicze & Tereny zielone",
        "label_de": "Gartenbau / Landschaftsbau",
        "osm": ["craft=gardener", "shop=garden_centre"],
        "pkd": ["81.30.Z"],
        "wz": ["81.30"],
    },
    "gardener": {
        "label_pl": "Ogrodnik / Usługi ogrodnicze",
        "label_de": "Gartenbau",
        "osm": ["craft=gardener", "shop=garden_centre"],
        "pkd": ["81.30.Z"],
        "wz": ["81.30"],
    },
    # Architektura & Projektowanie
    "architekt": {
        "label_pl": "Architekt / Biuro projektowe",
        "label_de": "Architekt / Architekturbüro",
        "osm": ["office=architect"],
        "pkd": ["71.11.Z"],
        "wz": ["71.11"],
    },
    "architect": {
        "label_pl": "Architekt / Biuro projektowe",
        "label_de": "Architekt / Architekturbüro",
        "osm": ["office=architect"],
        "pkd": ["71.11.Z"],
        "wz": ["71.11"],
    },
    # Optycy
    "optyk": {
        "label_pl": "Optyk / Salon optyczny",
        "label_de": "Optiker / Augenoptik",
        "osm": ["shop=optician"],
        "pkd": ["47.78.Z"],
        "wz": ["47.78"],
    },
    "optician": {
        "label_pl": "Optyk / Salon optyczny",
        "label_de": "Optiker / Augenoptik",
        "osm": ["shop=optician"],
        "pkd": ["47.78.Z"],
        "wz": ["47.78"],
    },
    # Fizjoterapia & Rehabilitacja
    "fizjoterapia": {
        "label_pl": "Fizjoterapia / Gabinet rehabilitacji",
        "label_de": "Physiotherapie / Physiotherapeut",
        "osm": ["amenity=physiotherapist", "healthcare=physiotherapist"],
        "pkd": ["86.90.A"],
        "wz": ["86.90"],
    },
    "rehabilitacja": {
        "label_pl": "Rehabilitacja / Fizjoterapia",
        "label_de": "Physiotherapie / Rehabilitation",
        "osm": ["amenity=physiotherapist", "healthcare=physiotherapist"],
        "pkd": ["86.90.A"],
        "wz": ["86.90"],
    },
    # Ślusarstwo
    "slusarz": {
        "label_pl": "Ślusarz / Usługi ślusarskie",
        "label_de": "Schlosser / Schlosserei",
        "osm": ["craft=locksmith"],
        "pkd": ["25.62.Z"],
        "wz": ["25.62"],
    },
    "locksmith": {
        "label_pl": "Ślusarz / Usługi ślusarskie",
        "label_de": "Schlosser / Schlosserei",
        "osm": ["craft=locksmith"],
        "pkd": ["25.62.Z"],
        "wz": ["25.62"],
    },
    # Notariusz & Prawo
    "notariusz": {
        "label_pl": "Kancelaria Notarialna / Notariusz",
        "label_de": "Notar / Notariat",
        "osm": ["office=notary"],
        "pkd": ["69.10.Z"],
        "wz": ["69.10"],
    },
    "notary": {
        "label_pl": "Kancelaria Notarialna / Notariusz",
        "label_de": "Notar / Notariat",
        "osm": ["office=notary"],
        "pkd": ["69.10.Z"],
        "wz": ["69.10"],
    },
    # Tłumaczenia
    "tlumacz": {
        "label_pl": "Tłumacz / Biuro tłumaczeń",
        "label_de": "Übersetzer / Übersetzungsbüro",
        "osm": ["office=translator"],
        "pkd": ["74.30.Z"],
        "wz": ["74.30"],
    },
    "translator": {
        "label_pl": "Tłumacz / Biuro tłumaczeń",
        "label_de": "Übersetzer / Übersetzungsbüro",
        "osm": ["office=translator"],
        "pkd": ["74.30.Z"],
        "wz": ["74.30"],
    },
    # HVAC & Klimatyzacja
    "klimatyzacja": {
        "label_pl": "Klimatyzacja & Wentylacja / HVAC",
        "label_de": "Klima & Lüftungstechnik / HVAC",
        "osm": ["craft=hvac", "craft=air_conditioning"],
        "pkd": ["43.22.Z"],
        "wz": ["43.22"],
    },
    "hvac": {
        "label_pl": "Klimatyzacja & Wentylacja / HVAC",
        "label_de": "Klima & Lüftungstechnik / HVAC",
        "osm": ["craft=hvac", "craft=air_conditioning"],
        "pkd": ["43.22.Z"],
        "wz": ["43.22"],
    },
    # Fotowoltaika
    "fotowoltaika": {
        "label_pl": "Fotowoltaika & Energia Słoneczna",
        "label_de": "Photovoltaik & Solaranlagen",
        "osm": ["craft=electrician", "craft=photovoltaic"],
        "pkd": ["43.21.Z"],
        "wz": ["43.21"],
    },
    "solar": {
        "label_pl": "Fotowoltaika & Energia Słoneczna",
        "label_de": "Photovoltaik & Solaranlagen",
        "osm": ["craft=electrician", "craft=photovoltaic"],
        "pkd": ["43.21.Z"],
        "wz": ["43.21"],
    },
    # Sprzątanie
    "sprzatanie": {
        "label_pl": "Firma sprzątająca / Usługi czystości",
        "label_de": "Gebäudereinigung / Reinigungsfirma",
        "osm": ["craft=cleaning", "office=cleaning"],
        "pkd": ["81.21.Z"],
        "wz": ["81.21"],
    },
    "cleaning": {
        "label_pl": "Firma sprzątająca / Usługi czystości",
        "label_de": "Gebäudereinigung / Reinigungsfirma",
        "osm": ["craft=cleaning", "office=cleaning"],
        "pkd": ["81.21.Z"],
        "wz": ["81.21"],
    },
    # Przeprowadzki
    "przeprowadzki": {
        "label_pl": "Przeprowadzki & Transport",
        "label_de": "Umzüge & Transport",
        "osm": ["craft=moving", "office=moving"],
        "pkd": ["49.42.Z"],
        "wz": ["49.42"],
    },
    "moving": {
        "label_pl": "Przeprowadzki & Transport",
        "label_de": "Umzüge & Transport",
        "osm": ["craft=moving", "office=moving"],
        "pkd": ["49.42.Z"],
        "wz": ["49.42"],
    },
    # Geodezja
    "geodeta": {
        "label_pl": "Geodeta / Usługi geodezyjne",
        "label_de": "Vermessungsbüro / Geodät",
        "osm": ["office=surveyor"],
        "pkd": ["71.12.Z"],
        "wz": ["71.12"],
    },
    # Kominiarz
    "kominiarz": {
        "label_pl": "Kominiarz / Usługi kominiarskie",
        "label_de": "Schornsteinfeger",
        "osm": ["craft=chimney_sweeper"],
        "pkd": ["81.22.Z"],
        "wz": ["81.22"],
    },
    # Krawiectwo
    "krawiec": {
        "label_pl": "Krawiec / Usługi krawieckie & Poprawki",
        "label_de": "Schneider / Schneiderei",
        "osm": ["craft=tailor"],
        "pkd": ["14.13.Z", "95.29.Z"],
        "wz": ["14.13", "95.29"],
    },
    # Szewc
    "szewc": {
        "label_pl": "Szewc / Naprawa obuwia",
        "label_de": "Schuhmacher / Schuhreparatur",
        "osm": ["craft=shoemaker"],
        "pkd": ["95.23.Z"],
        "wz": ["95.23"],
    },
    # Drukarnia
    "drukarnia": {
        "label_pl": "Drukarnia / Usługi poligraficzne",
        "label_de": "Druckerei / Druckstudio",
        "osm": ["craft=printer"],
        "pkd": ["18.12.Z"],
        "wz": ["18.12"],
    },
    # Tatuaż
    "tatuaz": {
        "label_pl": "Studio Tatuażu / Piercing",
        "label_de": "Tattoo-Studio / Piercing",
        "osm": ["shop=tattoo"],
        "pkd": ["96.09.Z"],
        "wz": ["96.09"],
    },
    # Kosmetyka
    "kosmetyczka": {
        "label_pl": "Salon Kosmetyczny / Kosmetologia",
        "label_de": "Kosmetikstudio / Beauty",
        "osm": ["shop=beauty"],
        "pkd": ["96.02.Z"],
        "wz": ["96.02"],
    },
    # Apteki
    "apteka": {
        "label_pl": "Apteka",
        "label_de": "Apotheke",
        "osm": ["amenity=pharmacy"],
        "pkd": ["47.73.Z"],
        "wz": ["47.73"],
    },
    # Zegarmistrz
    "zegarmistrz": {
        "label_pl": "Zegarmistrz / Naprawa zegarków",
        "label_de": "Uhrmacher / Uhrenservice",
        "osm": ["craft=watchmaker", "shop=watch"],
        "pkd": ["95.25.Z"],
        "wz": ["95.25"],
    },
    # Stomatologia / Dentyści
    "stomatolog": {
        "label_pl": "Stomatolog / Gabinet stomatologiczny",
        "label_de": "Zahnarzt / Zahnarztpraxis",
        "osm": ["amenity=dentist", "healthcare=dentist"],
        "pkd": ["86.23.Z"],
        "wz": ["86.23"],
    },
    "dentysta": {
        "label_pl": "Stomatolog / Dentysta",
        "label_de": "Zahnarzt / Zahnarztpraxis",
        "osm": ["amenity=dentist", "healthcare=dentist"],
        "pkd": ["86.23.Z"],
        "wz": ["86.23"],
    },
    "dentist": {
        "label_pl": "Stomatolog / Gabinet stomatologiczny",
        "label_de": "Zahnarzt / Zahnarztpraxis",
        "osm": ["amenity=dentist", "healthcare=dentist"],
        "pkd": ["86.23.Z"],
        "wz": ["86.23"],
    },
    "dentists": {
        "label_pl": "Stomatolodzy / Gabinety stomatologiczne",
        "label_de": "Zahnärzte / Zahnarztpraxen",
        "osm": ["amenity=dentist", "healthcare=dentist"],
        "pkd": ["86.23.Z"],
        "wz": ["86.23"],
    },
    "zahnarzt": {
        "label_pl": "Stomatolog / Gabinet stomatologiczny",
        "label_de": "Zahnarzt / Zahnarztpraxis",
        "osm": ["amenity=dentist", "healthcare=dentist"],
        "pkd": ["86.23.Z"],
        "wz": ["86.23"],
    },
    # Prawnicy & Kancelarie
    "prawnik": {
        "label_pl": "Adwokat / Kancelaria prawna",
        "label_de": "Rechtsanwalt / Kanzlei",
        "osm": ["office=lawyer"],
        "pkd": ["69.10.Z"],
        "wz": ["69.10"],
    },
    "adwokat": {
        "label_pl": "Adwokat / Kancelaria adwokacka",
        "label_de": "Rechtsanwalt / Kanzlei",
        "osm": ["office=lawyer"],
        "pkd": ["69.10.Z"],
        "wz": ["69.10"],
    },
    "lawyer": {
        "label_pl": "Adwokat / Kancelaria prawna",
        "label_de": "Rechtsanwalt / Kanzlei",
        "osm": ["office=lawyer"],
        "pkd": ["69.10.Z"],
        "wz": ["69.10"],
    },
    "lawyers": {
        "label_pl": "Adwokaci & Kancelarie prawne",
        "label_de": "Rechtsanwälte & Kanzleien",
        "osm": ["office=lawyer"],
        "pkd": ["69.10.Z"],
        "wz": ["69.10"],
    },
    "rechtsanwalt": {
        "label_pl": "Adwokat / Kancelaria prawna",
        "label_de": "Rechtsanwalt / Kanzlei",
        "osm": ["office=lawyer"],
        "pkd": ["69.10.Z"],
        "wz": ["69.10"],
    },
    # Księgowość & Rachunkowość
    "ksiegowy": {
        "label_pl": "Biuro rachunkowe / Księgowość",
        "label_de": "Steuerberater / Buchhaltung",
        "osm": ["office=accountant", "office=tax_advisor"],
        "pkd": ["69.20.Z"],
        "wz": ["69.20"],
    },
    "ksiegowosc": {
        "label_pl": "Biuro rachunkowe / Księgowość",
        "label_de": "Steuerberater / Buchhaltung",
        "osm": ["office=accountant", "office=tax_advisor"],
        "pkd": ["69.20.Z"],
        "wz": ["69.20"],
    },
    "accountant": {
        "label_pl": "Biuro rachunkowe / Księgowość",
        "label_de": "Steuerberater / Buchhaltung",
        "osm": ["office=accountant", "office=tax_advisor"],
        "pkd": ["69.20.Z"],
        "wz": ["69.20"],
    },
    "accountants": {
        "label_pl": "Biura rachunkowe & Księgowość",
        "label_de": "Steuerberater & Buchhaltung",
        "osm": ["office=accountant", "office=tax_advisor"],
        "pkd": ["69.20.Z"],
        "wz": ["69.20"],
    },
    "steuerberater": {
        "label_pl": "Biuro rachunkowe / Doradca podatkowy",
        "label_de": "Steuerberater / Buchhaltung",
        "osm": ["office=accountant", "office=tax_advisor"],
        "pkd": ["69.20.Z"],
        "wz": ["69.20"],
    },
    # Mechanika & Warsztaty (synonimy do auto_repair)
    "car_repair": {
        "label_pl": "Warsztat samochodowy / Mechanika",
        "label_de": "KFZ-Werkstatt / Autoreparatur",
        "osm": ["shop=car_repair", "craft=car_repair"],
        "pkd": ["45.20.Z"],
        "wz": ["45.20"],
    },
    "warsztat": {
        "label_pl": "Warsztat samochodowy / Mechanika pojazdowa",
        "label_de": "KFZ-Werkstatt / Autoreparatur",
        "osm": ["shop=car_repair", "craft=car_repair"],
        "pkd": ["45.20.Z"],
        "wz": ["45.20"],
    },
    # Fryzjerstwo (synonimy)
    "hairdressers": {
        "label_pl": "Salon fryzjerski / Barber",
        "label_de": "Friseursalon / Barber",
        "osm": ["shop=hairdresser"],
        "pkd": ["96.02.Z"],
        "wz": ["96.02"],
    },
    # Restauracje (synonimy)
    "restaurants": {
        "label_pl": "Restauracje & Lokale gastronomiczne",
        "label_de": "Restaurants & Gastronomie",
        "osm": ["amenity=restaurant"],
        "pkd": ["56.10.A"],
        "wz": ["56.10"],
    },
}


def create_custom_vertical(query: str, country: str = "PL") -> VerticalDefinition:
    """Dynamically construct a VerticalDefinition for an arbitrary user query or direct OSM tag."""
    norm = query.strip().lower()

    # 1. Direct OSM tag (e.g. "craft=glazier" or "amenity=dentist")
    if "=" in norm:
        key, val = [x.strip() for x in norm.split("=", 1)]
        clean_val = re.sub(r"[^a-zA-Z0-9_]", "", val.replace(" ", "_"))
        v_id = f"custom_{key}_{clean_val}"
        name = val.replace("_", " ").title()
        osm_tags = [f"{key}={val}"]
        label_pl = f"{name} ({key}={val})"
        label_de = f"{name} ({key}={val})"
        return VerticalDefinition(
            id=v_id,
            name=name,
            aliases=VerticalAliases(pl=[query], de=[query]),
            pl=CountryVerticalConfig(query=val, label=label_pl, osm=osm_tags),
            de=CountryVerticalConfig(query=val, label=label_de, osm=osm_tags),
        )

    # 2. Check known dictionary of trades (both direct and without diacritics)
    trade = KNOWN_CUSTOM_TRADES.get(norm)
    if not trade:
        ascii_key = _strip_diacritics(norm)
        trade = KNOWN_CUSTOM_TRADES.get(ascii_key)

    if trade:
        clean_slug = re.sub(r"[^a-zA-Z0-9_]", "", _strip_diacritics(norm).replace(" ", "_"))
        v_id = f"custom_{clean_slug}"
        name = norm.title()
        return VerticalDefinition(
            id=v_id,
            name=name,
            aliases=VerticalAliases(pl=[norm], de=[norm]),
            pl=CountryVerticalConfig(
                query=norm,
                label=trade["label_pl"],
                pkd=trade.get("pkd", []),
                osm=trade["osm"],
            ),
            de=CountryVerticalConfig(
                query=norm,
                label=trade["label_de"],
                wz=trade.get("wz", []),
                osm=trade["osm"],
            ),
        )

    # 3. Fallback for completely arbitrary custom trade or keyword (e.g. "sauna", "browar")
    clean_slug = re.sub(r"[^a-zA-Z0-9_]", "", _strip_diacritics(norm).replace(" ", "_")) or "trade"
    v_id = f"custom_{clean_slug}"
    name = norm.title()
    osm_tags = [
        f"craft={clean_slug}",
        f"shop={clean_slug}",
        f"amenity={clean_slug}",
        f"office={clean_slug}",
    ]
    return VerticalDefinition(
        id=v_id,
        name=name,
        aliases=VerticalAliases(pl=[norm], de=[norm]),
        pl=CountryVerticalConfig(query=norm, label=f"Branża: {name}", osm=osm_tags),
        de=CountryVerticalConfig(query=norm, label=f"Branche: {name}", osm=osm_tags),
    )


def resolve_or_create_vertical(query: str, country: str = "PL") -> VerticalDefinition:
    """Resolve vertical from predefined YAML files, or dynamically generate one for custom input."""
    if not query or not query.strip():
        # Fallback to plumbers if blank
        return find_vertical("plumbers") or create_custom_vertical("plumbers", country)

    existing = find_vertical(query)
    if existing:
        return existing

    return create_custom_vertical(query, country=country)

