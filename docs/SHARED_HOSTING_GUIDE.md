# 🚀 WULF LEAD.ER — Przewodnik Wdrożenia na Hosting Współdzielony

Ten poradnik krok po kroku wyjaśnia, jak uruchomić aplikację **WULF LEAD.ER** na typowym hostingu współdzielonym z obsługą Pythona (np. **cPanel**, **MyDevil.net**, **dhosting**, **LH.pl**, **Cyberfolks**, **Plesk**, **CloudLinux**).

---

## 📋 Wymagania Wstępne
- Konto na hostingu współdzielonym z dostępem SSH lub modułem **Setup Python App** (Phusion Passenger / WSGI).
- Python w wersji `>= 3.11` (zalecany `3.12`).
- Domena lub subdomena przypisana do katalogu aplikacji (np. `radar.twojadomena.pl`).

---

## 🛠️ Opcja A: cPanel z modułem "Setup Python App" (Najpopularniejsza)

Większość polskich i zagranicznych hostingów współdzielonych (Cyberfolks, Smarthost, Hostinger, Atthost itp.) posiada w cPanelu narzędzie **Setup Python App**.

### 1. Prześlij pliki na hosting
1. Spakuj zawartość katalogu aplikacji (lub sklonuj przez SSH) do katalogu docelowego, np. `/home/twoj_user/wulf-web-leader`.
2. Upewnij się, że w głównym katalogu znajdują się pliki:
   - `passenger_wsgi.py`
   - `.htaccess`
   - `pyproject.toml`
   - katalog `src/`

### 2. Utwórz aplikację w cPanelu
1. Zaloguj się do cPanelu i wyszukaj **Setup Python App**.
2. Kliknij **Create Application**:
   - **Python version**: Wybierz `3.12` (lub `3.11`).
   - **Application root**: Wpisz ścieżkę katalogu aplikacji, np. `wulf-web-leader`.
   - **Application URL**: Wybierz swoją subdomenę (np. `radar.twojadomena.pl`).
   - **Application startup file**: Wpisz `passenger_wsgi.py`.
   - **Application Entry point**: Wpisz `application`.
3. Kliknij **Create**.

### 3. Zainstaluj zależności
1. W górnej części widoku aplikacji cPanel skopiuj komendę aktywacji środowiska, np.:
   ```bash
   source /home/twoj_user/virtualenv/wulf-web-leader/3.12/bin/activate && cd /home/twoj_user/wulf-web-leader
   ```
2. Zaloguj się przez SSH do hostingu, wklej powyższą komendę i uruchom:
   ```bash
   pip install --upgrade pip
   pip install -e .
   ```
   *(Alternatywnie w panelu cPanel w sekcji "Configuration files" możesz wpisać `pyproject.toml` i kliknąć "Run Pip Install")*.

### 4. Restart i uruchomienie
1. W panelu cPanel kliknij przycisk **Restart**.
2. Wejdź pod adres swojej subdomeny — zobaczysz pełną konsolę **WULF LEAD.ER** w kolorystyce `wulf-code.it`.

---

## ⚡ Opcja B: MyDevil.net / FreeBSD / BHyve

Hosting **MyDevil.net** posiada znakomitą natywną obsługę aplikacji Python przez Phusion Passenger:

```bash
# 1. Dodanie strony w devil
devil www add radar.twojadomena.pl python /usr/local/bin/python3.12

# 2. Przejście do katalogu public_html
cd ~/domains/radar.twojadomena.pl/public_html

# 3. Klonowanie lub wgranie plików i utworzenie venv
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .

# 4. Restart Phusion Passenger
devil www restart radar.twojadomena.pl
```

---

## 🔄 Jak zrestartować aplikację po aktualizacji kodu?

Phusion Passenger monitoruje plik `tmp/restart.txt`. Aby natychmiast załadować nowy kod bez restartowania całego serwera www:

```bash
mkdir -p tmp
touch tmp/restart.txt
```

---

## 🛡️ Bezpieczeństwo i Prywatność Danych

- Plik `.htaccess` automatycznie blokuje dostęp do plików konfiguracyjnych (`.env`, `.git`, `.venv`, `pyproject.toml`).
- Baza przeskanowanych leadów oraz cache OSM/CEIDG zapisywane są lokalnie w katalogu `data/` na Twoim serwerze. Nikt z zewnątrz nie ma dostępu do Twoich leadów ani kodu źródłowego.
