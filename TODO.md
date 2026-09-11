# TODO — Plan Rozwoju wulf-web-leader

Plan wdrożeń i weryfikacji dla ekipy tworzącej strony www w Polsce i Niemczech.  
Każde zadanie to zamknięty zakres na jedną sesję programistyczną lub jeden wieczór operacyjny.

---

## Teraz (zanim nowy kod)

### W0.1 Terenowa weryfikacja 20 leadów HOT z v0.1 (Pilot terenowy) [P0]
- **Po co**: Sprawdzić w realnym kontakcie telefonicznym/terenowym, czy leady oznaczone przez v0.1 jako HOT (wynik ≥ 70) to faktycznie istniejące firmy bez stron www, czy martwe wpisy z OSM.
- **Scope**: Uruchomienie skanów (`wulf scan --miasto Rzeszów --vertical plumbers --has-phone --min-score 70` oraz dla Drezna `--vertical hair --lang de`), wykonanie min. 20 prób weryfikacji telefonicznej lub rejestrowej.
- **Poza scope**: Pisanie nowego kodu, refaktoryzacja algorytmów.
- **Definition of done**: Notatka z 20 zweryfikowanych pozycji z oceną: trafiony / fałszywy (wraz z przyczyną: firma zamknięta, zły numer, strona istnieje pod inną domeną).
- **Zależności**: brak
- **Szacunek**: M (1 sesja operacyjna ekipy)

### W0.2 Rejestr fałszywych trafień i kalibracja wag scoringu
- **Po co**: Zgromadzić faktyczną wiedzę o powodach błędnych ocen scoringu, aby kolejne zmiany w kodzie opierały się na danych z terenu, a nie domysłach.
- **Scope**: Utworzenie dokumentu `docs/false_positives.md` klasyfikującego typowe pułapki (np. salon kosmetyczny podpięty pod fryzjera, portal ogłoszeniowy jako telefon).
- **Poza scope**: Modyfikowanie wag w `src/wulf_web_leader/score/engine.py`.
- **Definition of done**: Plik `docs/false_positives.md` z min. 5 opisanymi wzorcami fałszywych trafień zebranymi podczas weryfikacji W0.1.
- **Zależności**: W0.1
- **Szacunek**: S

---

## Etap A — stabilizacja v0.1

### WA.1 Higiena repozytorium, wersjonowanie i release checklist
- **Po co**: Uporządkować metadane projektu, zweryfikować reguły `.gitignore` i ustalić powtarzalną procedurę wydań.
- **Scope**: `pyproject.toml` (wersja 0.1.0, metadane), `.gitignore` (izolacja `.cache/`, `leads*.csv`, `leads*.json`), utworzenie `CHECKLIST_RELEASE.md`.
- **Poza scope**: Zmiany w silniku skanowania i audytu.
- **Definition of done**: Czyste środowisko po instalacji przez `uv pip install -e .`, polecenie `python -m build` tworzy poprawny pakiet kołowy (wheel), checklist wydania gotowy.
- **Zależności**: brak
- **Szacunek**: S

### WA.2 Komunikaty błędów sieci i diagnostyka pustych wyników w CLI
- **Po co**: Wyświetlać czytelne polskie komunikaty w terminalu, gdy Overpass rzuci błędem timeoutu lub gdy w zadanym promieniu nie znaleziono żadnej firmy.
- **Scope**: `src/wulf_web_leader/cli.py`, `src/wulf_web_leader/pipeline.py` (obsługa wyjątków sieciowych i podpowiedzi dla użytkownika w tabeli Rich).
- **Poza scope**: Dodawanie nowych źródeł danych, zmiany w modelach danych.
- **Definition of done**: Testy symulujące awarię Overpass i brak wyników sprawdzają obecność polskich podpowiedzi w konsoli (zwiększ promień, sprawdź pisownię) bez zrzucania surowego tracebacku Pythona.
- **Zależności**: brak
- **Szacunek**: S

