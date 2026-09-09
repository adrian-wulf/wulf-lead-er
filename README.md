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

### 1. Hydraulicy w Rzeszowie (promień 15 km)
Domyślny język to polski (`pl`), więc wystarczy jedno polecenie:
```bash
wulf scan --country pl --miasto Rzeszów --vertical plumbers --radius 15
```
Możesz też użyć polskiego synonimu branży:
```bash
wulf scan --country pl --city Rzeszów --vertical hydraulik --radius 15
```

### 2. Salony fryzjerskie w Dreźnie (promień 15 km)
Dla Niemiec podaj flagę `--country de` i język hooków `--lang de`:
```bash
wulf scan --country de --city Dresden --vertical hair --radius 15 --lang de
```
Lub z niemieckim aliasem binarki i branży:
```bash
keinweb scan --country de --city Dresden --vertical friseur --radius 15 --lang de
```

### Błyskawiczne rozeznanie terenu (`--quick`)
Jeśli chcesz w 2 sekundy sprawdzić liczbę firm bez czekania na audyt sieciowy stron:
```bash
wulf scan --country pl --city Kraków --vertical electricians --radius 20 --quick
```

### Tylko firmy z numerem telefonu (`--has-phone`)
Od razu gotowa lista do obdzwonienia:
```bash
wulf scan --country pl --city Rzeszów --vertical plumbers --radius 15 --has-phone
```

---

## Dostępne branże (Verticals)

Wszystkie definicje znajdują się w plikach YAML w katalogu `verticals/`.  
Aby wyświetlić listę wspieranych branż i ich polskich oraz niemieckich aliasów:
```bash
wulf list-verticals
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

### `wulf scan`
Skanuje miasto, geokoduje przez Nominatim, odpytuje OpenStreetMap przez Overpass, klasyfikuje domenę, opcjonalnie audytuje stronę HTTP i generuje pliki `leads.csv` oraz `leads.json`.

Opcje:
- `--country`, `-c`: Kod kraju (`pl` lub `de`, domyślnie `pl`).
- `--city`, `--miasto`: Nazwa miasta (np. `Rzeszów`, `Dresden`, `Poznań`).
- `--vertical`, `-v`: ID branży lub alias (np. `plumbers`, `hydraulik`, `hair`, `friseur`).
- `--radius`, `-r`: Promień w kilometrach (domyślnie `15.0`).
- `--lang`, `-l`: Język hooków sprzedażowych (`pl`, `de`, `en`, domyślnie `pl`).
- `--has-phone`: Filtruje tylko leady z dostępnym publicznym numerem telefonu.
- `--quick`, `--no-audit`: Pomija audyt HTTP stron (szybki zwiad).
- `--min-score`: Minimalna punktacja leada (od 0 do 100).
- `--delimiter`: Separator w pliku CSV (`comma` lub `semicolon`).
- `--out`, `-o`: Własna ścieżka do pliku lub katalogu wyjściowego.

### `wulf audit`
Ponownie sprawdza dostępność i jakość stron z wcześniej zapisanego pliku `leads.json`:
```bash
wulf audit leads.json --lang pl
```

### `wulf export`
Filtruje leady i generuje nowy plik CSV lub JSON:
```bash
wulf export leads.json --min-score 70 --format csv --out leads_gorace.csv
```

---

## Skrót scoringu (0–100)

Silnik punktacji jest w 100% deterministyczny ([`engine.py`](src/wulf_web_leader/score/engine.py)):
- **+50 pkt**: Brak jakiejkolwiek strony www (`website_kind == "none"`)
- **+35 pkt**: Tylko profil w mediach społecznościowych lub katalogu (`facebook`, `instagram`, `directory`)
- **+20 pkt**: Publiczny numer telefonu w wizytówce (bezpośrednia możliwość kontaktu)
- **+40 pkt**: Domena widnieje w bazie, ale strona jest całkowicie martwa / nieosiągalna
- **+15 pkt**: Strona nie ma viewportu (nieczytelna na smartfonach)
- **+10 pkt**: Brak szyfrowania HTTPS (tylko HTTP)
- **+10 pkt**: Przestarzały szablon/CMS (np. stary Joomla, Drupal 7)
- **-100 pkt**: Firma oznaczona jako wyrejestrowana / nieaktywna

**Werdykty:**
- **HOT** (Wynik ≥ 70): Idealny kandydat na telefon (np. brak strony + publiczny numer telefonu).
- **WARM** (Wynik ≥ 45): Warty uwagi (np. tylko profil na Facebooku z numerem lub brak strony bez podanego telefonu).
- **SKIP** (Wynik < 45): Posiada działającą, responsywną stronę www.

---

## Zasady i etyka (Czego to narzędzie NIE robi)

1. **Zero masowych maili / spamu**: Narzędzie nie posiada i nigdy nie będzie posiadać modułu masowej wysyłki maili (brak SMTP, brak sequencerów). To baza pod kontakt ludzki.
2. **Google Maps NIE jest rdzeniem**: Nie scrapujemy Google Maps. Zapobiega to łamaniu regulaminów, blokadom IP i niestabilności. Dane bazują na otwartych źródłach.
3. **Zero scrapowania handelsregister.de na żywo**: Niemiecki rejestr handlowy nie ma otwartego API do masowych zapytań na żywo. Wzbogacanie danych w v1.1 opiera się na otwartych zrzutach OffeneRegister (offline SQLite/JSON).
4. **Zero chmury i telemetrii**: Narzędzie działa lokalnie na Twojej maszynie. Nie wysyła żadnych danych analitycznych ani logów.
5. **Szanowanie limitów API**: Nominatim jest odpytywany z limitem min. 1 sekundy i lokalnym cache w `~/.cache/wulf-web-leader/`. Zapytania Overpass są ograniczone do niezbędnych pól (`out center tags qt`).

---

## Prawa autorskie i atrybucja danych (ODbL)

Dane pobierane przez narzędzie pochodzą ze społeczności **OpenStreetMap** za pośrednictwem Nominatim i Overpass API.  
Zgodnie z licencją [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/):
- **Data © OpenStreetMap contributors under ODbL 1.0**

Pliki CSV generowane są z kodowaniem `utf-8-sig`, dzięki czemu otwierają się poprawnie w programie Microsoft Excel z polskimi (`ą, ć, ę, ł, ń, ó, ś, ź, ż`) oraz niemieckimi (`ä, ö, ü, ß`) znakami diakrytycznymi.

---

## Licencja

MIT License. Szczegóły w pliku [LICENSE](LICENSE).
