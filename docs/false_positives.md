# Rejestr Fałszywych Trafień (False-Positives Register)

Dokumentacja wzorców fałszywych trafień zidentyfikowanych w kodzie źródłowym, definicjach branż (`verticals/*.yaml`) oraz danych pobieranych z OpenStreetMap i audytu HTTP.

---

## Wzorzec 1: Nadmiarowy tag nadrzędny w wertykale (np. `shop=beauty` w branży fryzjerskiej)

- **Problem:** Plik `verticals/hair.yaml` pierwotnie zawierał tag `shop=beauty`, co ściągało do wyników gabinety kosmetyczne, solaria, salony masażu i spa zamiast wyłącznie fryzjerów i barberów (aż 30-35% wyników w teście drezdeńskim).
- **Wpływ:** Użytkownik dzwonił do salonu masażu z ofertą strony dla fryzjera.
- **Rozwiązanie:** Ograniczenie tagów w YAML wyłącznie do `shop=hairdresser`.
- **Jak wykryć testem:** Test jednostkowy ładujący definicję `hair` i sprawdzający `assert "shop=beauty" not in vertical.pl.osm` oraz `assert "shop=beauty" not in vertical.de.osm`.

---

## Wzorzec 2: Zbyt szerokie tagi w warsztatach samochodowych (`shop=car` w `auto_repair.yaml`)

- **Problem:** Jeśli wertykał mechaniki pojazdowej zawiera ogólny tag `shop=car` zamiast `shop=car_repair`, ściąga salony sprzedaży aut nowych i używanych (komisy), które zazwyczaj posiadają rozbudowane korporacyjne strony www lub portale Otomoto.
- **Wpływ:** Komis samochodowy jest błędnie kwalifikowany jako warsztat mechaniczny.
- **Rozwiązanie:** Wykluczenie `shop=car` z `auto_repair.yaml`; dozwolone wyłącznie `shop=car_repair`, `craft=blacksmith` (jeśli dotyczy resorów), `service=tyres` itp.
- **Jak wykryć testem:** Test sprawdzający, czy żaden tag w `auto_repair.yaml` nie ma wartości `shop=car` oraz czy zapytanie Overpass nie zwraca salonów dealerskich.

---

## Wzorzec 3: Wizytówki platformowe i katalogi traktowane jako strona własna (`*.business.site`, Booksy, ZnanyLekarz, Oferteo)

- **Problem:** Jeśli pole `website` w OSM zawiera darmową wizytówkę Google (`https://*.business.site`), profil na Booksy (`booksy.com/...`), profil Oferteo czy ZnanyLekarz, a klasyfikator domen traktuje to jako stronę własną (`own`), lead otrzymuje zaniżony wynik (score 20 zamiast 55–70).
- **Wpływ:** Firma bez prawdziwej strony www zostaje oznaczona jako SKIP, bo algorytm uznaje profil w katalogu za witrynę własną.
- **Rozwiązanie:** Rozszerzenie reguł w `audit/classifier.py` o domeny katalogowe i platformowe (`booksy.com`, `oferteo.pl`, `znanylekarz.pl`, `olx.pl`, `*.business.site`).
- **Jak wykryć testem:** Test parametryzowany weryfikujący, że `classify_website_kind("https://salon.business.site") == "directory"` oraz `classify_website_kind("https://booksy.com/pl-pl/1234") == "directory"`.

---

## Wzorzec 4: Martwe punkty usługowe (wygasłe tagi `disused:*`, `abandoned:*`, `closed=*`)

- **Problem:** W OpenStreetMap punkty zlikwidowane są często oznaczane przez edytorów zmianą klucza tagu na np. `disused:shop=hairdresser`, `abandoned:amenity=restaurant` lub tagiem `opening_hours=closed`. Jeśli zapytanie lub parser nie odfiltruje takich prefiksów, zlikwidowane firmy trafiają na listę jako HOT z nieczynnym telefonem.
- **Wpływ:** Użytkownik dzwoni pod numer nieistniejącej firmy.
- **Rozwiązanie:** Parser w `adapters/osm.py` musi ignorować elementy posiadające tagi `disused`, `abandoned` lub prefiksy `disused:` / `abandoned:`.
- **Jak wykryć testem:** Fixtura elementu OSM z tagami `{"disused:shop": "hairdresser", "name": "Stary Zakład"}` po przepuszczeniu przez `parse_elements_to_leads` zwraca pustą listę.

---

## Wzorzec 5: Duplikat węzła i obrysu budynku (Node + Way w promieniu kilkunastu metrów)

