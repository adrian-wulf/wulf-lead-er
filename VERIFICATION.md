# VERIFICATION AUDIT REPORT: wulf-web-leader (brakstrony / keinweb)

**Data audytu:** 2026-09-09  
**Weryfikator:** Antigravity AI  
**Cel audytu:** Weryfikacja faktycznego stanu repozytorium przed przystąpieniem do fazy utwardzania (Hardening) i wdrażania nowych funkcji.

---

## 1. Zestawienie kontrolne (Pass / Fail per Check)

| Nr | Obszar audytu | Wymaganie | Wynik | Uwagi audytora |
|---|---|---|---|---|
| **1** | **Testy jednostkowe** | `pytest -q` przechodzi w 100% | **PASS** | 16/16 testów zaliczonych w 0.19s (`tests/test_*.py`). |
| **2** | **CLI Binary & Help** | Dostępność poleceń `scan`, `audit`, `export`, `list-verticals` | **PASS** | `brakstrony --help` działa poprawnie, obsługuje komplet komend. |
| **3** | **Live Scan (Rzeszów)** | Działanie na żywo z prawdziwymi API Nominatim + Overpass | **PASS** | `scan --country pl --city Rzeszów --vertical plumbers --radius 10 --quick` zwrócił 6 firm (1 HOT, 1 WARM, 4 SKIP). |
| **4** | **Formuła punktacji** | Brak strony + telefon osiąga status HOT (≥ 70) | **PASS** | Brak strony (+50) + telefon (+20) = 70 (`hot`). Dokładna formuła opisana w Sekcji 2. |
| **5** | **Precyzja tagów (Hair)** | 670 wyników w Dreźnie r=15km – analiza nadmiarowości | **FAIL (DO POPRAWY)** | `verticals/hair.yaml` zawiera tag `shop=beauty`, który ściąga kosmetyczki, solaria, salony paznokci i spa. Wymaga zawężenia wyłącznie do `shop=hairdresser`. |
| **6** | **Klasyfikator domen** | Facebook, Instagram, katalogi nie mogą być traktowane jako "własna strona" | **PASS** | `audit/classifier.py` klasyfikuje platformy społecznościowe i katalogi (Panorama Firm, PKT, Gelbe Seiten itp.) przed regułą domeny własnej. |
| **7** | **Nominatim Adapter** | Czytelny User-Agent, limit ≥1.0s, lokalny cache | **PASS** | UA: `brakstrony/0.1.0 (+https://github.com/wulf-org/brakstrony)`, twarde `time.sleep` chroniące limit 1 req/s, cache w `~/.cache/brakstrony/geocache.json`. |
| **8** | **Overpass Adapter** | Deduplikacja, normalizacja telefonu, failover serwerów lustrzanych, brak `mail.ru` | **PASS** | Brak `mail.ru`; 4 europejskie mirrory (`overpass-api.de`, `lz4`, `kumi.systems`, `private.coffee`); deduplikacja po ID OSM i siatce 100m; normalizacja numerów do formatu międzynarodowego. |
| **9** | **Audyt WWW / SSRF Guard** | Blokada IP prywatnych/link-local, ochrona przekierowań (TOCTOU), limit 1MB | **PASS** | `audit/fetch.py` weryfikuje IP na każdym przeskoku (redirect hop), blokuje pętlę zwrotną, sieci prywatne, multicast oraz metadane chmurowe `169.254.169.254`. Limit bufora: 1MB. |
| **10** | **Eksport i ODbL** | Kodowanie `utf-8-sig`, obecność noty OpenStreetMap ODbL | **PASS (z uwagą)** | `utf-8-sig` działa w CSV. JSON posiada pole `_attribution`. Konsola drukuje notę ODbL. W Fazie 2 warto dodać wiersz atrybucji również bezpośrednio do pliku CSV. |
| **11** | **Treść pitch hooków** | Wyłącznie doradcze, brak gróźb prawnych ("Abmahnrisiko") w wersji niemieckiej | **PASS** | `locales/de.json` skupia się na utraconych klientach mobilnych i braku widoczności w Google. Zero wzmianek o Abmahnung / paragrafach. |

