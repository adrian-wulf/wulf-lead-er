# Zasady współtworzenia (Contributing Guidelines) — wulf-web-leader

Dziękujemy za chęć rozwoju projektu `wulf-web-leader` (CLI: `wulf`, aliasy: `brakstrony`, `keinweb`).  
Projekt powstał jako narzędzie typu **Robin Hood dla lokalnych twórców stron www** — w 100% lokalne, otwarte (MIT), zorientowane na jakość i szacunek dla prywatności oraz prawa.

Aby projekt zachował swoją tożsamość i lekkość, każdy Pull Request musi spełniać poniższe reguły architektoniczne.

---

## Wiążące reguły architektoniczne (Zasady odrzucania PR)

Wszystkie Pull Requesty naruszające poniższe punkty będą **bezwzględnie odrzucane bez dyskusji**:

### 1. Bezwzględny zakaz scrapowania Google Maps (WF.1)
- **Reguła**: Nigdy nie implementujemy scrapera Google Maps / Google Places jako źródła danych.
- **Uzasadnienie**: Złamanie Terms of Service Google, ryzyko prawne, bany adresów IP, niestabilność selektorów i zanieczyszczenie architektury.
- **Źródło prawdy**: Rdzeniem pozostaje otwarta baza **OpenStreetMap (OSM)** przez Nominatim i Overpass API.

### 2. Bezwzględny zakaz modułów masowej wysyłki maili i spamu (WF.1)
- **Reguła**: W repozytorium nie ma i nigdy nie będzie modułów wysyłki wiadomości e-mail: brak SMTP, brak sequencerów cold-mailowych, brak webhooków do narzędzi mailowych.
- **Uzasadnienie**: Narzędzie tworzy bazę do kontaktu bezpośredniego (telefon, wizyta osobista, dedykowana prezentacja), nie spam-maszynę. Chronimy reputację twórców oraz przestrzegamy przepisów o ochronie prywatności (RODO, UODO, niemieckie UWG).

### 3. Bezwzględny zakaz scrapowania handelsregister.de na żywo (WF.1 / WE.1)
- **Reguła**: Brak zapytań live-scrapujących portal `handelsregister.de`.
- **Uzasadnienie**: Niemiecki rejestr handlowy nie posiada publicznego bezpłatnego API i aktywnie blokuje scraping. Wszelkie wzbogacanie danych niemieckich podmiotów opiera się wyłącznie na legalnych, lokalnych zrzutach SQLite (projekt OffeneRegister).

### 4. Zakaz aplikacji chmurowych, SaaS, GUI i telemetrii (WF.2)
- **Reguła**: `wulf-web-leader` jest i pozostanie w 100% **local-first CLI**.
- **Wymóg techniczny**: W `pyproject.toml` nie dodajemy zależności serwerowych (Django, FastAPI, Flask, Celery, SQLAlchemy, bazy danych w chmurze, Firebase, Supabase).
- **Zero telemetrii**: Zero analityki, wysyłania pingów, zbierania logów użytkowników czy rejestracji kont.

### 5. Zamrożenie na 8 bazowych gałęziach branżowych (WF.2)
- **Reguła**: Zamiast dodawać 40 powierzchownych branż, skupiamy się na bezbłędnej jakości i tagach w 8 kluczowych branżach:
  `plumbers`, `electricians`, `hair`, `auto_repair`, `restaurant`, `bakery`, `veterinary`, `gym`.
- Nowe branże mogą być dodawane wyłącznie lokalnie przez użytkownika w plikach `verticals/*.yaml`.

---

## Standardy techniczne i workflow

1. **Język dokumentacji i CLI**:
   - Dokumentacja (`README.md`, `TODO.md`, `CHECKLIST_RELEASE.md`, `docs/*.md`) jest prowadzona **wyłącznie w języku polskim**.
   - Domyślny język flagi `--lang` to `pl`.
2. **Jakość kodu i testy**:
   - Każda zmiana w kodzie musi posiadać dedykowany zestaw testów `pytest`.
   - Przed wystawieniem PR cały zestaw testów musi przechodzić bezbłędnie:
     ```bash
     pytest -q
     ```
3. **Determinizm scoringu**:
   - Punktacja (0–100) i werdykty (`hot`, `warm`, `skip`) muszą być w pełni powtarzalne i deterministyczne.
   - W hookach sprzedażowych zabronione jest używanie agresywnego języka prawnego, gróźb kar (np. brak słów *Abmahnung*, *kara*, *pozew*).
4. **Kodowanie plików wyjściowych**:
   - Wszystkie eksporty CSV muszą być zapisywane z kodowaniem `utf-8-sig` w celu zapewnienia kompatybilności z arkuszami kalkulacyjnymi (Excel, LibreOffice Calc).
