# Pakiet weryfikacyjny pilotażu terenowego (W0.1)

Pakiet przygotowany dla ekipy tworzącej strony www w Polsce do przeprowadzenia weryfikacji 20 realnych leadów o statusie **HOT** przed jakimikolwiek zmianami w kodzie, wagach scoringu czy tagach OSM.

---

## 1. Po co robimy ten pilot i dlaczego 1 HOT w hydraulikach to norma

Fakt ze skanu Rzeszowa (`plumbers`, r=20 km): znaleziono **1 lead HOT** (`Atut`, score 70).  
**To nie jest błąd w kodzie ani bug algorytmu — to naturalna specyfika i ograniczenie bazy OpenStreetMap.**  
W rzemieślniczych niszach (jak hydraulika czy instalatorstwo) mniejsze punkty rzadko trafiają do OSM z kompletem tagów (często brakuje numeru telefonu lub wpis dodawany jest bez danych kontaktowych). Z kolei w branżach o gęstszej infrastrukturze fizycznej (mechanika pojazdowa, wulkanizacje, serwisy opon) baza OSM zawiera dziesiątki punktów z telefonami i bez stron www.

Celem pilotażu jest sprawdzenie w realnym świecie (wyszukiwarka + krótki telefon), czy leady wytypowane jako HOT:
- rzeczywiście istnieją pod wskazanym adresem,
- odbierają podany numer telefonu,
- faktycznie nie mają własnej nowoczesnej witryny www.

---

## 2. Sprawdzone komendy skanowania (Rynek PL)

Poniżej znajduje się zestaw działających komend dla miast Podkarpacia w różnych branżach (`--has-phone --min-score 70`):

1. **Rzeszów — Hydraulicy (baza pilota):**
   ```bash
   wulf scan --country pl --miasto Rzeszów --vertical plumbers --radius 20 --has-phone --min-score 70 --lang pl --out leads_rzeszow_plumbers.csv
   ```
2. **Rzeszów — Warsztaty samochodowe i wulkanizacja:**
   ```bash
   wulf scan --country pl --miasto Rzeszów --vertical auto_repair --radius 15 --has-phone --min-score 70 --lang pl --out leads_rzeszow_auto.csv
   ```
3. **Rzeszów / Łańcut — Usługi elektryczne:**
   ```bash
   wulf scan --country pl --miasto Rzeszów --vertical electricians --radius 20 --has-phone --min-score 70 --lang pl --out leads_rzeszow_elec.csv
   ```
4. **Krosno — Warsztaty i serwisy opon:**
   ```bash
   wulf scan --country pl --miasto Krosno --vertical auto_repair --radius 15 --has-phone --min-score 70 --lang pl --out leads_krosno_auto.csv
   ```
5. **Dębica — Warsztaty samochodowe:**
   ```bash
   wulf scan --country pl --miasto Dębica --vertical auto_repair --radius 15 --has-phone --min-score 70 --lang pl --out leads_debica_auto.csv
   ```
6. **Skan pomocniczy / dobitka (@60) — do osobnego pliku:**
   Używamy go tylko wtedy, gdy w wąskiej niszy brakuje pozycji @70 do zamknięcia puli:
   ```bash
   wulf scan --country pl --miasto Rzeszów --vertical plumbers --radius 20 --has-phone --min-score 60 --lang pl --out leads_rzeszow_plumbers_60.csv
   ```

---

## 3. Jak otworzyć plik CSV w Excelu i LibreOffice Calc

Pliki wyjściowe zapisywane są w formacie **`utf-8-sig`** (BOM), dzięki czemu polskie znaki (`ą, ć, ę, ł, ń, ó, ś, ź, ż`) wyświetlają się poprawnie w każdym arkuszu.

- **Microsoft Excel**: Domyślnym separatorem jest przecinek (`,`). Jeśli w Twoim systemie Excel wymaga średnika, dodaj do komendy skanu opcję `--delimiter semicolon` lub użyj importu: *Dane → Ze źródła tekst/CSV*.
- **LibreOffice Calc**: Przy otwieraniu wybierz kodowanie *Unicode (UTF-8)* oraz zaznacz separator *Przecinek*.

---

## 4. Zasady kontaktu z firmami

1. **Dzwonimy wyłącznie do leadów HOT z numerem telefonu.**
2. **Zero e-maili i cold-mailingu:** Narzędzie nie posiada i nie będzie posiadać modułu wysyłkowego.
3. **Podejście partnerskie:** Pytamy, czy firma pozyskuje klientów mobilnych z okolicy i czy potrzebuje prostej, szybkiej wizytówki one-pager.