### WA.3 Uzupełnienie dokumentacji o specyfikę i ograniczenia OSM
- **Po co**: Wyjaśnić ekipie, jak radzić sobie z lukami w danych adresowych i telefonicznych w zależności od wielkości miejscowości.
- **Scope**: `README.md` (sekcja o specyfice danych OpenStreetMap w Polsce i Niemczech, zalecane promienie poszukiwań i interpretacja braków telefonów).
- **Poza scope**: Tłumaczenia dokumentacji na inne języki, zmiany w kodzie.
- **Definition of done**: W `README.md` znajduje się sekcja opisująca realne ograniczenia otwartych danych oraz zalecenia doboru parametrów `--radius` w aglomeracjach vs małych miastach.
- **Zależności**: W0.1
- **Szacunek**: S

---

## Etap B — jakość leadów

### WB.1 Filtracja wygasłych i zamkniętych POI w zapytaniach OSM
- **Po co**: Wyeliminować z wyników firmy zlikwidowane, zamknięte na stałe lub oznaczone w OSM jako nieczynne.
- **Scope**: `src/wulf_web_leader/adapters/osm.py` (wykluczenie tagów `disused=*`, `abandoned=*`, `closed=*`, `opening_hours=closed` oraz prefixów `disused:`).
- **Poza scope**: Zapytania do zewnętrznych rejestrów KRS/CEIDG.
- **Definition of done**: Test jednostkowy z fixturą węzła z tagiem `disused:shop=hairdresser` potwierdza, że wpis jest odrzucany na etapie parsowania.
- **Zależności**: WA.2
- **Szacunek**: S

### WB.2 Rozszerzona klasyfikacja podstron i wizytówek (platformy i katalogi)
- **Po co**: Zapobiec traktowaniu profili na Booksy, ZnanyLekarz, Oferteo, OLX czy Google Business Site jako własnej, niezależnej strony www.
- **Scope**: `src/wulf_web_leader/audit/classifier.py` (dodanie wzorców domen `*.business.site`, `booksy.com`, `oferteo.pl`, `znanylekarz.pl`, `olx.pl`, `allegro.pl`).
- **Poza scope**: Zmiany w logice pobierania HTTP (`fetch.py`).
- **Definition of done**: Testy jednostkowe w `tests/test_classifier.py` potwierdzają klasyfikację wymienionych platform jako `directory` lub `other`, a nie `own`.
- **Zależności**: W0.2
- **Szacunek**: S

### WB.3 Zaostrzenie definicji tagów OSM w pozostałych branżach `verticals/`
- **Po co**: Usunąć nadmiarowe, zbyt szerokie tagi ściągające niepowiązane punkty w pozostałych 7 branżach (wzorem naprawionego `hair.yaml`).
- **Scope**: Pliki w katalogu `verticals/*.yaml` (analiza i zawężenie tagów w polach `osm:`).
- **Poza scope**: Dodawanie nowych plików branżowych, zmiany w kodzie parsera.
- **Definition of done**: Test jednostkowy weryfikujący poprawność struktury wszystkich definicji YAML oraz brak tagów ogólnych (np. `shop=car` w warsztatach mechanicznych).
- **Zależności**: W0.1
- **Szacunek**: M

### WB.4 Usprawnienie normalizacji i deduplikacji leadów wewnątrz miasta
- **Po co**: Zapobiec dublowaniu firm wprowadzonych do OSM jednocześnie jako punkt węzłowy (node) i obrys budynku (way) z drobnymi rozbieżnościami w nazwie.
- **Scope**: `src/wulf_web_leader/adapters/osm.py` (funkcja normalizacji nazwy handlowej i reguły scalania po numerze telefonu w promieniu 100m).
- **Poza scope**: Rozbudowane zewnętrzne algorytmy dopasowywania rozmytego (fuzzy matching).
- **Definition of done**: Test jednostkowy potwierdzający scalenie dwóch elementów OSM (node i way) o identycznym numerze telefonu i zbliżonej nazwie do jednego `CanonicalLead`.
- **Zależności**: WB.1
- **Szacunek**: S

---

## Etap C — workflow ekipy

