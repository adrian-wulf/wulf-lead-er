import re
import unicodedata
from pathlib import Path
from typing import Any
import yaml
from wulf_web_leader.models import VerticalDefinition, CountryVerticalConfig, VerticalAliases


def get_verticals_dir() -> Path:
    """Return path to verticals directory."""
    current = Path(__file__).resolve().parent
    candidates = [
        current.parent.parent / "verticals",
        current / "verticals",
        Path.cwd() / "verticals",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
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
        except Exception:
            continue
    return verticals


def find_vertical(query: str, verticals: dict[str, VerticalDefinition] | None = None) -> VerticalDefinition | None:
    """Find a vertical strictly by predefined YAML ID or PL/DE alias (case-insensitive)."""
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
    # 1. IT, Informatyka, Programowanie, Technologie
    "informatyk": {
        "label_pl": "Informatyk / Usługi IT & Software",
        "label_de": "IT-Dienstleister / Softwareentwicklung",
        "osm": [
            "office=it",
            "shop=computer",
            "craft=computer",
            "office=graphic_design",
            "office=web_design",
        ],
        "pkd": ["62.01.Z", "62.02.Z", "62.03.Z", "62.09.Z", "63.11.Z", "95.11.Z", "47.41.Z", "73.11.Z"],
        "wz": ["62.01", "62.02", "62.03", "62.09", "63.11", "95.11", "47.41", "73.11"],
    },
    "programista": {
        "label_pl": "Programista / Software House",
        "label_de": "Programmierer / Software House",
        "osm": ["office=it", "office=web_design"],
        "pkd": ["62.01.Z", "62.02.Z"],
        "wz": ["62.01", "62.02"],
    },
    "serwis_komputerowy": {
        "label_pl": "Serwis komputerowy / Naprawa komputerów",
        "label_de": "Computer-Reparatur / PC-Notdienst",
        "osm": ["shop=computer", "craft=computer", "office=it"],
        "pkd": ["95.11.Z", "47.41.Z"],
        "wz": ["95.11", "47.41"],
    },
    "tworzenie_stron": {
        "label_pl": "Tworzenie stron WWW / Agencja Interaktywna",
        "label_de": "Webdesign / Webagentur",
        "osm": ["office=it", "office=advertising_agency", "office=graphic_design", "office=web_design"],
        "pkd": ["62.01.Z", "73.11.Z"],
        "wz": ["62.01", "73.11"],
    },
    "agencja_marketingowa": {
        "label_pl": "Agencja Marketingowa / Reklama & SEO",
        "label_de": "Marketingagentur / Werbeagentur & SEO",
        "osm": ["office=advertising_agency", "office=graphic_design"],
        "pkd": ["73.11.Z"],
        "wz": ["73.11"],
    },

    # 2. Budownictwo, Remonty, Wykończenia
    "budowlanka": {
        "label_pl": "Firma budowlana / Usługi budowlano-remontowe",
        "label_de": "Bauunternehmen / Handwerker",
        "osm": [
            "craft=builder",
            "craft=tiler",
            "craft=plasterer",
            "craft=stonemason",
            "craft=concreter",
            "office=construction_company",
        ],
        "pkd": ["41.20.Z", "43.31.Z", "43.33.Z", "43.34.Z", "43.39.Z", "43.99.Z"],
        "wz": ["41.20", "43.31", "43.33", "43.34", "43.39", "43.99"],
    },
    "glazurnik": {
        "label_pl": "Glazurnik / Płytkarz & Układanie kafelków",
        "label_de": "Fliesenleger / Fliesenverlegung",
        "osm": ["craft=tiler"],
        "pkd": ["43.33.Z"],
        "wz": ["43.33"],
    },
    "brukarz": {
        "label_pl": "Brukarz / Układanie kostki brukowej",
        "label_de": "Pflasterer / Pflasterbau",
        "osm": ["craft=paver"],
        "pkd": ["43.99.Z", "42.11.Z"],
        "wz": ["43.99", "42.11"],
    },
    "spawacz": {
        "label_pl": "Spawacz / Usługi spawalnicze",
        "label_de": "Schweißer / Schweißarbeiten",
        "osm": ["craft=welder", "craft=metal_construction"],
        "pkd": ["25.62.Z"],
        "wz": ["25.62"],
    },
    "tapicer": {
        "label_pl": "Tapicer / Usługi tapicerskie & Renowacja",
        "label_de": "Polsterer / Polsterei",
        "osm": ["craft=upholsterer"],
        "pkd": ["95.24.Z", "31.09.Z"],
        "wz": ["95.24", "31.09"],
    },

    # 3. Zdrowie, Medycyna, Gabinety
    "lekarz": {
        "label_pl": "Lekarz / Przychodnia & Centrum medyczne",
        "label_de": "Arzt / Arztpraxis & Medizinisches Zentrum",
        "osm": ["amenity=doctors", "amenity=clinic", "healthcare=doctor", "healthcare=clinic"],
        "pkd": ["86.21.Z", "86.22.Z"],
        "wz": ["86.21", "86.22"],
    },
    "pediatra": {
        "label_pl": "Pediatra / Poradnia dziecięca",
        "label_de": "Kinderarzt / Pädiatrie",
        "osm": ["healthcare:speciality=paediatrics"],
        "pkd": ["86.21.Z", "86.22.Z"],
        "wz": ["86.21", "86.22"],
    },
    "ginekolog": {
        "label_pl": "Ginekolog / Gabinet ginekologiczny",
        "label_de": "Gynäkologe / Frauenarzt",
        "osm": ["healthcare:speciality=gynaecology"],
        "pkd": ["86.22.Z"],
        "wz": ["86.22"],
    },
    "okulista": {
        "label_pl": "Okulista / Gabinet okulistyczny & Optyk",
        "label_de": "Augenarzt / Augenheilkunde",
        "osm": ["healthcare:speciality=ophthalmology", "shop=optician"],
        "pkd": ["86.22.Z", "47.78.Z"],
        "wz": ["86.22", "47.78"],
    },
    "dermatolog": {
        "label_pl": "Dermatolog / Gabinet dermatologiczny",
        "label_de": "Hautarzt / Dermatologe",
        "osm": ["healthcare:speciality=dermatology"],
        "pkd": ["86.22.Z"],
        "wz": ["86.22"],
    },
    "kardiolog": {
        "label_pl": "Kardiolog / Poradnia kardiologiczna",
        "label_de": "Kardiologe / Kardiologie",
        "osm": ["healthcare:speciality=cardiology"],
        "pkd": ["86.22.Z"],
        "wz": ["86.22"],
    },
    "ortopeda": {
        "label_pl": "Ortopeda / Poradnia ortopedyczna",
        "label_de": "Orthopäde / Orthopädie",
        "osm": ["healthcare:speciality=orthopaedics"],
        "pkd": ["86.22.Z"],
        "wz": ["86.22"],
    },
    "psycholog": {
        "label_pl": "Psycholog / Psychoterapia & Gabinet",
        "label_de": "Psychologe / Psychotherapie",
        "osm": ["healthcare=psychotherapist", "healthcare=counselling", "office=therapist"],
        "pkd": ["86.90.E", "86.22.Z"],
        "wz": ["86.90", "86.22"],
    },
    "stomatolog": {
        "label_pl": "Stomatolog / Dentysta",
        "label_de": "Zahnarzt / Zahnarztpraxis",
        "osm": ["amenity=dentist", "healthcare=dentist"],
        "pkd": ["86.23.Z"],
        "wz": ["86.23"],
    },
    "fizjoterapia": {
        "label_pl": "Fizjoterapia / Gabinet rehabilitacji",
        "label_de": "Physiotherapie / Physiotherapeut",
        "osm": ["amenity=physiotherapist", "healthcare=physiotherapist"],
        "pkd": ["86.90.A"],
        "wz": ["86.90"],
    },
    "masaz": {
        "label_pl": "Salon Masażu / Masażysta",
        "label_de": "Massage / Massagestudio",
        "osm": ["shop=massage", "amenity=physiotherapist"],
        "pkd": ["96.04.Z", "86.90.A"],
        "wz": ["96.04", "86.90"],
    },

    # 4. Prawo, Notariat, Księgowość, Nieruchomości, Ubezpieczenia
    "prawnik": {
        "label_pl": "Adwokat / Kancelaria prawna",
        "label_de": "Rechtsanwalt / Kanzlei",
        "osm": ["office=lawyer"],
        "pkd": ["69.10.Z"],
        "wz": ["69.10"],
    },
    "notariusz": {
        "label_pl": "Kancelaria Notarialna / Notariusz",
        "label_de": "Notar / Notariat",
        "osm": ["office=notary"],
        "pkd": ["69.10.Z"],
        "wz": ["69.10"],
    },
    "ksiegowy": {
        "label_pl": "Biuro rachunkowe / Księgowość",
        "label_de": "Steuerberater / Buchhaltung",
        "osm": ["office=accountant", "office=tax_advisor"],
        "pkd": ["69.20.Z"],
        "wz": ["69.20"],
    },
    "ubezpieczenia": {
        "label_pl": "Agencja Ubezpieczeniowa / Ubezpieczenia",
        "label_de": "Versicherung / Versicherungsmakler",
        "osm": ["office=insurance"],
        "pkd": ["66.22.Z"],
        "wz": ["66.22"],
    },
    "nieruchomosci": {
        "label_pl": "Biuro Nieruchomości / Pośrednik",
        "label_de": "Immobilienmakler / Immobilienbüro",
        "osm": ["office=estate_agent"],
        "pkd": ["68.31.Z", "68.32.Z"],
        "wz": ["68.31", "68.32"],
    },
    "szkola_jazdy": {
        "label_pl": "Szkoła Jazdy / Nauka Jazdy (OSK)",
        "label_de": "Fahrschule / Fahrlehrer",
        "osm": ["amenity=driving_school"],
        "pkd": ["85.53.Z"],
        "wz": ["85.53"],
    },

    # 5. Instalacje, Klimatyzacja, HVAC, Fotowoltaika
    "klimatyzacja": {
        "label_pl": "Klimatyzacja & Wentylacja / HVAC",
        "label_de": "Klima & Lüftungstechnik / HVAC",
        "osm": ["craft=hvac", "craft=air_conditioning"],
        "pkd": ["43.22.Z"],
        "wz": ["43.22"],
    },
    "fotowoltaika": {
        "label_pl": "Fotowoltaika & Energia Słoneczna",
        "label_de": "Photovoltaik & Solaranlagen",
        "osm": ["craft=photovoltaic"],
        "pkd": ["43.21.Z"],
        "wz": ["43.21"],
    },
    "pompy_ciepla": {
        "label_pl": "Pompy Ciepła / Instalacje Grzewcze",
        "label_de": "Wärmepumpen / Heizungstechnik",
        "osm": ["craft=hvac"],
        "pkd": ["43.22.Z"],
        "wz": ["43.22"],
    },

    # 6. Motoryzacja, Detailing, Opony, Pomoc drogowa
    "wulkanizacja": {
        "label_pl": "Wulkanizacja / Serwis opon",
        "label_de": "Reifendienst / Reifenwechsel",
        "osm": ["shop=tyres"],
        "pkd": ["45.20.Z"],
        "wz": ["45.20"],
    },
    "myjnia": {
        "label_pl": "Myjnia Samochodowa & Auto Detailing",
        "label_de": "Autowäsche & Fahrzeugaufbereitung",
        "osm": ["amenity=car_wash"],
        "pkd": ["45.20.Z"],
        "wz": ["45.20"],
    },
    "pomoc_drogowa": {
        "label_pl": "Pomoc Drogowa / Holowanie & Laweta",
        "label_de": "Abschleppdienst / Pannenhilfe",
        "osm": ["craft=towing"],
        "pkd": ["52.21.Z"],
        "wz": ["52.21"],
    },
    "stacja_kontroli_pojazdow": {
        "label_pl": "Stacja Kontroli Pojazdów / Przeglądy",
        "label_de": "TÜV / Fahrzeugprüfung",
        "osm": ["amenity=vehicle_inspection"],
        "pkd": ["71.20.B"],
        "wz": ["71.20"],
    },

    # 7. Uroda, Kosmetyka, Paznokcie
    "kosmetyczka": {
        "label_pl": "Salon Kosmetyczny / Kosmetologia & Paznokcie",
        "label_de": "Kosmetikstudio / Nagelstudio",
        "osm": ["shop=beauty"],
        "pkd": ["96.02.Z"],
        "wz": ["96.02"],
    },
    "tatuaz": {
        "label_pl": "Studio Tatuażu / Piercing",
        "label_de": "Tattoo-Studio / Piercing",
        "osm": ["shop=tattoo"],
        "pkd": ["96.09.Z"],
        "wz": ["96.09"],
    },

    # 8. Czystość, Przeprowadzki, Geodezja, Kominiarstwo
    "sprzatanie": {
        "label_pl": "Firma sprzątająca / Usługi czystości",
        "label_de": "Gebäudereinigung / Reinigungsfirma",
        "osm": ["craft=cleaning", "office=cleaning"],
        "pkd": ["81.21.Z", "81.22.Z"],
        "wz": ["81.21", "81.22"],
    },
    "przeprowadzki": {
        "label_pl": "Przeprowadzki & Transport",
        "label_de": "Umzüge & Transport",
        "osm": ["craft=moving", "office=moving"],
        "pkd": ["49.42.Z"],
        "wz": ["49.42"],
    },
    "geodeta": {
        "label_pl": "Geodeta / Usługi geodezyjne",
        "label_de": "Vermessungsbüro / Geodät",
        "osm": ["office=surveyor"],
        "pkd": ["71.12.Z"],
        "wz": ["71.12"],
    },
    "kominiarz": {
        "label_pl": "Kominiarz / Usługi kominiarskie",
        "label_de": "Schornsteinfeger",
        "osm": ["craft=chimney_sweeper"],
        "pkd": ["81.22.Z"],
        "wz": ["81.22"],
    },
    "architekt": {
        "label_pl": "Architekt / Biuro projektowe",
        "label_de": "Architekt / Architekturbüro",
        "osm": ["office=architect"],
        "pkd": ["71.11.Z"],
        "wz": ["71.11"],
    },
    "tlumacz": {
        "label_pl": "Tłumacz / Biuro tłumaczeń",
        "label_de": "Übersetzer / Übersetzungsbüro",
        "osm": ["office=translator"],
        "pkd": ["74.30.Z"],
        "wz": ["74.30"],
    },

    # 9. Rzemiosło tradycyjne
    "szklarz": {
        "label_pl": "Szklarz / Usługi szklarskie",
        "label_de": "Glaser / Glaserei",
        "osm": ["craft=glazier", "shop=glaziery"],
        "pkd": ["43.34.Z"],
        "wz": ["43.34"],
    },
    "stolarz": {
        "label_pl": "Stolarz / Usługi stolarskie & Meble",
        "label_de": "Tischler / Schreiner / Möbelbau",
        "osm": ["craft=carpenter", "craft=joiner", "craft=furniture"],
        "pkd": ["16.23.Z", "31.09.Z"],
        "wz": ["16.23", "31.09"],
    },
    "malarz": {
        "label_pl": "Malarz / Usługi malarskie",
        "label_de": "Malerbetrieb / Lackierer",
        "osm": ["craft=painter"],
        "pkd": ["43.34.Z"],
        "wz": ["43.34"],
    },
    "dekarz": {
        "label_pl": "Dekarz / Usługi dekarskie & Dachy",
        "label_de": "Dachdecker / Bedachungen",
        "osm": ["craft=roofer"],
        "pkd": ["43.91.Z"],
        "wz": ["43.91"],
    },
    "slusarz": {
        "label_pl": "Ślusarz / Usługi ślusarskie",
        "label_de": "Schlosser / Schlosserei",
        "osm": ["craft=locksmith"],
        "pkd": ["25.62.Z"],
        "wz": ["25.62"],
    },
    "krawiec": {
        "label_pl": "Krawiec / Usługi krawieckie & Poprawki",
        "label_de": "Schneider / Schneiderei",
        "osm": ["craft=tailor"],
        "pkd": ["14.13.Z", "95.29.Z"],
        "wz": ["14.13", "95.29"],
    },
    "szewc": {
        "label_pl": "Szewc / Naprawa obuwia",
        "label_de": "Schuhmacher / Schuhreparatur",
        "osm": ["craft=shoemaker"],
        "pkd": ["95.23.Z"],
        "wz": ["95.23"],
    },
    "zegarmistrz": {
        "label_pl": "Zegarmistrz / Naprawa zegarków",
        "label_de": "Uhrmacher / Uhrenservice",
        "osm": ["craft=watchmaker", "shop=watch"],
        "pkd": ["95.25.Z"],
        "wz": ["95.25"],
    },
    "jubiler": {
        "label_pl": "Jubiler / Złotnik & Biżuteria",
        "label_de": "Juwelier / Goldschmied",
        "osm": ["shop=jewelry", "craft=jeweller"],
        "pkd": ["47.77.Z", "32.12.Z"],
        "wz": ["47.77", "32.12"],
    },
    "fotograf": {
        "label_pl": "Fotograf / Studio fotograficzne",
        "label_de": "Fotograf / Fotostudio",
        "osm": ["craft=photographer", "shop=photo"],
        "pkd": ["74.20.Z"],
        "wz": ["74.20"],
    },
    "drukarnia": {
        "label_pl": "Drukarnia / Usługi poligraficzne",
        "label_de": "Druckerei / Druckstudio",
        "osm": ["craft=printer"],
        "pkd": ["18.12.Z"],
        "wz": ["18.12"],
    },
    "ogrodnik": {
        "label_pl": "Ogrodnik / Usługi ogrodnicze & Tereny zielone",
        "label_de": "Gartenbau / Landschaftsbau",
        "osm": ["craft=gardener", "shop=garden_centre"],
        "pkd": ["81.30.Z"],
        "wz": ["81.30"],
    },
    "kwiaciarnia": {
        "label_pl": "Kwiaciarnia / Florystyka",
        "label_de": "Blumengeschäft / Floristik",
        "osm": ["shop=florist"],
        "pkd": ["47.76.Z"],
        "wz": ["47.76"],
    },
    "optyk": {
        "label_pl": "Optyk / Salon optyczny",
        "label_de": "Optiker / Augenoptik",
        "osm": ["shop=optician"],
        "pkd": ["47.78.Z"],
        "wz": ["47.78"],
    },
    "apteka": {
        "label_pl": "Apteka",
        "label_de": "Apotheke",
        "osm": ["amenity=pharmacy"],
        "pkd": ["47.73.Z"],
        "wz": ["47.73"],
    },

    # 10. Gastronomia & Noclegi
    "pizzeria": {
        "label_pl": "Pizzeria / Restauracja włoska",
        "label_de": "Pizzeria / Italienisches Restaurant",
        "osm": ["amenity=restaurant", "amenity=fast_food"],
        "pkd": ["56.10.A"],
        "wz": ["56.10"],
    },
    "kebab": {
        "label_pl": "Kebab / Fast Food",
        "label_de": "Döner / Fast Food",
        "osm": ["amenity=fast_food", "amenity=restaurant"],
        "pkd": ["56.10.B"],
        "wz": ["56.10"],
    },
    "sushi": {
        "label_pl": "Sushi / Kuchnia azjatycka",
        "label_de": "Sushi / Asiatische Küche",
        "osm": ["amenity=restaurant"],
        "pkd": ["56.10.A"],
        "wz": ["56.10"],
    },
    "burger": {
        "label_pl": "Burgerownia / Burgery",
        "label_de": "Burger-Restaurant / Burger",
        "osm": ["amenity=restaurant", "amenity=fast_food"],
        "pkd": ["56.10.A"],
        "wz": ["56.10"],
    },
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
    "catering": {
        "label_pl": "Catering / Dieta pudełkowa",
        "label_de": "Catering / Partyservice",
        "osm": ["craft=caterer"],
        "pkd": ["56.21.Z", "56.29.Z"],
        "wz": ["56.21", "56.29"],
    },
    "hotel": {
        "label_pl": "Hotel / Obiekt noclegowy & Pensjonat",
        "label_de": "Hotel / Pension / Unterkunft",
        "osm": ["tourism=hotel", "tourism=guest_house", "tourism=hostel", "tourism=motel"],
        "pkd": ["55.10.Z", "55.20.Z"],
        "wz": ["55.10", "55.20"],
    },

    # 11. Edukacja, Zwierzęta, Sport
    "groomer": {
        "label_pl": "Groomer / Strzyżenie psów & Salon dla zwierząt",
        "label_de": "Hundesalon / Tierpflege",
        "osm": ["shop=pet_grooming"],
        "pkd": ["96.09.Z"],
        "wz": ["96.09"],
    },
    "szkola_jezykowa": {
        "label_pl": "Szkoła Językowa / Kursy językowe",
        "label_de": "Sprachschule / Sprachkurse",
        "osm": ["amenity=language_school"],
        "pkd": ["85.59.A"],
        "wz": ["85.59"],
    },
    "przedszkole": {
        "label_pl": "Przedszkole / Żłobek",
        "label_de": "Kindergarten / Kita",
        "osm": ["amenity=kindergarten"],
        "pkd": ["85.10.Z"],
        "wz": ["85.10"],
    },
    "basen": {
        "label_pl": "Basen / Pływalnia & Nauka pływania",
        "label_de": "Schwimmbad / Hallenbad",
        "osm": ["leisure=swimming_pool"],
        "pkd": ["93.11.Z"],
        "wz": ["93.11"],
    },
}

