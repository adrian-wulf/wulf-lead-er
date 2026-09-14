"""
Lead Filtering and Relevance Verification for WULF LEAD.ER.

Ensures strict quality control by filtering out:
1. Public / municipal / government institutions and communal entities.
2. Major retail chains, gas stations, hypermarkets, and franchise corporations.
3. Industry-incompatible businesses via per-vertical negative keywords (e.g. coffee machine / AGD repair in IT).
"""

import re
from typing import Any

# Public institutions, municipal entities, state offices, schools, hospitals
PUBLIC_INSTITUTION_PATTERNS = re.compile(
    r"\b("
    # Polish public institutions
    r"urząd|urzad|gmina|gminn[yae]|miejsk[iaey]|wojewódzk[iaey]|wojewodzk[iaey]|państwow[iaey]|panstwow[iaey]|"
    r"szpital|szpitaln[yae]|klinika\s+uniwersytecka|nfz|policja|komisariat|komenda|straż\s+pożarna|straz\s+pozarna|"
    r"sąd|sad\s+rejonowy|sad\s+okręgowy|poczta\s+polska|zus|urząd\s+skarbowy|urzad\s+skarbowy|krajowa\s+administracja|"
    r"mosir|osir|szkoła\s+podstawowa|szkola\s+podstawowa|liceum|technikum|zespół\s+szkół|zespol\s+szkol|"
    r"przedszkole\s+miejskie|żłobek\s+miejski|zlobek\s+miejski|uniwersytet|politechnika|akademia|wydział|wydzial|"
    r"instytut\s+nauk|cmentarz|parafia|kościół|kosciol|"
    # German public institutions
    r"rathaus|bürgeramt|buergeramt|stadtverwaltung|gemeindeverwaltung|landratsamt|finanzamt|amtsgericht|"
    r"polizei|polizeiwache|polizeipräsidium|feuerwehr|berufsfeuerwehr|krankenhaus|klinikum|bundesagentur\s+für\s+arbeit|"
    r"grundschule|gymnasium|realschule|gesamtschule|universität|universitaet|hochschule"
    r")\b",
    re.IGNORECASE,
)

# Major national & international retail chains, hypermarkets, gas stations, franchises
CHAIN_BRAND_PATTERNS = re.compile(
    r"\b("
    r"mcdonald|kfc|burger\s+king|subway|starbucks|costa\s+coffee|pizza\s+hut|"
    r"biedronka|żabka|zabka|lidl|kaufland|dino|aldi|netto|carrefour|auchan|tesco|spar|eurospar|"
    r"rossmann|hebe|pepco|action|kik|tedi|"
    r"castorama|leroy\s+merlin|obi|bricomarche|brico|jula|hornbach|bauhaus|"
    r"media\s+markt|media\s+expert|rtv\s+euro\s+agd|neonet|x-kom|komputronik|"
    r"orlen|bp|shell|circle\s+k|amic|mol|avia|aral|esso|totalenergies|"
    r"dhl|dpd|inpost|gls|ups|fedex|paczkomat"
    r")\b",
    re.IGNORECASE,
)

