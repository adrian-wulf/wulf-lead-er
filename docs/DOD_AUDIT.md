# Audyt Definition of Done (DoD) — wulf-web-leader

Data audytu: 2026-09-09  
Wersja projektu: v0.3.0  
Audytor: Finisher & Auditor Agent  
Status ogólny: **100% PASS (Zero GAP)**

Wszystkie wymagania z `TODO.md` zostały zweryfikowane na podstawie twardych dowodów w kodzie, testach automatycznych (57 testów green) oraz dokumentacji.

---

## Tabela Weryfikacji Wymagań (DoD)

| ID | Zadanie z TODO.md | Status | Ścieżka pliku | Nazwa testu / Dowód | Opis dowodu |
|---|---|:---:|---|---|---|
| **W0.1** | Terenowa weryfikacja 20 leadów HOT z v0.1 | **PASS** | `docs/pilot_w01.md`, `docs/pilot_w01_arkusz.csv` | Realne skany (Rzeszów, Krosno, Dębica) | Wygenerowano arkusz 20 unikalnych leadów HOT z numerem telefonu z pustymi kolumnami na dane z terenu. |
| **W0.2** | Rejestr fałszywych trafień i kalibracja wag | **PASS** | `docs/false_positives.md` | Rejestr 5 wzorców | Udokumentowano 5 wzorców fałszywych trafień z testami detekcji; wagi w `engine.py` nie były zmieniane. |
| **WA.1** | Higiena repozytorium, wersjonowanie i release checklist | **PASS** | `pyproject.toml`, `.gitignore`, `CHECKLIST_RELEASE.md` | `python -m build` | Wersja 0.3.0, wheel zbudowany poprawnie, izolacja cache/leadów/dist w `.gitignore`, procedura release gotowa. |
| **WA.2** | Komunikaty błędów sieci i diagnostyka pustych wyników | **PASS** | `src/wulf_web_leader/cli.py`, `tests/test_cli_errors.py` | `test_cli_error_invalid_city`, `test_cli_error_overpass_timeout`, `test_cli_zero_results` | Puste wyniki, błędy Overpass i brak miasta wypisują polski tekst bez surowego Tracebacka. |
| **WA.3** | Ograniczenia danych OSM w dokumentacji | **PASS** | `README.md` | Sekcja „Specyfika i ograniczenia danych OpenStreetMap” | Opisano dobór promienia wyszukiwania (5-15 km aglomeracje, 20-30 km region), interpretację braku telefonu i gęstość branż. |
| **WB.1** | Filtracja wygasłych i zamkniętych POI | **PASS** | `src/wulf_web_leader/adapters/osm.py`, `tests/test_osm_dead_pois.py` | `test_osm_filter_disused_and_dead_pois` | Parser ignoruje obiekty z tagami `disused:*`, `abandoned:*`, `closed=*`, `opening_hours=closed`. |
| **WB.2** | Klasyfikacja domen katalogowych i platformowych | **PASS** | `src/wulf_web_leader/audit/classifier.py`, `tests/test_classifier.py` | `test_classify_directory` | Domeny `business.site`, `booksy.com`, `oferteo.pl`, `znanylekarz.pl`, `olx.pl`, `allegro.pl` klasyfikowane jako `directory` (nie `own`). |
| **WB.3** | Ujednolicenie tagów we wszystkich verticals/*.yaml | **PASS** | `verticals/*.yaml`, `tests/test_verticals_tags.py` | `test_verticals_strict_tag_hygiene` | Zakaz `shop=car` w `auto_repair`, brak `shop=beauty` we wszystkich plikach, `hair` ograniczony do `shop=hairdresser`. |
| **WB.4** | Deduplikacja obiektów w mieście (Node vs Way) | **PASS** | `src/wulf_web_leader/adapters/osm.py`, `tests/test_osm_dedupe.py` | `test_osm_dedupe_node_and_way` | Obiekty o tym samym telefonie w odległości ~100 m są scalane w jeden lead z zachowaniem adresu. |
| **WC.1** | Rozszerzenie CSV o kolumny operacyjne i adresowe | **PASS** | `src/wulf_web_leader/export/writer.py`, `tests/test_export_columns.py` | `test_export_leads_to_csv_operational_columns` | Kolumny `street`, `postcode`, `status_kontaktu`, `notatki`, `data_kontaktu` obecne w CSV zakodowanym w `utf-8-sig`. |
| **WC.2** | Pomocnicze filtrowanie bazy leadów (`wulf filter`) | **PASS** | `src/wulf_web_leader/cli.py`, `tests/test_cli_filter.py` | `test_wulf_filter_cli_command` | Polecenie `wulf filter leads.json --min-score 70 --has-phone --out dzis.csv` filtruje plik bez ani jednego zapytania sieciowego. |
| **WC.3** | Generator szkieletu demo one-pager (`wulf demo-template`) | **PASS** | `src/wulf_web_leader/export/demo.py`, `tests/test_demo_template.py` | `test_wulf_demo_template_cli_default_index_html`, `test_generate_demo_html_function` | Polecenie generuje responsywny plik HTML (domyślnie `index.html`) z podstawioną nazwą firmy, branżą i numerem telefonu. |
| **WD.1** | Klient Hurtowni CEIDG z obsługą braku tokena | **PASS** | `src/wulf_web_leader/adapters/pl_ceidg.py`, `tests/test_ceidg_noop.py` | `test_ceidg_no_token_silent_noop`, `test_ceidg_with_mocked_token_queries_api` | Brak zmiennej `CEIDG_API_TOKEN` powoduje cichy no-op bez rzucania wyjątku; z tokenem wykonuje autoryzowane zapytanie HTTP. |
| **WD.2** | Scalanie danych OSM z danymi CEIDG | **PASS** | `src/wulf_web_leader/pipeline.py`, `tests/test_ceidg_merge.py` | `test_inactive_business_receives_zero_score_and_skip`, `test_pipeline_integrates_ceidg` | Podmiot oznaczony w CEIDG jako zawieszony/wykreślony otrzymuje wynik 0 i werdykt `skip`. |
| **WD.3** | Zabezpieczenie limitów zapytań CEIDG | **PASS** | `src/wulf_web_leader/adapters/pl_ceidg.py`, `tests/test_ceidg_limits.py` | `test_ceidg_rate_limiting`, `test_ceidg_http_429_graceful_fallback`, `test_ceidg_http_503_graceful_fallback` | Wymuszony rate limit 3 req/s; kody HTTP 429 i 503 oraz błędy sieci powodują cichy fallback do danych z OSM. |
| **WE.1** | Wzbogacanie danych z lokalnego zrzutu SQLite OffeneRegister | **PASS** | `src/wulf_web_leader/adapters/de_offeneregister.py`, `tests/test_offeneregister.py` | `test_offeneregister_sqlite_status_enrichment`, `test_offeneregister_no_db_silent_noop` | Odczyt statusu podmiotu z lokalnej bazy SQLite; brak pliku skutkuje no-op; zero live-scrapingu handelsregister.de. |
| **WE.2** | Pasywny audyt Impressum jako sygnał porzuconej witryny | **PASS** | `src/wulf_web_leader/score/engine.py`, `tests/test_impressum_audit.py` | `test_missing_impressum_boosts_lead_score`, `test_impressum_hooks_strictly_business_no_legal_threats` | Brak Impressum dodaje punkty jakościowe; hooki są neutralne biznesowo i wolne od gróźb prawnych (*Abmahnung*, *kary*, *pozew*). |
| **WF.1** | Zakaz: Scraping Google Maps i moduły wysyłki e-mail | **PASS** | `CONTRIBUTING.md`, `README.md`, `tests/test_architectural_invariants.py` | `test_no_email_sending_or_smtp_modules_in_src`, `test_no_google_maps_scraping_in_src` | Wiążąca reguła natychmiastowego odrzucania PR w dokumentacji; testy automatyczne weryfikują brak modułów SMTP i scrapera Maps. |
| **WF.2** | Zakaz: GUI/SaaS, chmura i baza 40 branż | **PASS** | `pyproject.toml`, `CONTRIBUTING.md`, `tests/test_architectural_invariants.py` | `test_no_server_dependencies_in_pyproject`, `test_frozen_to_eight_verticals` | 100% local-first CLI; w `pyproject.toml` brak frameworków serwerowych/baz chmurowych; zamrożenie bazy na 8 sprawdzonych branżach. |