# Stem and keyword routing to map any inflection, plural, or synonym to a trade key or base vertical ID
STEM_TO_TRADE: dict[str, str] = {
    # Base 8 verticals mappings
    "hydraul": "plumbers",
    "wod-kan": "plumbers",
    "kanalizac": "plumbers",
    "rur": "plumbers",
    "plumber": "plumbers",
    "klempner": "plumbers",
    "sanitaer": "plumbers",
    "elektry": "electricians",
    "elektro": "electricians",
    "electrician": "electricians",
    "elektriker": "electricians",
    "mechan": "auto_repair",
    "warsztat": "auto_repair",
    "autonapraw": "auto_repair",
    "samochodow": "auto_repair",
    "autoreparatur": "auto_repair",
    "autowerkstatt": "auto_repair",
    "piekar": "bakery",
    "chleb": "bakery",
    "baeckerei": "bakery",
    "bakery": "bakery",
    "silown": "gym",
    "fitness": "gym",
    "gym": "gym",
    "fryzj": "hair",
    "barber": "hair",
    "friseur": "hair",
    "hairdresser": "hair",
    "restaurac": "restaurant",
    "gastronom": "restaurant",
    "weteryn": "veterinary",
    "tierarzt": "veterinary",
    "veterinary": "veterinary",

    # IT / Software / Komputery
    "informatyk": "informatyk",
    "informatyc": "informatyk",
    "informaty": "informatyk",
    "programis": "programista",
    "programow": "programista",
    "komputer": "informatyk",
    "software": "informatyk",
    "webdev": "informatyk",
    "webdesign": "tworzenie_stron",
    "stron": "tworzenie_stron",
    "pozycjonow": "agencja_marketingowa",
    "marketing": "agencja_marketingowa",
    "reklam": "agencja_marketingowa",
    "seo": "agencja_marketingowa",
    "edv": "informatyk",
    "systemhaus": "informatyk",
    "developer": "programista",

    # Budownictwo / Remonty / Wykończenia
    "budowl": "budowlanka",
    "remont": "budowlanka",
    "wykonczen": "budowlanka",
    "glazur": "glazurnik",
    "plytk": "glazurnik",
    "kafel": "glazurnik",
    "flis": "glazurnik",
    "brukar": "brukarz",
    "kostka": "brukarz",
    "murar": "budowlanka",
    "tynk": "budowlanka",
    "posadzk": "budowlanka",
    "ocieplen": "budowlanka",
    "elewac": "budowlanka",
    "spawacz": "spawacz",
    "spawal": "spawacz",
    "tapicer": "tapicer",
    "bau": "budowlanka",
    "renovier": "budowlanka",
    "handwerk": "budowlanka",
    "fliesen": "glazurnik",

    # Zdrowie / Medycyna
    "lekar": "lekarz",
    "przychodn": "lekarz",
    "klinik": "lekarz",
    "doktor": "lekarz",
    "medyc": "lekarz",
    "pediatr": "pediatra",
    "ginekolog": "ginekolog",
    "okulist": "okulista",
    "dermatol": "dermatolog",
    "kardiolog": "kardiolog",
    "ortoped": "ortopeda",
    "psycholog": "psycholog",
    "psychiatr": "psycholog",
    "psychoterap": "psycholog",
    "stomatol": "stomatolog",
    "dentys": "stomatolog",
    "ortodont": "stomatolog",
    "protety": "stomatolog",
    "fizjoterap": "fizjoterapia",
    "rehabilit": "fizjoterapia",
    "osteopat": "fizjoterapia",
    "masaz": "masaz",
    "arzt": "lekarz",
    "praxis": "lekarz",
    "zahnarzt": "stomatolog",
    "physio": "fizjoterapia",

    # Prawo / Księgowość / Finanse
    "prawn": "prawnik",
    "adwokat": "prawnik",
    "radca": "prawnik",
    "kancelar": "prawnik",
    "mecenas": "prawnik",
    "notariusz": "notariusz",
    "ksiegow": "ksiegowy",
    "rachunk": "ksiegowy",
    "podatk": "ksiegowy",
    "audyt": "ksiegowy",
    "steuer": "ksiegowy",
    "anwalt": "prawnik",
    "notar": "notariusz",
    "lawyer": "prawnik",
    "accountant": "ksiegowy",

    # Nieruchomości / Ubezpieczenia / Szkoła jazdy
    "nieruchom": "nieruchomosci",
    "mieszkan": "nieruchomosci",
    "immobilien": "nieruchomosci",
    "makler": "nieruchomosci",
    "estate": "nieruchomosci",
    "ubezpiecz": "ubezpieczenia",
    "polis": "ubezpieczenia",
    "versicher": "ubezpieczenia",
    "insurance": "ubezpieczenia",
    "szkola jazd": "szkola_jazdy",
    "nauka jazd": "szkola_jazdy",
    "instruktor jazd": "szkola_jazdy",
    "prawo jazd": "szkola_jazdy",
    "osk": "szkola_jazdy",
    "fahrschul": "szkola_jazdy",

    # HVAC / Fotowoltaika
    "klimatyz": "klimatyzacja",
    "klima": "klimatyzacja",
    "wentylac": "klimatyzacja",
    "chlodn": "klimatyzacja",
    "pompy ciepl": "pompy_ciepla",
    "pompa ciepl": "pompy_ciepla",
    "rekuper": "klimatyzacja",
    "hvac": "klimatyzacja",
    "fotowolt": "fotowoltaika",
    "solar": "fotowoltaika",

    # Motoryzacja
    "wulkaniz": "wulkanizacja",
    "opon": "wulkanizacja",
    "tyre": "wulkanizacja",
    "reifen": "wulkanizacja",
    "autodetail": "myjnia",
    "detail": "myjnia",
    "myjnia": "myjnia",
    "pomoc drogow": "pomoc_drogowa",
    "holowani": "pomoc_drogowa",
    "lawet": "pomoc_drogowa",
    "przeglad": "stacja_kontroli_pojazdow",
    "stacja kontrol": "stacja_kontroli_pojazdow",

    # Uroda
    "kosmety": "kosmetyczka",
    "paznok": "kosmetyczka",
    "manicur": "kosmetyczka",
    "pedicur": "kosmetyczka",
    "makijaz": "kosmetyczka",
    "rzes": "kosmetyczka",
    "brwi": "kosmetyczka",
    "kosmetolog": "kosmetyczka",
    "tatuaz": "tatuaz",
    "tattoo": "tatuaz",
    "piercing": "tatuaz",

    # Czystość / Transport
    "sprzat": "sprzatanie",
    "czyszcz": "sprzatanie",
    "reinig": "sprzatanie",
    "cleaning": "sprzatanie",
    "przeprowadzk": "przeprowadzki",
    "bagazow": "przeprowadzki",
    "umzug": "przeprowadzki",
    "moving": "przeprowadzki",

    # Gastronomia / Noclegi
    "pizz": "pizzeria",
    "kebab": "kebab",
    "doner": "kebab",
    "sushi": "sushi",
    "burger": "burger",
    "catering": "catering",
    "dieta pudelkow": "catering",
    "hotel": "hotel",
    "hostel": "hotel",
    "pensjonat": "hotel",
    "nocleg": "hotel",
    "apartament": "hotel",

    # Rzemiosło
    "szklar": "szklarz",
    "glasi": "szklarz",
    "stolar": "stolarz",
    "mebl": "stolarz",
    "schrein": "stolarz",
    "tischl": "stolarz",
    "carpenter": "stolarz",
    "malar": "malarz",
    "maler": "malarz",
    "painter": "malarz",
    "dekar": "dekarz",
    "dachdeck": "dekarz",
    "roofer": "dekarz",
    "slusar": "slusarz",
    "schlosser": "slusarz",
    "locksmith": "slusarz",
    "kraw": "krawiec",
    "schneider": "krawiec",
    "tailor": "krawiec",
    "szew": "szewc",
    "schuh": "szewc",
    "shoemaker": "szewc",
    "zegarmistrz": "zegarmistrz",
    "uhrmach": "zegarmistrz",
    "watchmak": "zegarmistrz",
    "jubiler": "jubiler",
    "zlotnik": "jubiler",
    "juwelier": "jubiler",
    "jewel": "jubiler",
    "fotograf": "fotograf",
    "photograph": "fotograf",
    "drukarn": "drukarnia",
    "druck": "drukarnia",
    "printer": "drukarnia",
    "ogrodn": "ogrodnik",
    "garten": "ogrodnik",
    "garden": "ogrodnik",
    "kwiaciarn": "kwiaciarnia",
    "blumen": "kwiaciarnia",
    "florist": "kwiaciarnia",
    "cukiern": "cukiernia",
    "konditor": "cukiernia",
    "pastry": "cukiernia",
    "kawiarn": "kawiarnia",
    "cafe": "kawiarnia",
    "optyk": "optyk",
    "optik": "optyk",
    "optician": "optyk",
    "aptek": "apteka",
    "apotheke": "apteka",
    "pharmacy": "apteka",
    "geodet": "geodeta",
    "vermess": "geodeta",
    "surveyor": "geodeta",
    "komin": "kominiarz",
    "schornstein": "kominiarz",
    "architekt": "architekt",
    "architect": "architekt",
    "tlumacz": "tlumacz",
    "translat": "tlumacz",
    "groomer": "groomer",
    "hundesalon": "groomer",
    "jezyk": "szkola_jezykowa",
    "przedszkol": "przedszkole",
    "zlobek": "przedszkole",
    "basen": "basen",
    # Specific short codes & Polish alternations
    "it": "informatyk",
    "pc": "informatyk",
    "ai": "informatyk",
    "web": "informatyk",
    "adwok": "prawnik",
    "radc": "prawnik",
    "mecenas": "prawnik",
    "dentys": "stomatolog",
    "dentyst": "stomatolog",
    "dentysc": "stomatolog",
    "stomatol": "stomatolog",
    "plytk": "glazurnik",
    "kafel": "glazurnik",
    "flis": "glazurnik",
    "ogrodnictw": "ogrodnik",
}


