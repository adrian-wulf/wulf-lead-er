# WULF LEAD.ER // Radar B2B & Lead Intelligence Console

<p align="center">
  <strong>Autonomiczny silnik wywiadu gospodarczego i audytu technologicznego dla agencji interaktywnych, software house'ów i web designerów.</strong><br>
  Znajduj lokalne firmy w Polsce i Niemczech, które pilnie potrzebują nowej strony www, naprawy awarii lub modernizacji wizerunku.
</p>

<p align="center">
  <a href="https://lead.social-wulf.eu"><img src="https://img.shields.io/badge/Aplikacja_Live-lead.social--wulf.eu-D4A418?style=for-the-badge&logo=fastapi&logoColor=white" alt="Live App"></a>
  <a href="https://social-wulf.eu"><img src="https://img.shields.io/badge/Wulf_Hub-social--wulf.eu-141414?style=for-the-badge" alt="Hub"></a>
  <a href="https://wulf-code.it"><img src="https://img.shields.io/badge/Agencja-wulf--code.it-9B1B1B?style=for-the-badge" alt="Wulf Code"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12%2B-blue?style=flat-square&logo=python" alt="Python Version">
  <img src="https://img.shields.io/badge/FastAPI-0.111%2B-009688?style=flat-square&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Google_AI_Studio-Gemini_3.6_Flash-4285F4?style=flat-square&logo=google" alt="Gemini AI">
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker" alt="Docker Ready">
  <img src="https://img.shields.io/badge/Licencja-MIT-green?style=flat-square" alt="MIT License">
  <img src="https://img.shields.io/badge/Status-Produkcja_v0.3.0-gold?style=flat-square" alt="Version">
</p>

---

## 🎯 Po co powstał WULF LEAD.ER?

Większość agencji marnuje setki godzin na ręczne przeszukiwanie map lub wysyłanie bezmyślnego spamu mailowego, który ląduje w koszu.

**WULF LEAD.ER działa inaczej:**
1. **Pobiera legalne dane:** Przeszukuje otwarty rejestr OpenStreetMap dla wybranego miasta, promienia i branży (w Polsce i Niemczech).
2. **Automatycznie audytuje witryny www:** Weryfikuje błędy HTTP (404, 500), wygasłe domeny, brak responsywności (RWD / mobile viewport), brak certyfikatu SSL, przestarzałe technologie (np. Joomla, Drupal 7, stary WordPress) oraz brak wymaganego prawem Impressum w Niemczech.
3. **Kalkulator Utraconych Przychodów & Sonda Speed:** Oblicza szacunkowy comiesięczny i roczny wyciek kapitału klienta oraz mierzy czas pierwszej odpowiedzi serwera (TTFB) i wagę strony.
4. **Google Search Grounding & OSINT:** Dzięki integracji z silnikiem Gemini 3.6 Flash i Google Search Grounding aplikacja bada w czasie rzeczywistym reputację firmy w Google Maps, wyciąga oceny i generuje celny pitch.
5. **Focus Dialer & Mini Pipeline CRM:** Dedykowany tryb pełnoekranowy do obzwania bazy (skróty klawiszowe, 1-Click Click-to-Call, WhatsApp, statusy: Nowy, Zadzwoniono, Wysłano audyt, Spotkanie, Odrzucony).
6. **Karta Audytu A4 (Print & PDF):** Generuje certyfikowany, elegancki raport diagnostyczny gotowy do druku na spotkanie handlowe lub wysyłki mailowej.
7. **Błyskawiczny Prototyp Nowej Witryny (Instant Demo):** Generuje spersonalizowany podgląd nowoczesnej strony komercyjnej dla konkretnego klienta w 1 kliknięcie.
8. **Matryca Ripost na Obiekcje (Battlecards):** Gotowe scenariusze rozmów obalające obiekcje: „wystarcza nam Facebook”, „mamy stronę z 2012 roku”, „klienci przychodzą z polecenia”, „brak budżetu”.

---

## 🚀 Szybki start (Self-Hosting)

