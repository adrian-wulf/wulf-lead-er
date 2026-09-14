# Plan Wdrożenia: WULF LEAD.ER // 3-Fazy Modernizacji Pipeline'u

## Cel
Wdrożenie pełnego pakietu ulepszeń o najwyższym ROI dla agencji interaktywnych:
1. Dane decydenta (CEIDG / Impressum) i klasyfikacja telefonu (Mobile / WhatsApp / Stacjonarny).
2. Deep-crawling podstron kontaktowych oraz harwester social media (FB, IG, LinkedIn, TikTok, YouTube).
3. Audyt marketingowy (Meta Pixel, GA4, GTM) i integracja wskaźników TTFB w raportach.

---

## Architektura Swarmu Agentów

| Rola Agenta | Nazwa Subagenta | Zakres odpowiedzialności & Pliki |
| :--- | :--- | :--- |
| **Orchestrator** | `Antigravity (Główny)` | Zarządzanie workflow, synchronizacja stanu, scalanie zmian, weryfikacja architektury. |
| **Worker 1** | `worker-telephony-registry` | `models.py`, `adapters/pl_ceidg.py`, `adapters/osm.py`, `adapters/gmaps_scraper.py` |
| **Worker 2** | `worker-deep-crawler` | `audit/fetch.py`, `audit/parser.py`, `audit/verifier.py`, `models.py` |
| **Worker 3** | `worker-marketing-ux` | `audit/parser.py`, `audit/speed.py`, `score/hooks.py`, `score/engine.py`, `export/report.py` |
| **Worker 4** | `worker-qa-critic` | `tests/test_*.py`, regresja 481 testów, testy jednostkowe nowych modułów |

---

## Szczegółowy Harmonogram Zadań

### Faza 1: Dane Rejestrowe, Klasyfikacja Telefonów & Google Maps
- [x] **T1.1 (Model & CEIDG):** Rozszerzenie `CanonicalLead` o `owner_name`, `nip`, `regon`, `phone_type`, `whatsapp_url`, `google_maps_url`. Aktualizacja `adapters/pl_ceidg.py` o odczyt `wlasciciel.imie`, `wlasciciel.nazwisko`, `nip`, `regon`.  
  *Weryfikacja:* `pytest tests/test_ceidg_*.py` oraz test parsowania payloadu CEIDG.
- [x] **T1.2 (Klasyfikacja Telefonu):** Implementacja klasyfikatora numeru w `adapters/osm.py` (`mobile` vs `landline`) dla PL (+48) i DE (+49) bez twardych zewnętrznych zależności (wbudowany parser prefiksów komórkowych UKE/BNetzA + fallback na `phonenumbers` jeśli zainstalowane). Generowanie linku `https://wa.me/<numer>`.  
  *Weryfikacja:* Testy jednostkowe numerów komórkowych i stacjonarnych w `tests/test_osm.py`.
- [x] **T1.3 (Optymalizacja Google Maps Scraper):** Przekazywanie flagi `-radius` (metry) i konfigurowalnej `-depth` (domyślnie 2–3) w `adapters/gmaps_scraper.py`. Pobieranie `google_maps_url` i flagi `open_state`.  
  *Weryfikacja:* Test `tests/test_gmaps_scraper.py`.

---

### Faza 2: Deep-Crawling Podstron, Impressum & Social Media Harvester
- [x] **T2.1 (Deep-Crawling Kontaktowy):** Rozbudowa `audit/fetch.py`: jeśli na stronie głównej brak e-maila lub telefonu, asynchroniczne odpytanie max 2 podstron kontaktowych (`/kontakt`, `/impressum`, `/o-nas`, `/contact`, `/about`). Zabezpieczenia: ten sam host, timeout 3s, ochrona SSRF.  
  *Weryfikacja:* Mock test w `tests/test_audit_deep_crawl.py`.
- [x] **T2.2 (Ekstrakcja Decydenta z Niemieckiego Impressum):** Parser w `audit/parser.py` wyciągający imię i nazwisko reprezentanta z Impressum (`Vertreten durch`, `Geschäftsführer`, `Inhaber`).  
  *Weryfikacja:* Test na próbkach HTML stron niemieckich w `tests/test_impressum_audit.py`.
- [x] **T2.3 (Harvester Social Media):** Rozszerzenie `SafeWebsiteHTMLParser` w `audit/parser.py` o wykrywanie profili `facebook.com`, `instagram.com`, `linkedin.com`, `tiktok.com`, `youtube.com`. Zapis do `AuditResult.social_links`.  
  *Weryfikacja:* Test w `tests/test_classifier.py` i `tests/test_parser.py`.

---

### Faza 3: Audyt Marketingowy, Pomiar TTFB & Nowoczesny Raport UX
- [x] **T3.1 (Detektor Pikseli & Trackingu):** Wykrywanie w `audit/parser.py`: Meta Pixel (`fbq`), Google Analytics 4 (`G-XXXX`), Google Tag Manager (`GTM-XXXX`), TikTok Pixel (`ttq`). Zapis do `AuditResult.detected_pixels`.  
  *Weryfikacja:* Testy detekcji skryptów śledzących w `tests/test_marketing_audit.py`.
- [x] **T3.2 (Integracja TTFB & Scorer Hooks):** Wpięcie bezpośredniego pomiaru TTFB do `AuditResult` w `audit/fetch.py`. Generowanie hooków cold email/call uwzględniających imię właściciela ("Dzień dobry Panie Piotrze"), brak analityki ("Strona nie posiada Pixela Meta ani GA4") i link WhatsApp.  
  *Weryfikacja:* Test w `tests/test_scoring.py` i `tests/test_scoring_archetypes.py`.
- [x] **T3.3 (Interaktywny Raport HTML & Eksport):** Aktualizacja `export/report.py`:
  - Przycisk szybkiego czatu `🟢 WhatsApp` dla numerów komórkowych.
  - Odznaki: `Imię decydenta`, `NIP`, `Typ telefonu` (Komórka / Stacjonarny).
  - Sekcja wykrytych Social Media i brakujących Pixeli marketingowych.
  - Szablon e-mail z automatyczną personalizacją po imieniu (`wlasciciel`).  
  *Weryfikacja:* Wygenerowanie przykładowego raportu HTML i test w `tests/test_report.py`.

---

### Faza 4: Regresja i Niezmienniki Architektury (QA Critic)
- [x] **T4.1 (Pełny Zestaw Testów):** Uruchomienie całego pakietu 481+ testów w środowisku `.venv`.
- [x] **T4.2 (Sprawdzenie Inwariantów Architektonicznych):** `test_architectural_invariants.py`, ochrona SSRF, limit 1MB, zachowanie kompatybilności wstecznej CLI i eksportów CSV/JSON.