def _match_stem_or_keyword(text: str) -> str | None:
    """Find the best matching trade key from raw or stemmed query."""
    clean = _strip_diacritics(text.lower().strip())
    # Exact check first
    if clean in KNOWN_CUSTOM_TRADES:
        return clean
    if clean in STEM_TO_TRADE:
        return STEM_TO_TRADE[clean]

    # Check multi-word phrase matching
    for stem, target in STEM_TO_TRADE.items():
        if " " in stem and stem in clean:
            return target

    # Check word tokens and roots
    words = re.findall(r"\w+", clean)
    for word in words:
        if word in KNOWN_CUSTOM_TRADES:
            return word
        if word in STEM_TO_TRADE:
            return STEM_TO_TRADE[word]
        # Prefix / substring root match
        for stem, target in STEM_TO_TRADE.items():
            if len(stem) >= 3 and (word.startswith(stem) or (len(stem) >= 4 and stem in word)):
                return target

    return None


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

    # 2. Check direct match in known dictionary of trades
    trade_key = None
    if norm in KNOWN_CUSTOM_TRADES:
        trade_key = norm
    else:
        ascii_key = _strip_diacritics(norm)
        if ascii_key in KNOWN_CUSTOM_TRADES:
            trade_key = ascii_key

    # 3. If still not matched, run intelligent stem and keyword resolver
    if not trade_key:
        stem_match = _match_stem_or_keyword(norm)
        if stem_match:
            # If the stem matched one of the 8 base verticals, delegate to it
            base_v = find_vertical(stem_match)
            if base_v:
                return base_v
            if stem_match in KNOWN_CUSTOM_TRADES:
                trade_key = stem_match

    if trade_key and trade_key in KNOWN_CUSTOM_TRADES:
        trade = KNOWN_CUSTOM_TRADES[trade_key]
        clean_slug = re.sub(r"[^a-zA-Z0-9_]", "", _strip_diacritics(trade_key).replace(" ", "_"))
        v_id = f"custom_{clean_slug}"
        name = norm.title()
        return VerticalDefinition(
            id=v_id,
            name=name,
            aliases=VerticalAliases(pl=[norm, trade_key], de=[norm, trade_key]),
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

    # 4. Fallback for completely arbitrary custom trade or keyword (e.g. "sauna", "browar")
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