### WC.1 Rozszerzenie eksportu CSV o pełne dane adresowe i pola statusu kontaktu
- **Po co**: Umożliwić osobie dzwoniącej prowadzenie notatek i oznaczanie statusu rozmowy bezpośrednio w wygenerowanym arkuszu bez ręcznego dodawania kolumn.
- **Scope**: `src/wulf_web_leader/export/writer.py`, `src/wulf_web_leader/models.py` (dodanie kolumn: `street`, `postcode`, `status_kontaktu`, `notatki`, `data_kontaktu`).
- **Poza scope**: Własny backend CRM, baza danych SQLite/PostgreSQL.
- **Definition of done**: Plik CSV zawiera nowe kolumny adresowe i puste kolumny operacyjne, a testy potwierdzają integralność formatu `utf-8-sig`.
- **Zależności**: WA.1
- **Szacunek**: S

### WC.2 Komenda pomocnicza segregacji i podziału leadów (`wulf filter`)
- **Po co**: Ułatwić podział bazy na mniejsze pakiety robocze (np. „do obdzwonienia dzisiaj”, „wyłącznie z komórką”).
- **Scope**: `src/wulf_web_leader/cli.py` (komenda CLI filtrująca zapisany wcześniej plik `leads.json` i eksportująca wynik pod nową nazwę).
- **Poza scope**: Sekwencery korespondencji, cold-mailing.
- **Definition of done**: Polecenie `wulf filter leads.json --min-score 70 --has-phone --out dzis.csv` działa bez odpytywania sieci i posiada test jednostkowy CLI.
- **Zależności**: WC.1
- **Szacunek**: S

### WC.3 Generator szkieletu demo one-pager (`wulf demo-template`)
- **Po co**: Wygenerować w 5 sekund prosty, responsywny plik demonstracyjny HTML z podstawioną nazwą firmy, branżą i telefonem, by pokazać go klientowi podczas rozmowy.
- **Scope**: Nowe podpolecenie CLI generujące lokalny plik `index.html` na podstawie szablonu branżowego.
- **Poza scope**: Hosting w chmurze, automatyczne wdrażanie stron, wysyłka linków do klienta.
- **Definition of done**: Polecenie tworzy statyczny plik HTML dla wskazanego leada z poprawnie podstawioną nazwą firmy i danymi kontaktowymi.
- **Zależności**: WC.1
- **Szacunek**: M

---

## Etap D — Polska (CEIDG)

### WD.1 Klient Hurtowni CEIDG z obsługą braku tokena (no-op)
- **Po co**: Umożliwić weryfikację aktywności jednoosobowych działalności gospodarczych w oficjalnym API bez wymuszania posiadania tokena na każdym użytkowniku.
- **Scope**: `src/wulf_web_leader/adapters/pl_ceidg.py` (odczyt zmiennej środowiskowej `CEIDG_API_TOKEN`, zapytanie HTTP z nagłówkiem autoryzacji).
- **Poza scope**: Scrapowanie strony ceidg.gov.pl, rejestracja kont użytkowników.
- **Definition of done**: Gdy zmienna `CEIDG_API_TOKEN` nie jest ustawiona, adapter jest pomijany bez żadnego błędu; z mockowanym tokenem wykonuje prawidłowe zapytanie testowe.
- **Zależności**: WA.2
- **Szacunek**: M

### WD.2 Scalanie danych OSM z danymi CEIDG (status firmy i PKD)
- **Po co**: Zdyskwalifikować firmy wyrejestrowane lub zawieszone (werdykt `skip`) oraz zweryfikować zgodność branży po kodzie PKD.
- **Scope**: `src/wulf_web_leader/adapters/pl_ceidg.py`, `src/wulf_web_leader/pipeline.py`.
- **Poza scope**: Modyfikacja modelu podstawowego `CanonicalLead`.
- **Definition of done**: Test jednostkowy: firma oznaczona w mocku CEIDG jako zawieszona otrzymuje wynik 0 i werdykt `skip`.
- **Zależności**: WD.1, WB.4
- **Szacunek**: M

