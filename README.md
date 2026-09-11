---
title: Wulf Web Leader
emoji: 🐺
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 6.27.0
app_file: app.py
python_version: "3.12"
short_description: Skaner leadów dla web designerów (PL i DE)
pinned: false
---

# wulf-web-leader

Lokalny skaner leadów dla ekipy, która robi strony w PL i DE.  
Bez konta, bez chmury, bez wysyłki maili. 100% local-first, licencja MIT.

---

## Po co
Dostajesz listę lokalnych firm z okolicy, które nie mają własnej strony www albo polegają wyłącznie na profilu na Facebooku, Instagramie czy starym wpisie w katalogu.

Ty dzwonisz, wchodzisz jak człowiek do warsztatu czy salonu albo wpadacie z gotowym demem. Narzędzie **nie spamuje**, nie wysyła maili i nie służy do cold-mailingu. Zwraca wyłącznie zwalidowaną, posortowaną listę firm z publicznym kontaktem, statusem strony i gotowym, naturalnym hookiem sprzedażowym (PL lub DE).

---

## Wymagania
- Python 3.12+
- `uv` (rekomendowane) lub standardowy `pip`

---

## Instalacja

Szybka instalacja przy użyciu `uv`:
```bash
# Sklonuj repozytorium
git clone https://github.com/wulf-org/wulf-web-leader.git
cd wulf-web-leader

# Utwórz środowisko i zainstaluj paczkę
uv venv
uv pip install -e .
```

Albo przez klasyczny `pip`:
```bash
pip install -e .
```

Po instalacji masz dostępne główne polecenie **`wulf`** oraz wstecznie kompatybilne aliasy **`brakstrony`** i **`keinweb`**.

---

## Start — Dwa przykłady na start

Główna komenda CLI to **`lead.er`** (dostępna również jako **`leader`** oraz **`wulf`**).

### 1. Hydraulicy w Rzeszowie (promień 15 km)
Domyślny język to polski (`pl`), więc wystarczy jedno polecenie:
```bash
lead.er scan --country pl --miasto Rzeszów --vertical plumbers --radius 15
```
Możesz też użyć polskiego synonimu branży:
```bash
lead.er scan --country pl --city Rzeszów --vertical hydraulik --radius 15
```

### 2. Salony fryzjerskie w Dreźnie (promień 15 km)
Dla Niemiec podaj flagę `--country de` i język hooków `--lang de`:
```bash
lead.er scan --country de --city Dresden --vertical hair --radius 15 --lang de
```
Lub z niemieckim aliasem binarki i branży:
```bash
keinweb scan --country de --city Dresden --vertical friseur --radius 15 --lang de
```

### Błyskawiczne rozeznanie terenu (`--quick`)
Jeśli chcesz w 2 sekundy sprawdzić liczbę firm bez czekania na audyt sieciowy stron:
```bash
lead.er scan --country pl --city Kraków --vertical electricians --radius 20 --quick
```

### Tylko gorące leady z numerem telefonu (`--has-phone`, `--min-score`)
Od razu gotowa lista do obdzwonienia — bez zbędnych wpisów i bez firm bez kontaktu:
```bash
lead.er scan --country pl --miasto Rzeszów --vertical plumbers --radius 15 --has-phone --min-score 70
```

### Dyskowe buforowanie audytów stron (Cache)
Wyniki audytów stron www są automatycznie buforowane na dysku (`~/.cache/wulf-web-leader/audit_cache.json`) z okresem ważności 7 dni. Ponowne skanowanie tego samego rejonu pomija zbędne zapytania sieciowe.
Aby wymusić świeży audyt wszystkich stron i zaktualizować cache:
```bash
lead.er scan --country pl --miasto Rzeszów --vertical plumbers --no-cache
```

---

## Dostępne branże (Verticals)

Wszystkie definicje znajdują się w plikach YAML w katalogu `verticals/`.  
Aby wyświetlić listę wspieranych branż i ich polskich oraz niemieckich aliasów:
```bash
lead.er list-verticals
```

Wbudowane branże w standardzie:
- `plumbers` (`hydraulik`, `hydraulicy`, `instalator`, `klempner`, `sanitär`)
- `electricians` (`elektryk`, `elektrycy`, `usługi elektryczne`, `elektriker`)
- `hair` (`fryzjer`, `salon fryzjerski`, `barber`, `friseur`) — *ściśle salony fryzjerskie i barberzy*
- `auto_repair` (`mechanik`, `warsztat samochodowy`, `wulkanizacja`, `autowerkstatt`, `kfz`)
- `restaurant` (`restauracja`, `gastronomia`, `kawiarnia`, `pizzeria`, `restaurant`)
- `bakery` (`piekarnia`, `cukiernia`, `bäckerei`, `konditorei`)
- `veterinary` (`weterynarz`, `lecznica weterynaryjna`, `tierarzt`)
- `gym` (`siłownia`, `fitness`, `klub fitness`, `fitnessstudio`)