# Blacklist of industry-incompatible terms per vertical (Polish & German)
VERTICAL_NEGATIVE_KEYWORDS: dict[str, list[str]] = {
    # 1. IT, Software & Web
    "informatyk": [
        "agd", "pralek", "pralki", "lodówek", "lodowek", "lodówki", "lodowki",
        "ekspres", "ekspresów", "ekspresow", "ekspresy", "kawa", "kawy", "kawiarnia",
        "kuchenek", "telewizor", "telewizorów", "telewizorow", "rtv",
        "vorwerk", "thermomix", "kobold", "zelmer", "amica",
        "ksero", "pieczątki", "pieczatki", "drukarnia", "toner", "tonery",
        "złom", "zlom", "złomu", "zlomu", "elektrośmieci", "elektrosmieci",
        "anteny", "montaż anten", "montaz anten", "telewizja naziemna",
        "kaffee", "kaffeemaschine", "haushaltsgeräte", "waschmaschine", "kühlschrank",
    ],
    "programista": [
        "agd", "pralek", "lodówek", "ekspres", "kawa", "telewizor", "rtv",
        "złom", "kancelaria", "nieruchomości", "sprzątanie", "serwis rtv",
        "vorwerk", "thermomix",
    ],
    "serwis_komputerowy": [
        "agd", "pralek", "lodówek", "lodówki", "ekspres", "ekspresów", "kawy",
        "kuchenek", "zmywarek", "pralki", "vorwerk", "thermomix", "odkurzaczy",
        "kaffeemaschinen", "haushaltsgeräte", "waschmaschinen",
    ],
    "tworzenie_stron": [
        "agd", "pralek", "lodówek", "ekspres", "złom", "druk wielkoformatowy",
    ],
    "agencja_marketingowa": [
        "agd", "pralek", "naprawa ekspresów", "złom", "sprzątanie",
    ],

    # 2. Hydraulicy (Plumbers)
    "plumbers": [
        "hurtownia", "salon łazienek", "salon lazienek", "płytki", "plytki",
        "glazura", "terakota", "ceramika", "wyposażenie wnętrz", "wyposazenie wnetrz",
        "meble łazienkowe", "meble lazienkowe", "market budowlany",
        "fliesenhandel", "baustoffhandel", "badausstellung",
    ],
    "hydraulik": [
        "hurtownia", "salon łazienek", "salon lazienek", "płytki", "plytki",
        "glazura", "terakota", "ceramika", "wyposażenie wnętrz", "wyposazenie wnetrz",
        "meble łazienkowe", "meble lazienkowe", "market budowlany",
    ],

    # 3. Elektrycy (Electricians)
    "electricians": [
        "sklep rtv", "hurtownia elektryczna", "oświetlenie lampy", "salon lamp",
        "sklep agd", "sklep z oświetleniem", "elektromarket",
        "leuchtenhaus", "elektrofachmarkt", "lampengeschäft",
    ],
    "elektryk": [
        "sklep rtv", "hurtownia elektryczna", "oświetlenie lampy", "salon lamp",
        "sklep agd", "sklep z oświetleniem", "elektromarket",
    ],

    # 4. Mechanika pojazdowa (Auto repair)
    "auto_repair": [
        "autokomis", "komis samochodowy", "salon samochodowy", "sprzedaż samochodów",
        "sprzedaz samochodow", "wypożyczalnia aut", "wypozyczalnia aut", "rent a car",
        "złomowanie aut", "kasacja pojazdów", "stacja demontażu",
        "autohaus", "autovermietung", "kfz-zulassung", "autoverwertung",
    ],
    "mechanik": [
        "autokomis", "komis samochodowy", "salon samochodowy", "sprzedaż samochodów",
        "sprzedaz samochodow", "wypożyczalnia aut", "rent a car",
        "złomowanie aut", "kasacja pojazdów",
    ],

    # 5. Siłownie & Fitness (Gym)
    "gym": [
        "orlik", "stadion", "hala sportowa", "ośrodek sportu", "osrodek sportu",
        "mosir", "osir", "basen miejski", "korty tenisowe", "boisko",
        "stadion sportowy", "klub zapaśniczy", "klub strzelecki",
        "turnhalle", "sportplatz", "stadion", "hallenbad",
    ],
    "silownia": [
        "orlik", "stadion", "hala sportowa", "ośrodek sportu", "osrodek sportu",
        "mosir", "osir", "basen miejski", "korty tenisowe", "boisko",
    ],

    # 6. Edukacja
    "szkola_jazdy": [
        "szkoła podstawowa", "szkola podstawowa", "liceum", "technikum",
        "szkoła wyższa", "przedszkole", "uniwersytet",
    ],
    "szkola_jezykowa": [
        "szkoła podstawowa", "szkola podstawowa", "liceum", "technikum",
        "przedszkole", "żłobek", "uniwersytet",
    ],

    # 7. Usługi motoryzacyjne specjalistyczne
    "wulkanizacja": [
        "myjnia ręczna", "myjnia bezdotykowa", "lakiernictwo", "blacharstwo",
    ],
    "myjnia": [
        "mechanika pojazdowa", "blacharstwo", "lakiernictwo", "naprawa silników",
    ],
    "stacja_kontroli_pojazdow": [
        "myjnia", "wulkanizacja opon", "autokomis", "blacharstwo",
    ],
}


