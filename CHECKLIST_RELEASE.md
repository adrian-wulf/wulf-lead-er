# Checklist wydania (Release Checklist) — wulf-web-leader

Procedura weryfikacji i publikacji nowej wersji paczki (`v0.3.0+`).  
Wykonaj poniższe kroki przed utworzeniem taga release w repozytorium.

---

## 1. Weryfikacja stanu repozytorium
- [ ] `git status` — upewnij się, że nie ma niezatwierdzonych zmian ani śmieci w drzewie roboczym.
- [ ] Sprawdź, czy w `.gitignore` ignorowane są pliki robocze:
  - `leads*.csv`, `leads*.json` (brak danych leadów w repozytorium)
  - `.cache/`, `.wulf-cache/`, `audit_cache.json`, `geocache.json`
  - `dist/`, `build/`

## 2. Spójność wersji (Version Bumping)
- [ ] `pyproject.toml` — zweryfikuj pole `version` (np. `"0.3.0"`).
- [ ] `src/wulf_web_leader/__init__.py` — zweryfikuj wartość `__version__` (musi być identyczna jak w `pyproject.toml`).

## 3. Testy automatyczne
- [ ] Uruchomienie pełnego zestawu testów jednostkowych:
  ```bash
  pytest -v
  ```
  *Wszystkie testy (57/57) muszą przejść na zielono.*

## 4. Weryfikacja binarek i aliasów CLI
- [ ] Główna binarka:
  ```bash
  wulf --help
  ```
- [ ] Aliasy wstecznej kompatybilności:
  ```bash
  brakstrony --help
  keinweb --help
  ```
- [ ] Lista branż:
  ```bash
  wulf list-verticals
  ```

## 5. Dymny test wykonawczy (Smoke Test)
- [ ] Szybki zwiad w trybie `--quick`:
  ```bash
  wulf scan --country pl --miasto Rzeszów --vertical plumbers --radius 10 --quick
  ```
- [ ] Weryfikacja kodowania pliku CSV:
  - Plik `leads.csv` musi być zakodowany w `utf-8-sig` (poprawne polskie znaki w arkuszu kalkulacyjnym).

## 6. Budowa paczki dystrybucyjnej (Wheel & Source Distribution)
- [ ] Zbudowanie paczki:
  ```bash
  python -m build
  ```
- [ ] Sprawdzenie czy w katalogu `dist/` powstały poprawne pliki `.whl` oraz `.tar.gz`.

## 7. Tagowanie wydania w Git
- [ ] Utworzenie podpisanego lub opisanego taga:
  ```bash
  git tag -a v0.3.0 -m "Release v0.3.0 - wulf-web-leader"
  git push origin v0.3.0
  ```