Możesz dodawać własne branże, tworząc nowy plik YAML w `verticals/` (np. `verticals/glazier.yaml`).

---

## Przegląd poleceń CLI

### `lead.er scan`
Skanuje miasto, geokoduje przez Nominatim, odpytuje OpenStreetMap przez Overpass, klasyfikuje domenę, opcjonalnie audytuje stronę HTTP i generuje pliki `leads.csv` oraz `leads.json`.

Opcje:
- `--country`, `-c`: Kod kraju (`pl` lub `de`, domyślnie `pl`).
- `--city`, `--miasto`: Nazwa miasta (np. `Rzeszów`, `Dresden`, `Poznań`).
- `--vertical`, `-v`: ID branży lub alias (np. `plumbers`, `hydraulik`, `hair`, `friseur`).
- `--radius`, `-r`: Promień w kilometrach (domyślnie `15.0`).
- `--lang`, `-l`: Język hooków sprzedażowych (`pl`, `de`, `en`, domyślnie `pl`).
- `--has-phone`: Filtruje tylko leady z dostępnym publicznym numerem telefonu.
- `--quick`, `--no-audit`: Pomija audyt HTTP stron (szybki zwiad).
- `--no-cache`, `--refresh-audit`: Pomija cache dyskowy i wymusza świeży audyt stron www.
- `--min-score`: Minimalna punktacja leada (od 0 do 100).
- `--delimiter`: Separator w pliku CSV (`comma` lub `semicolon`).
- `--out`, `-o`: Własna ścieżka do pliku lub katalogu wyjściowego.

### `lead.er audit`
Ponownie sprawdza dostępność i jakość stron z wcześniej zapisanego pliku `leads.json` (obsługuje również flagę `--no-cache` / `--refresh-audit`):
```bash
lead.er audit leads.json --lang pl
```

### `lead.er export`
Filtruje leady i generuje nowy plik CSV lub JSON:
```bash
lead.er export leads.json --min-score 70 --format csv --out leads_gorace.csv
```

### `lead.er report`
Generuje samodzielny, interaktywny raport HTML z ciemnym motywem, czytelnymi kartami firm i filtrami w czystym JavaScript (100% offline, bez serwera i bez zewnętrznych CDN-ów):
```bash
# Wygeneruj raport z pliku leads.json (domyślnie tworzy report.html w bieżącym katalogu)
lead.er report leads.json

# Otwórz wygenerowany raport w przeglądarce internetowej:
xdg-open report.html      # Linux
open report.html          # macOS
start report.html         # Windows
```
Raport pozwala na błyskawiczne filtrowanie leadów (HOT / WARM / SKIP), odfiltrowanie pozycji bez telefonu, wyszukiwanie po nazwie oraz otwieranie pozycji bezpośrednio na mapie OpenStreetMap.

### `lead.er web` (Nowoczesny Dashboard Web GUI)
Uruchamia lokalny, interaktywny serwer Web GUI (FastAPI + Uvicorn) z dark-themed dashboardem, wsparciem SSE (Server-Sent Events), automatycznym wykrywaniem wolnego portu, podglądem skanu na żywo oraz kartami firm:
```bash
# Uruchom interaktywny pulpit Web GUI (automatycznie otwiera przeglądarkę pod wolnym portem, np. http://127.0.0.1:8000 lub 8001)
lead.er web

# Opcjonalne parametry: zmiana portu lub hosta
lead.er web --port 8080 --host 0.0.0.0 --no-browser
```
Funkcje pulpitu Web GUI:
- Formularz kryteriów wyszukiwania (wybór kraju PL/DE z flagą, miasto, dynamiczna lista branż, suwak promienia 0–100 km, język hooków).
- Pasek postępu na żywo ze strumieniowaniem zdarzeń SSE i logami terminala.
- Karty leadów ze statusem technicznym, punktacją (HOT / WARM / SKIP) i gotowymi hookami.
- Modal z pełnym audytem technicznym (SSL, RWD, CMS, Impressum) i bezpośrednim przyciskiem weryfikacji w Google.
- Natychmiastowy eksport wyników do formatów CSV, JSON i HTML.

---

## Wielowymiarowy scoring i archetypy szans (0–100)

Koniec z monokulturą jednego błędu („brak strony www”). Narzędzie precyzyjnie rozpoznaje 6 różnych archetypów sytuacji rynkowej klienta ([`engine.py`](src/wulf_web_leader/score/engine.py)):