---

## 2. Dokładna formuła punktacji (`src/brakstrony/score/engine.py`)

Punktacja bazowa: `score = 0`. Wartość wynikowa jest przycinana do zakresu `[0, 100]`.

```python
# 0. Dyskwalifikacja
if lead.registry_status == "inactive":
    return 0, "skip"

# 1. Status strony www
if lead.website_kind == "none":
    score += 50
elif lead.website_kind in ("facebook", "instagram", "directory"):
    score += 35
elif lead.website_kind == "own":
    if lead.audit:
        if not lead.audit.reachable:
            score += 40  # Strona zgłoszona w OSM, ale domena martwa/niedostępna
        else:
            if not lead.audit.is_https:
                score += 10  # Brak HTTPS
            if not lead.audit.has_viewport:
                score += 15  # Brak responsywności mobilnej (brak viewport)
            if is_outdated_cms(lead.audit.generator):
                score += 10  # Przestarzały generator (np. Joomla, Drupal 7)
else:
    score += 20  # Inne platformy

# 2. Kanał kontaktu (użyteczność dla freelancera)
if lead.phone and len(lead.phone.strip()) >= 7:
    score += 20  # Jest publiczny numer telefonu do bezpośredniego kontaktu

# Progi werdyktów:
# score >= 70: "hot"
# score >= 45: "warm"
# score <  45: "skip"
```

### Przykładowe kalkulacje:
1. **Firma bez strony z numerem telefonu:** `50 (brak strony) + 20 (telefon) = 70` ➔ **HOT**
2. **Firma bez strony i bez telefonu:** `50 (brak strony) + 0 = 50` ➔ **WARM**
3. **Tylko profil na Facebooku z telefonem:** `35 (social) + 20 (telefon) = 55` ➔ **WARM**
4. **Tylko profil na Facebooku z telefonem + audytowana strona HTTP bez viewportu:** `35 + 20 + 10 + 15 = 80` ➔ **HOT**
5. **Działająca nowoczesna strona HTTPS z viewportem:** `0 + 20 (telefon) = 20` ➔ **SKIP**

---

## 3. Analiza fałszywych trafień (False-Positive Notes)

Na podstawie próby 15 leadów z pliku `leads_hot_de.csv` (skan Drezna dla branży `hair` w promieniu 15 km):

1. **`Kosmetik-Salon` (Kreischa):** FAŁSZYWE TRAFIENIE. Gabinet kosmetyczny / pielęgnacyjny, nie salon fryzjerski. Źródło: tag `shop=beauty`.
2. **`Friseursalon Karin Brenke` (Kreischa):** PRAWIDŁOWE. Salon fryzjerski, aktualny telefon stacjonarny, brak strony.
3. **`Friseur Lädchen` (Kreischa):** PRAWIDŁOWE. Salon fryzjerski, telefon komórkowy, brak strony.
4. **`Regina Pietsch` (Wilsdruff):** PRAWIDŁOWE. Usługi fryzjerskie.
5. **`Kerstin Riemer Schwarze` (Freital):** PRAWIDŁOWE.
6. **`Salon Marion` (Freital):** PRAWIDŁOWE. Salon fryzjerski.
7. **`Friseursalon "Sandra"` (Freital):** PRAWIDŁOWE.
8. **`Channoine In Vita Point` (Freital):** FAŁSZYWE TRAFIENIE. Dystrybucja kosmetyków / salon pielęgnacyjny. Źródło: tag `shop=beauty`.
9. **`Friseursalon Lindner` (Wilsdruff):** PRAWIDŁOWE.
10. **`feelings` (Dresden):** Weryfikacja – salon stylizacji i urody.
11. **`Kosmetikstudio Anke Damme`:** FAŁSZYWE TRAFIENIE. Studio kosmetyczne. Źródło: `shop=beauty`.
12. **`Beautyfarm Sigrid Kleint`:** FAŁSZYWE TRAFIENIE. Farma urody / masaże / spa. Źródło: `shop=beauty`.