def _normalize_string(val: str) -> str:
    """Normalize string for safe regex matching."""
    return " " + re.sub(r"[^\w\s-]", " ", val.lower()) + " "


def is_lead_relevant(
    lead_name: str,
    vertical_id: str = "",
    tags: dict[str, Any] | None = None,
    category: str | None = None,
) -> tuple[bool, str | None]:
    """
    Verify whether a lead candidate is genuinely relevant to the requested industry vertical.

    Returns:
        (is_relevant: bool, rejection_reason: str | None)
    """
    if not lead_name or not lead_name.strip():
        return False, "Brak nazwy firmy"

    norm_name = _normalize_string(lead_name)

    # 1. Public / Municipal / Government institutions check
    if PUBLIC_INSTITUTION_PATTERNS.search(norm_name):
        return False, f"Instytucja publiczna lub samorządowa: '{lead_name.strip()}'"

    # 2. National / International chain brands check
    if CHAIN_BRAND_PATTERNS.search(norm_name):
        return False, f"Znana sieć korporacyjna lub franczyza: '{lead_name.strip()}'"

    # 3. OSM tags check (if provided)
    if tags:
        brand = _normalize_string(tags.get("brand") or "")
        operator = _normalize_string(tags.get("operator") or "")
        if CHAIN_BRAND_PATTERNS.search(brand):
            return False, f"Sieciowa marka w tagach OSM (brand: {tags.get('brand')})"
        if CHAIN_BRAND_PATTERNS.search(operator):
            return False, f"Sieciowy operator w tagach OSM (operator: {tags.get('operator')})"

        # Check public operator tags
        if tags.get("operator:type") in ("public", "government", "community"):
            return False, "Podmiot publiczny / komunalny (operator:type=public)"
        if tags.get("government") or tags.get("amenity") in ("townhall", "courthouse", "police", "fire_station"):
            return False, f"Instytucja rządowa / komunalna ({tags.get('amenity') or 'government'})"

    # 4. Google Maps category check (if provided)
    if category:
        norm_cat = _normalize_string(category)
        if PUBLIC_INSTITUTION_PATTERNS.search(norm_cat):
            return False, f"Kategoria publiczna w Google Maps: '{category}'"
        if CHAIN_BRAND_PATTERNS.search(norm_cat):
            return False, f"Kategoria franczyzowa w Google Maps: '{category}'"

    # 5. Industry-specific negative keywords check
    v_key = vertical_id.lower().strip()
    # Normalize aliases e.g. "custom_informatyk" -> "informatyk"
    if v_key.startswith("custom_"):
        v_key = v_key[7:]

    # Match exact vertical or check fallback
    neg_list: list[str] = []
    if v_key in VERTICAL_NEGATIVE_KEYWORDS:
        neg_list = VERTICAL_NEGATIVE_KEYWORDS[v_key]
    else:
        # Check if v_key contains any known vertical key
        for k, v_words in VERTICAL_NEGATIVE_KEYWORDS.items():
            if k in v_key or v_key in k:
                neg_list = v_words
                break

    if neg_list:
        combined_text = norm_name
        if category:
            combined_text += " " + _normalize_string(category)

        for nw in neg_list:
            # Word boundary check for negative keyword
            pattern = rf"(?:\b|_){re.escape(nw.lower())}(?:\b|_)"
            if re.search(pattern, combined_text):
                return False, f"Wykryto słowo wykluczające '{nw}' dla branży '{vertical_id}' w '{lead_name.strip()}'"

    return True, None