Aplikację możesz uruchomić na 3 sposoby: przez Docker, lokalnie w Pythonie lub w przeglądarce.

### Opcja 1: Uruchomienie przez Docker (Rekomendowane)

Wymagany zainstalowany Docker oraz Docker Compose:

```bash
# 1. Sklonuj repozytorium
git clone https://github.com/adrian-wulf/wulf-lead-er.git
cd wulf-lead-er

# 2. Uruchom kontener
docker compose up -d --build

# 3. Otwórz w przeglądarce
# http://localhost:8000
```

Dane sesji oraz historia skanów będą bezpiecznie zapisywane w lokalnym katalogu `./sessions`.

---

### Opcja 2: Uruchomienie lokalne (Python 3.12+)

```bash
# 1. Sklonuj i wejdź do katalogu
git clone https://github.com/adrian-wulf/wulf-lead-er.git
cd wulf-lead-er

# 2. Utwórz wirtualne środowisko i zainstaluj zależności
python3 -m venv .venv
source .venv/bin/activate    # Linux/macOS
# lub: .venv\Scripts\activate na Windows

pip install -e .

# 3. Uruchom interaktywny pulpit Web GUI
lead.er web
```

Domyślnie otworzy się przeglądarka pod adresem `http://127.0.0.1:8000`.

---

### Opcja 3: Skanowanie bezpośrednio z terminala (CLI)

Możesz korzystać z narzędzia w trybie czysto konsolowym bez uruchamiania przeglądarki:

```bash
# Hydraulicy w Rzeszowie (promień 20 km, tylko z telefonem, min. 70 pkt)
lead.er scan --country pl --city Rzeszów --vertical plumbers --radius 20 --has-phone --min-score 70

# Warsztaty samochodowe w Dębicy
lead.er scan --country pl --city Dębica --vertical mechanik --radius 15

# Salony fryzjerskie w Dreźnie (język niemiecki)
lead.er scan --country de --city Dresden --vertical friseur --radius 15 --lang de
```

Wyniki automatycznie zapisują się do plików `leads.csv` oraz `leads.json`.

## 🛡️ Konfiguracja Bezpieczeństwa, Proxy & Kluczy API

### 1. Gdzie dodać własne serwery proxy (Google Maps & OSINT)?

Aby uniknąć limitów i blokad antybotowych ze strony Google Maps oraz wyszukiwarek przy automatycznym poszukiwaniu domen firmowych (OSINT candidate discovery), system korzysta z puli serwerów proxy.

* **Domyślna lokalizacja pliku:**  
  Umieść swoje proxy w pliku: `data/proxies.txt`  
  *(Alternatywnie możesz wskazać własną ścieżkę w zmiennej środowiskowej `PROXIES_FILE=/sciezka/do/pliku.txt`).*

* **Obsługiwane formaty (1 proxy na linię):**  
  System automatycznie wykrywa i parsuje oba najpopularniejsze formaty:
  1. Standardowy format URL HTTP/HTTPS:
     ```text
     http://uzytkownik:haslo@1.2.3.4:8080
     ```
  2. Format eksportu z paneli dostawców proxy (np. Webshare / proxy list):
     ```text
     1.2.3.4:8080:uzytkownik:haslo
     ```
  Wzorzec demonstracyjny znajdziesz w pliku `data/proxies.txt.example`.

### 2. Gdzie dodać klucze API?

* **Opcja A — Plik `.env` (konfiguracja systemowa):**  
  Skopiuj szablon `.env.example` do `.env` w głównym katalogu projektu:
  ```bash
  cp .env.example .env
  ```
  Zdefiniuj klucze według potrzeb:
  ```env
  GEMINI_API_KEY=twoj_klucz_z_google_ai_studio
  CEIDG_API_TOKEN=twoj_token_z_rejestru_dane_biznes_gov_pl
  ```

* **Opcja B — Interfejs graficzny Web GUI:**  
  Klucz Google AI Studio możesz wkleić bezpośrednio w przeglądarce, klikając przycisk `✨ Gemini AI` w górnym pasku aplikacji. Klucz zostanie zapisany wyłącznie w Twojej sesji przeglądarki.