---

## 5. Tabela weryfikacji (20 leadów HOT z realnych skanów)

Wszystkie pozycje poniżej zostały wygenerowane z rzeczywistych skanów OSM w Rzeszowie, Krośnie i Dębicy (`--min-score 70 --has-phone`).  
Kolumny **Co w terenie** oraz **Przyczyna** uzupełnia osoba weryfikująca.

Dopuszczalne wartości w kolumnie **Przyczyna**:
- *(pozostaw puste)* — **trafiony** (firma istnieje, telefon odpowiada, nie mają własnej strony)
- `firma nie istnieje` — punkt zamknięty, zlikwidowany, brak działalności
- `zły numer` — numer nie odpowiada, nie istnieje, należy do osoby prywatnej
- `mają stronę` — firma posiada już działającą stronę www (podaj link w notatce)
- `zła branża` — punkt świadczy zupełnie inne usługi
- `inne` — inne przyczyny (zwięzły opis)

| Lp. | Firma | Telefon | Próg | Score | Werdykt wulf | Co w terenie | Przyczyna |
|:---:|---|---|:---:|:---:|:---:|---|---|
| 1 | Atut | +48***11 | 70 | 70 | HOT | | |
| 2 | Amper | +48***67 | 70 | 70 | HOT | | |
| 3 | Wulkanizacja (Rzeszów, ul. Podkarpacka) | +48***61 | 70 | 70 | HOT | | |
| 4 | EW Engine | +48***65 | 70 | 70 | HOT | | |
| 5 | Sołek CARS | +48***03 | 70 | 70 | HOT | | |
| 6 | Wulkanizacja (Rzeszów, al. Sikorskiego) | +48***75 | 70 | 70 | HOT | | |
| 7 | Auto-Spark Mechanika Pojazdowa | +48***73 | 70 | 70 | HOT | | |
| 8 | Mechanika Samochodowa Dariusz Dander | +48***19 | 70 | 70 | HOT | | |
| 9 | STAG TAD-MAT Tadeusz Czerkies | +48***82 | 70 | 70 | HOT | | |
| 10 | BJ auto serwis | +48***02 | 70 | 70 | HOT | | |
| 11 | Bosch Car Service - Przybyłowicz | +48***63 | 70 | 70 | HOT | | |
| 12 | ABCar-Auto | +48***09 | 70 | 70 | HOT | | |
| 13 | FUH Łukasz Lasota | +48***72 | 70 | 70 | HOT | | |
| 14 | Serwis opon "Auto-Luz" | +48***28 | 70 | 70 | HOT | | |
| 15 | Auto Naprawa | +48***98 | 70 | 70 | HOT | | |
| 16 | KMB Auto Serwis | +48***31 | 70 | 70 | HOT | | |
| 17 | Mwm. Mechanika pojazdowa. Muł W. | +48***30 | 70 | 70 | HOT | | |
| 18 | Edek Opony (Krosno) | +48***62 | 70 | 70 | HOT | | |
| 19 | Gal Mot (Krosno) | +48***65 | 70 | 70 | HOT | | |
| 20 | Auto Serwis Skoti (Dębica) | +48***91 | 70 | 70 | HOT | | |

---

## 6. Jak zapisać wnioski do docs/false_positives.md (Zadanie W0.2)

1. Po zweryfikowaniu tabeli oblicz odsetek trafień: `(liczba trafionych / 20) * 100%`.
2. Zbierz wszystkie wiersze, w których wypełniono pole `Przyczyna`.
3. W pliku `docs/false_positives.md` sformułuj zwięzłe wzorce zaobserwowanych rozbieżności w oparciu o fakty (np. „warsztat działa, ale strona jest pod nazwiskiem właściciela w domenie .pl”, „numer w OSM to stary stacjonarny”).
4. Wskaż, które błędy wynikają z braków aktualizacji w OSM, a które z potrzeby weryfikacji w CEIDG lub dokładniejszego filtrowania tagów.
5. Na podstawie tych danych zespół ustali priorytety prac programistycznych dla Etapu B.

---

## Opcjonalnie: Rynek niemiecki (DE)

*Odpalacie wyłącznie wtedy, gdy ekipa rzeczywiście pozyskuje klientów w Niemczech:*
```bash
wulf scan --country de --city Dresden --vertical hair --radius 15 --has-phone --min-score 70 --lang de --out leads_pilot_de.csv
```