1. **Awaria witryny / Zaślepka hostingu (`broken_website`) — 85 pkt (HOT)**:
   Strona zwraca błędy HTTP 4xx, 5xx, timeout, błąd certyfikatu SSL, albo jest zaparkowaną domeną / nieaktywną zaślepką serwera (np. „strona w budowie”, domyślna plansza Apache/Nginx/Webmailer).
2. **Pilny redesign techniczny (`critical_redesign`) — 70–85 pkt (HOT)**:
   Strona działa, ale nie nadaje się na urządzenia mobilne (brak viewportu / RWD: +35 pkt), nie ma szyfrowania HTTPS (+15 pkt), korzysta z archaicznego CMS-a (Joomla, Drupal 7, stary edytor HTML: +15 pkt) lub brakuje wymaganego prawem Impressum w DE (+10 pkt).
3. **Tylko media społecznościowe (`social_only`) — 70 pkt (HOT)**:
   Firma posiada i aktywnie podaje wyłącznie profil na Facebooku lub Instagramie zamiast własnej witryny.
4. **Tylko wpis w katalogu (`directory_only`) — 65 pkt (WARM)**:
   Firma ma jedynie podpiętą wizytówkę w katalogu firm (Panorama Firm, Cylex, YellowPages itp.).
5. **Prawdopodobny brak strony www (`no_website`) — 70 pkt (HOT)**:
   Lokalny rzemieślnik / jednoosobowa działalność (JDG / Handwerker), dla której brak wpisu strony w rejestrach z wysokim prawdopodobieństwem oznacza brak witryny.
6. **Spółka kapitałowa do weryfikacji (`suspect_unverified`) — max 50 pkt (WARM / niski poziom pewności)**:
   Spółka prawa handlowego (GmbH, Sp. z o.o., AG), która nie posiada tagu www w OSM. Aby nie zaśmiecać listy priorytetowych telefonów (HOT), jej wynik jest obcięty do poziomu WARM (50 pkt z telefonem, 30 pkt bez telefonu). Karta otrzymuje ostrzeżenie oraz bezpośredni przycisk weryfikacji w Google.
7. **Sprawna, nowoczesna witryna (`modern_active`) — 0–30 pkt (SKIP)**:
   Strona działa poprawnie, jest responsywna, zabezpieczona certyfikatem SSL i posiada aktualne dane firmy.

---

## Tarcza Jakościowa QA i Weryfikacja Tożsamości Firmy

Aby wyeliminować fałszywe alarmy (np. Gustav Bonse w Brunszwiku mający domenę `bonse-bs.de`, czy Feldheim w Hanowerze pod domeną `feldheim-sanitaer-heizung.de`), `wulf-web-leader` wyposażony jest w wielopoziomowy moduł QA ([`verifier.py`](src/wulf_web_leader/audit/verifier.py)):

1. **Deterministyczny de-anonimizator domen (Vorwahl + Kfz-Kennzeichen w DE)**:
   W Niemczech rzemieślnicy masowo rejestrują domeny według wzorca `{nazwa}-{rejestracja}.de` (np. `bonse-bs.de`, bo prefiks `0531` to Brunszwik, kod Kfz `BS`). CLI analizuje prefiks kierunkowy telefonu i miasto, po czym w kilka milisekund sprawdza istnienie domen w DNS bez zewnętrznych wyszukiwarek i bez limitów.
2. **Oficjalny weryfikator Google Custom Search JSON API**:
   Obsługuje opcjonalne zmienne środowiskowe `GOOGLE_API_KEY` oraz `GOOGLE_CSE_ID` (100 darmowych zapytań dziennie). Gdy są ustawione, CLI automatycznie odpytuje oficjalne API Google dla niepewnych podmiotów i sprawdza tożsamość firmy na znalezionej stronie.
3. **Wyszukiwanie rezerwowe (DuckDuckGo Lite)**:
   Gdy brak klucza Google API, silnik wykonuje bezpieczne zapytanie pomocnicze o stronę główną przedsiębiorstwa.
4. **Weryfikator tożsamości podmiotu (`verify_entity_match`)**:
   Bada zgodność kluczowych tokenów nazwy, lokalnego numeru telefonu, miasta oraz ulicy z treścią strony www (próg akceptacji: min. 35–55%).
5. **Weryfikator zaślepek i parkingu (`check_is_placeholder`)**:
   Rozpoznaje domyślne plansze serwerowe, parkingi domen i szablony budowy w języku polskim, niemieckim i angielskim.
6. **Przycisk 1-Click „🔍 Sprawdź w Google” w Raporcie HTML**:
   Na każdej karcie firmy ze statusem `suspect_unverified` lub brakiem strony w OSM umieszczony jest bezpośredni przycisk otwierający dokładne zapytanie w wyszukiwarce Google.