- **Problem:** Ten sam zakład jest często wpisany w OSM podwójnie: raz jako punkt POI (node) z numerem telefonu, a drugi raz jako budynek (way) z adresem, czasem z drobną literówką w nazwie (np. `Auto Serwis Kowalski` i `Kowalski Auto-Serwis`).
- **Wpływ:** Dwa prawie identyczne leady w wygenerowanym arkuszu CSV.
- **Rozwiązanie:** Agresywniejsza deduplikacja w `adapters/osm.py` oparta na znormalizowanym numerze telefonu oraz odległości geograficznej (np. < 100 m).
- **Jak wykryć testem:** Fixtura z dwoma elementami OSM (node i way) o identycznym numerze telefonu i odległości 30 m po przepuszczeniu przez parser łączy się w pojedynczy `CanonicalLead`.

---

## Wzorzec 6: Pominięcie domeny firmowej w tagu e-mail w OSM (Casus Feldheim & Söhne GmbH)

- **Problem:** Firma „Feldheim & Söhne GmbH” w Hanowerze posiadała w węźle OSM tag `contact:email=info@pefeld.de`, ale brakowało tagu `website`. Stary kod sprawdzał wyłącznie `website`, więc uznał, że firma w 100% nie posiada strony („HOT 70 brak strony www”). W rzeczywistości firma posiada domenę pocztową `pefeld.de` (strona z 2002 roku) oraz aktywną witrynę komercyjną `feldheim-sanitaer-heizung.de`. Webmaster dzwoniący z twierdzeniem „nie macie strony” palił kontakt w pierwszych 5 sekundach rozmowy.
- **Wpływ:** Fałszywy alarm i utrata wiarygodności agencji/freelancera podczas zimnego telefonu.
- **Rozwiązanie:** Parser w `adapters/osm.py` weryfikuje tagi `contact:email` i `email`, filtruje darmowych dostawców (blacklist freemail: Gmail, GMX, T-Online, WP, Onet itd.) i jeśli wykryje domenę własną, przypisuje ją jako adres `website` podlegający audytowi technicznemu.
- **Jak wykryć testem:** `tests/test_email_domain_extract.py::test_osm_adapter_discovers_website_from_email`.

---

## Wzorzec 7: Monokultura scoringu (brak strony www jako jedyny HOT >= 70)

- **Problem:** W pierwotnym silniku jedyną drogą do progu HOT (>=70) było `website_kind == 'none'` (+50) + telefon (+20). Awaria strony (błąd 404, 500, błąd DNS) dawała zaledwie 40 + 20 = 60 pkt (WARM). Koszmarna strona bez wersji na smartfony (brak RWD) i bez SSL dawała max 65 pkt (WARM). W efekcie 100% leadów HOT w każdym skanie to był wyłącznie „brak strony w OSM”, podczas gdy dla agencji www **zepsuta witryna klienta** to najwyższa możliwa konwersja sprzedażowa.
- **Wpływ:** Najlepsze okazje rynkowe (firmy, które rozumieją potrzebę www i tracą klientów przez awarię) były ukrywane przed użytkownikiem w worku WARM.
- **Rozwiązanie:** Przebudowa silnika scoringu (`score/engine.py`):
  1. `broken_website`: Awaria serwera (4xx/5xx/DNS/SSL) = +65 pkt + telefon (+20) -> **85 pkt (SUPER HOT)**.
  2. `critical_redesign`: Brak RWD (+35) + brak SSL (+15) / stary CMS (+15) + telefon (+20) -> **70–85 pkt (HOT)**.
  3. `social_only`: Facebook/Instagram + telefon (+20) -> **70 pkt (HOT)**.
  4. `no_website`: Brak w OSM dla rzemieślnika + telefon (+20) -> **70 pkt (HOT)**.
- **Jak wykryć testem:** `tests/test_scoring_archetypes.py` weryfikuje każdy z archetypów na poziomie HOT >= 70.

---

## Wzorzec 8: Spółki kapitałowe (GmbH, Sp. z o.o.) bez tagu www w OSM

- **Problem:** W OpenStreetMap brak wpisu `website` jest częsty z powodu lenistwa wolontariuszy. W przypadku jednoosobowego hydraulika brak strony w OSM jest bardzo prawdopodobny, ale spółka prawa handlowego (`GmbH`, `Sp. z o.o.`, `AG`) w 95% przypadków posiada stronę www, która po prostu nie została wpisana do map. Zgłoszenie jej jako 100% pewny brak strony prowadzi do kompromitacji podczas rozmowy.
- **Wpływ:** Fałszywa pewność raportu przy kontaktowaniu większych podmiotów.
- **Rozwiązanie:** Wykrywanie formy prawnej (`is_corporate_entity`) w `adapters/osm.py`. W przypadku braku strony podmiot otrzymuje `opportunity_type = "suspect_unverified"`, oznaczenie `confidence = "low"`, ostrzeżenie na karcie HTML (*"⚠️ Uwaga: To spółka prawa handlowego — sprawdź w Google przed telefonem"*) oraz bezpieczny skrypt rozmowy sondującej zamiast agresywnego oświadczenia o braku strony.
- **Jak wykryć testem:** `tests/test_scoring_archetypes.py::test_archetype_corporate_suspect_unverified`.