### Diagnoza błędu:
Około 30-35% wpisów w wertykale `hair` to gabinety kosmetyczne i spa, ponieważ `verticals/hair.yaml` posiadał tag `shop=beauty`.
**Zalecenie Fazy 2:** Usunąć `shop=beauty` z `hair.yaml` i pozostawić wyłącznie `shop=hairdresser`. Jeśli potrzebna jest branża kosmetyczna, należy utworzyć odrębny plik `beauty.yaml` (`kosmetyczka`).

---

## 4. Stan modułów: Rzeczywisty vs Stub (Stan kodu)

- **Rzeczywiste moduły (Production-ready w v1.0):**
  - `src/brakstrony/cli.py` – pełne CLI z obsługą Typer i formatowaniem Rich.
  - `src/brakstrony/models.py` – modele Pydantic v2.
  - `src/brakstrony/verticals.py` – dynamiczny loader branż YAML z obsługą synonimów PL i DE.
  - `src/brakstrony/adapters/nominatim.py` – geokodowanie z cache i ograniczeniem 1s.
  - `src/brakstrony/adapters/osm.py` – obsługa Overpass API z wieloma mirrorami, jitter backoff, normalizacją telefonów i deduplikacją.
  - `src/brakstrony/audit/classifier.py` – klasyfikator rodzajów stron (Facebook, Instagram, katalogi, własne domeny).
  - `src/brakstrony/audit/fetch.py` – bezpieczny klient HTTP z ochroną SSRF, streamingiem do 1MB i obsługą przekierowań.
  - `src/brakstrony/audit/parser.py` – parser strumieniowy HTML wyciągający viewport, CMS, kontakty i Impressum bez podatności ReDoS.
  - `src/brakstrony/score/engine.py` – deterministyczny silnik punktacji.
  - `src/brakstrony/score/hooks.py` – generator hooków sprzedażowych w oparciu o `locales/*.json`.
  - `src/brakstrony/export/writer.py` – generator plików CSV (`utf-8-sig`) i JSON.
  - `verticals/*.yaml` – 8 zdefiniowanych branż.
  - `locales/*.json` – teksty dla języków PL, DE i EN.

- **Stupy (Stubs - jawnie oznaczone dla v1.1):**
  - `src/brakstrony/adapters/pl_ceidg.py` – zaślepka klasy `CEIDGAdapter` (zwraca obiekt leada bez zmian; `is_available()` sprawdza obecność tokenu JWT). Brak zaimplementowanego pobierania z Hurtowni CEIDG.
  - `src/brakstrony/adapters/de_offeneregister.py` – zaślepka klasy `OffeneRegisterAdapter` (zwraca leada bez zmian; `is_available()` sprawdza ścieżkę do bazy SQLite). Brak zaimplementowanego zapytania SQLite.

---

## 5. Status Zmiany Nazwy (Rename Status)

- **Obecna nazwa w kodzie i konfiguracji:** `brakstrony` (alias `keinweb`).
- **Planowana nazwa w Fazie 2:**
  - Paczka i projekt: `wulf-web-leader`
  - Główna binarka CLI: `wulf`
  - Aliasy wstecznej kompatybilności: `brakstrony`, `keinweb`
  - Pakiet Pythona: `wulf_web_leader` (zostaną zaktualizowane wszystkie importy i skrypty).

---

## Podsumowanie i Rekomendacja

Faza 0 i Faza 1 zostały w pełni zrealizowane:
- Wszystkie testy jednostkowe przechodzą (16/16).
- Rzeczywisty stan kodu weryfikuje obietnice architektury z wyjątkiem zbyt szerokiego tagowania `hair.yaml` (`shop=beauty`), co zostało zidentyfikowane i przygotowane do poprawy w Fazie 2.
- Moduły CEIDG i OffeneRegister są czystymi zaślepkami przygotowanymi pod v1.1.

Zgodnie z instrukcją zatrzymano pracę po utworzeniu `VERIFICATION.md` w oczekiwaniu na decyzję "continue" użytkownika.