### WD.3 Zabezpieczenie limitów zapytań CEIDG i testy offline
- **Po co**: Chronić klucz użytkownika przed przekroczeniem limitów zapytaniowych (rate limit) i umożliwić testowanie bez dostępu do sieci.
- **Scope**: `src/wulf_web_leader/adapters/pl_ceidg.py` (ogranicznik zapytań max 3 req/s, obsługa odpowiedzi HTTP 429).
- **Poza scope**: Obsługa zewnętrznych płatnych proxy.
- **Definition of done**: Testy jednostkowe z mockami HTTP potwierdzają prawidłowe zachowanie przy kodach błędu 429 i 503 (cichy powrót do danych z OSM).
- **Zależności**: WD.2
- **Szacunek**: S

---

## Etap E — Niemcy (OffeneRegister & Impressum)

### WE.1 Wzbogacanie danych z lokalnego zrzutu SQLite OffeneRegister
- **Po co**: Zweryfikować status prawny niemieckich podmiotów (GmbH, UG) z otwartego zrzutu danych bez ryzykownego scrapowania portalu handelsregister.de.
- **Scope**: `src/wulf_web_leader/adapters/de_offeneregister.py` (odczyt lokalnego pliku bazy SQLite wskazanego w konfiguracji/fladze).
- **Poza scope**: Automatyczne pobieranie wielogigabajtowych archiwów z Internetu, live-scraping niemieckich rejestrów sądowych.
- **Definition of done**: Test jednostkowy na miniaturowej testowej bazie SQLite poprawnie odczytuje status podmiotu; brak pliku bazy skutkuje natychmiastowym pominięciem (no-op).
- **Zależności**: WA.2
- **Szacunek**: M

### WE.2 Pasywny audyt Impressum jako sygnał porzuconej witryny
- **Po co**: Wykryć niemieckie strony pozbawione danych kontaktowych właściciela (Impressum), co wskazuje na witrynę amatorską lub zaniedbaną.
- **Scope**: `src/wulf_web_leader/audit/parser.py`, `src/wulf_web_leader/score/engine.py` (detekcja linków do Impressum jako element audytu technicznego).
- **Poza scope**: Formułowanie gróźb prawnych, straszenie karami czy powoływanie się na przepisy prawne w generowanych hookach.
- **Definition of done**: Test jednostkowy potwierdza, że brak Impressum dodaje punkty do wyniku jakości witryny, a wygenerowany hook pozostaje neutralny i czysto biznesowy.
- **Zależności**: WB.2
- **Szacunek**: S

---

## Etap F — świadomie później / nie robić

### WF.1 Świadomie odrzucone: Scraping Google Maps i moduły masowej wysyłki maili
- **Po co**: Ochronić narzędzie przed banami IP, ryzykiem prawnym (RODO/UODO/UWG) oraz degeneracją w spam-maszynę.
- **Scope**: Bezwzględny zakaz implementacji scraperów Google Maps oraz masowych wysyłek e-mail (SMTP/sekwencery).
- **Poza scope**: N/A (reguła architektoniczna).
- **Definition of done**: Zasada zapisana w dokumentacji jako wiążący warunek odrzucania pull requestów naruszających ten punkt.
- **Zależności**: brak
- **Szacunek**: S

### WF.2 Świadomie odłożone: Aplikacja GUI/SaaS, chmura i baza 40 branż naraz
- **Po co**: Zachować 100% koncentracji na jakości danych w 8 bazowych branżach i komforcie pracy w terminalu zamiast budować zbędną infrastrukturę chmurową.
- **Scope**: Utrzymanie narzędzia jako 100% local-first CLI na licencji MIT, bez logowania, bez baz danych w chmurze i bez telemetrii.
- **Poza scope**: N/A (decyzja architektoniczna).
- **Definition of done**: Brak zależności serwerowych i zewnętrznych baz danych w pliku `pyproject.toml`.
- **Zależności**: brak
- **Szacunek**: S

---

## Kolejka wdrożeń (Najbliższe 5 zadań)

1. **W0.1** [P0] Terenowa weryfikacja 20 leadów HOT z v0.1 (Pilot Rzeszów / Drezno)
2. **W0.2** Rejestr fałszywych trafień i kalibracja wag scoringu
3. **WA.1** Higiena repozytorium, wersjonowanie i release checklist
4. **WA.2** Komunikaty błędów sieci i diagnostyka pustych wyników w CLI
5. **WB.1** Filtracja wygasłych i zamkniętych POI w zapytaniach OSM