### 3. Gwarancja prywatności i bezpieczeństwa (Zero wycieków)

> [!IMPORTANT]
> Pliki z prywatnymi danymi (`.env`, `.env.*`, `data/proxies.txt`, `*proxies*.txt`) są na stałe wpisane do reguł [`.gitignore`](.gitignore). Twoje hasła do proxy oraz klucze API **nigdy nie trafią do repozytorium GitHub**.

---

## 🧠 Integracja z Google AI Studio (Gemini 3.6 Flash)

Aplikacja posiada natywne wsparcie dla najnowszego modelu **Gemini 3.6 Flash** z włączonym narzędziem **Google Search Grounding**:

* **Weryfikacja w Google na żywo:** Sprawdza, czy firma posiada wizytówkę w Google Maps, ile ma opinii i jaką ma średnią ocenę.
* **Źródła (Grounding Chipy):** Pokazuje klikalne odnośniki do rzeczywistych źródeł w wyszukiwarce Google, z których model czerpał wiedzę.
* **Gotowy Pitch Sprzedażowy:** Generuje 3-zadaniowy, celny skrypt rozmowy telefonicznej wskazujący konkretną lukę technologiczną firmy (np. brak responsywności na smartfonach, błąd SSL, słabą widoczność).
* **Konfiguracja w 10 sekund:** Wystarczy wkleić swój darmowy klucz z [Google AI Studio](https://aistudio.google.com/) bezpośrednio w okienku aplikacji (przycisk `✨ Gemini AI` w nagłówku). Klucz jest szyfrowany i zapisywany w Twojej prywatnej sesji przeglądarki.

---

## 📊 Wielowymiarowy scoring szans (0–100 pkt)

Narzędzie automatycznie klasyfikuje leady według 6 sprawdzonych archetypów rynkowych:

| Archetyp | Punktacja | Status | Co oznacza w praktyce? |
| :--- | :---: | :---: | :--- |
| **`broken_website`** | **85 pkt** | `HOT 🔥` | **Awaria witryny:** Błędy HTTP 4xx/5xx, wygasły SSL, parking domeny lub zaślepka hostingowa („strona w budowie”). Klient pilnie potrzebuje pomocy! |
| **`critical_redesign`** | **70–85 pkt** | `HOT 🔥` | **Pilny redesign:** Strona działa, ale nie działa na telefonach (brak RWD / viewportu), brak szyfrowania HTTPS lub przestarzały CMS (Joomla, Drupal 7). |
| **`social_only`** | **70 pkt** | `HOT 🔥` | **Tylko social media:** Firma podaje wyłącznie fanpage na Facebooku lub Instagram zamiast własnej witryny. |
| **`no_website`** | **70 pkt** | `HOT 🔥` | **Brak witryny:** Lokalny przedsiębiorca (JDG / rzemieślnik), który nie ma żadnej zarejestrowanej domeny. |
| **`directory_only`** | **65 pkt** | `WARM ⚡` | **Tylko katalog firm:** Podpięty wyłącznie wpis w Panoramie Firm, Cylex lub YellowPages. |
| **`suspect_unverified`** | **max 50 pkt**| `WARM ⚡` | **Spółka kapitałowa:** Sp. z o.o. lub GmbH bez tagu www w OSM. Punktacja obniżona, aby nie zaśmiecać listy HOT przed weryfikacją. |
| **`modern_active`** | **0–30 pkt** | `SKIP ⚪` | **Nowoczesna strona:** Strona działa poprawnie, jest responsywna i bezpieczna. |

---

## 🛠️ Dostępne branże (Verticals)

Wszystkie szablony branżowe zdefiniowane są w przejrzystych plikach YAML w katalogu `verticals/`:

* `plumbers` — Hydraulicy, instalacje sanitarne, ogrzewanie (`hydraulik`, `instalator`, `klempner`, `sanitär`)
* `auto_repair` — Warsztaty samochodowe, mechanicy, wulkanizacja (`mechanik`, `warsztat`, `autowerkstatt`, `kfz`)
* `hair` — Salony fryzjerskie, barberzy (`fryzjer`, `barber`, `friseur`)
* `electricians` — Elektrycy, instalacje elektryczne (`elektryk`, `usługi elektryczne`, `elektriker`)
* `restaurant` — Gastronomia, restauracje, pizzerie (`restauracja`, `pizzeria`, `restaurant`)
* `bakery` — Piekarnie, cukiernie (`piekarnia`, `cukiernia`, `bäckerei`)
* `veterinary` — Przychodnie i gabinety weterynaryjne (`weterynarz`, `lecznica`, `tierarzt`)
* `gym` — Siłownie, kluby fitness (`siłownia`, `fitness`, `fitnessstudio`)

*Możesz łatwo zdefiniować własną branżę, dodając nowy plik YAML w katalogu `verticals/`.*

---

## 🖥️ Komendy konsolowe (CLI Reference)

Główna binarka aplikacji to `lead.er` (dostępna także pod aliasem `leader` oraz wstecznie kompatybilnymi `brakstrony` i `keinweb`):

* **`lead.er scan`** — Skanuje obszar, geokoduje Nominatim, audytuje serwisy i tworzy pliki wyjściowe.
* **`lead.er web`** — Uruchamia interaktywny pulpit Web GUI z podglądem SSE na żywo.
* **`lead.er report [plik.json]`** — Generuje samodzielny, offline'owy raport HTML z wyszukiwarką i filtrami.
* **`lead.er audit [plik.json]`** — Ponawia audyt techniczny stron dla wcześniej zapisanego pliku.
* **`lead.er export [plik.json]`** — Filtruje i konwertuje bazę do wybranego formatu.
* **`lead.er list-verticals`** — Wyświetla listę branż wraz z polskimi i niemieckimi aliasami.

---

## 🌐 Wdrożenie na hosting współdzielony (np. Hostido / LiteSpeed / cPanel)

Aplikacja posiada gotową architekturę do uruchomienia na tanim hostingu współdzielonym ze wsparciem **Python Selector / LiteSpeed WSGI**:

1. Skonfiguruj aplikację Python w panelu DirectAdmin / cPanel (Python 3.12).
2. Skopiuj plik [passenger_wsgi.py](passenger_wsgi.py) oraz [.htaccess](.htaccess).
3. Zarządzaj procesami w tle za pomocą dołączonego skryptu [runner.py](src/wulf_web_leader/web/runner.py), który jest odporny na limity czasowe LiteSpeed WSGI.
4. Pełną dokumentację wdrożenia krok po kroku znajdziesz w pliku [docs/SHARED_HOSTING_GUIDE.md](docs/SHARED_HOSTING_GUIDE.md).

---

## 🔒 Prywatność i Bezpieczeństwo

* **Odizolowane sesje:** Każdy użytkownik i okno incognito otrzymuje niezależną przestrzeń roboczą (`sessions/<id>/`).
* **Brak telemetrii:** Kod nie wysyła żadnych danych analitycznych do podmiotów trzecich.
* **Ochrona SSRF:** Wbudowane filtry uniemożliwiają odpytywanie adresów pętli zwrotnej (`127.0.0.1`, `localhost`, prywatne podsieci LAN).
* **Licencja MIT:** Możesz swobodnie modyfikować kod, wdrażać go wewnętrznie w firmie lub używać komercyjnie.

---

## 👥 Autorzy & Ekosystem

* **Twórca:** [Adrian Wulf](https://github.com/adrian-wulf)
* **Software House:** [Wulf Code](https://wulf-code.it)
* **Hub Ekosystemu:** [social-wulf.eu](https://social-wulf.eu)
* **Aplikacja w chmurze:** [lead.social-wulf.eu](https://lead.social-wulf.eu)

---

## 📜 Prawa autorskie & ODbL

Dane geograficzne i adresowe pochodzą ze społeczności **OpenStreetMap** (ODbL 1.0).  
Projekt wydany na otwartej licencji **MIT License**.
