# STATUS Wdrożenia wulf-web-leader

Data audytu i zamknięcia: 2026-09-09 | Wersja: v0.3.0 | Status: 100% DONE (Zero GAP)
Stan realizacji zadań z TODO.md (audyt Definition of Done w `docs/DOD_AUDIT.md`).

| ID | Nazwa zadania | Status | Dowód (test / plik / komenda) |
|---|---|:---:|---|
| **W0.1** | Terenowa weryfikacja 20 leadów HOT | DONE | 32 unikalne HOT z 3 miast/3 branż (20 w `docs/pilot_w01_arkusz.csv`) |
| **W0.2** | Rejestr fałszywych trafień | DONE | 5 wzorców z metodami detekcji w `docs/false_positives.md` |
| **WA.1** | Higiena repo / v0.1.0 / release | DONE | `pyproject.toml` (0.1.0), `.gitignore` (cache/dist/leads), `CHECKLIST_RELEASE.md` |
| **WA.2** | Błędy sieci i puste wyniki | DONE | 3 testy w `tests/test_cli_errors.py` (brak miasta, timeout Overpass, 0 firm) |
| **WA.3** | README ograniczenia OSM | DONE | Sekcja „Specyfika i ograniczenia danych OpenStreetMap” w `README.md` |
| **WB.1** | Martwe POI | DONE | Filtr `is_dead_or_disused_poi` w `osm.py` + test `tests/test_osm_dead_pois.py` |
| **WB.2** | Katalogi i platformy | DONE | `*.business.site`, `olx.pl`, `allegro.pl` w `classifier.py` + testy w `test_classifier.py` |
| **WB.3** | Tagi wszystkich verticals/*.yaml | DONE | Zakaz `shop=car` i `shop=beauty` + test w `tests/test_verticals_tags.py` |
| **WB.4** | Dedupe w mieście | DONE | Scalanie po telefonie i siatce ~100m w `osm.py` + test `tests/test_osm_dedupe.py` |
| **WC.1** | CSV operacyjny | DONE | Kolumny operacyjne i adresowe w `writer.py`/`models.py` + test `tests/test_export_columns.py` |
| **WC.2** | wulf filter | DONE | Komenda `wulf filter` w `cli.py` (zero sieci) + test `tests/test_cli_filter.py` |
| **WC.3** | wulf demo-template | DONE | Komenda `wulf demo-template` w `cli.py` + generator `demo.py` + testy `tests/test_demo_template.py` |
| **WD.1** | CEIDG klient no-op | DONE | `pl_ceidg.py` (brak tokena = cichy no-op) + test `tests/test_ceidg_noop.py` |
| **WD.2** | Merge CEIDG × OSM | DONE | `pipeline.py` + dyskwalifikacja zawieszonych (score=0, skip) + test `tests/test_ceidg_merge.py` |
| **WD.3** | Limity CEIDG | DONE | Ogranicznik rate limit (3 req/s) + fallback dla 429/503/timeout + test `tests/test_ceidg_limits.py` |
| **WE.1** | OffeneRegister SQLite | DONE | `de_offeneregister.py` (lokalny SQLite, brak live-scrapingu) + test `tests/test_offeneregister.py` |
| **WE.2** | Impressum pasywnie | DONE | Pasywny audyt Impressum (+10 pkt, neutralne hooki biznesowe) + test `tests/test_impressum_audit.py` |
| **WF.1** | Zakaz Maps + mail | DONE | Wiążąca reguła odrzucania PR w `CONTRIBUTING.md` i `README.md` + test `tests/test_architectural_invariants.py` |
| **WF.2** | Zakaz GUI/SaaS/40 branż | DONE | Brak zależności serwerowych w `pyproject.toml`, zamrożenie 8 branż + test `tests/test_architectural_invariants.py` |