W raporcie HTML i pliku CSV każda pozycja otrzymuje jawny status QA:
- `🟢 Zweryfikowano QA` — tożsamość firmy i działająca strona potwierdzone.
- `🟡 Zaślepka / Parking` — wykryto domenę ze statusem zaślepki serwera (awaria strony, wysoki priorytet naprawy).
- `🔴 Mismatch tożsamości` — domena w rejestrze nie zawiera danych tej firmy.
- `⚪ Brak weryfikacji` — brak witryny w rejestrach (do zweryfikowania 1-klikiem w Google).

---

## Specyfika i ograniczenia danych OpenStreetMap (OSM)

Dane w `wulf-web-leader` pochodzą z otwartej bazy OpenStreetMap tworzonej przez społeczność. Zrozumienie jej specyfiki pozwala oszczędzić czas i precyzyjnie dobrać parametry skanowania:

1. **Dobór promienia poszukiwań (`--radius`):**
   - **Duże aglomeracje** (np. Kraków, Warszawa, Wrocław, Drezno): promień **5–15 km** daje zazwyczaj od kilkudziesięciu do kilkuset trafień.
   - **Mniejsze miasta i powiaty** (np. Rzeszów, Krosno, Dębica, Łańcut): warto ustawić promień **20–30 km**, aby objąć okoliczne gminy, strefy podmiejskie i lokalne warsztaty.
2. **Brak telefonu w bazie OSM (`phone = None`):**
   - Brak numeru w OpenStreetMap **nie oznacza, że firma nie istnieje ani że nie ma telefonu**. Oznacza to jedynie, że osoba nanosząca punkt na mapę nie wpisała tagu `contact:phone`.
   - Takie firmy otrzymują u nas 50 punktów i werdykt **WARM**. Jeśli chcesz mieć od razu gotową listę do bezpośredniego dzwonienia, użyj flagi `--has-phone`.
3. **Gęstość danych zależy od branży:**
   - Branże posiadające widoczny szyld i warsztat stacjonarny (`auto_repair`, `hair`, `bakery`, `restaurant`) mają w OSM bardzo wysokie pokrycie (w jednym skanie potrafi wrócić kilkadziesiąt leadów HOT).
   - Branże mobilne i instalatorskie (`plumbers`, `electricians`) często mają mniej punktów stacjonarnych w OSM — 1–3 leady HOT w mniejszym mieście to zjawisko całkowicie normalne, a nie błąd narzędzia.

---

## Zasady i etyka (Czego to narzędzie NIE robi — Reguły PR)

1. **Zero masowych maili / spamu (WF.1)**: Narzędzie nie posiada i nigdy nie będzie posiadać modułu masowej wysyłki maili (brak SMTP, brak sequencerów). To baza pod bezpośredni kontakt ludzki. Pull Requesty dodające wysyłkę e-mail są bezwzględnie odrzucane.
2. **Google Maps NIE jest rdzeniem (WF.1)**: Nie scrapujemy Google Maps. Zapobiega to łamaniu regulaminów, blokadom IP i niestabilności. Dane bazują na otwartych źródłach (OSM).
3. **Zero scrapowania handelsregister.de na żywo (WF.1 / WE.1)**: Niemiecki rejestr handlowy nie ma otwartego API. Wszelkie wzbogacanie danych opiera się wyłącznie na legalnych lokalnych zrzutach SQLite (OffeneRegister).
4. **Zero chmury, SaaS i telemetrii (WF.2)**: Narzędzie działa w 100% lokalnie w terminalu. W repozytorium nie ma i nie będzie frameworków serwerowych, backendu chmurowego ani analityki.
5. **Zamrożenie na 8 kluczowych branżach (WF.2)**: Zamiast 40 niedopracowanych kategorii, dbamy o precyzję tagów OSM i kodów PKD/WZ w 8 bazowych branżach.
6. **Szanowanie limitów API**: Nominatim jest odpytywany z limitem min. 1 sekundy i lokalnym cache w `~/.cache/wulf-web-leader/`. Zapytania Overpass są ograniczone do niezbędnych pól (`out center tags qt`).

Pełne wytyczne architektoniczne i standardy kodowania znajdziesz w pliku [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Prawa autorskie i atrybucja danych (ODbL)

Dane pobierane przez narzędzie pochodzą ze społeczności **OpenStreetMap** za pośrednictwem Nominatim i Overpass API.  
Zgodnie z licencją [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/):
- **Data © OpenStreetMap contributors under ODbL 1.0**

Pliki CSV generowane są z kodowaniem `utf-8-sig`, dzięki czemu otwierają się poprawnie w programie Microsoft Excel z polskimi (`ą, ć, ę, ł, ń, ó, ś, ź, ż`) oraz niemieckimi (`ä, ö, ü, ß`) znakami diakrytycznymi.

---

## Licencja

MIT License. Szczegóły w pliku [LICENSE](LICENSE).
