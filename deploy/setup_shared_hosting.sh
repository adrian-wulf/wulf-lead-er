#!/usr/bin/env bash
# ==============================================================================
# WULF LEAD.ER — Automatyczny instalator dla hostingu współdzielonego
# (cPanel, DirectAdmin, Plesk, CloudLinux)
# ==============================================================================

set -e

echo "--------------------------------------------------------"
echo "  🐺 WULF LEAD.ER — Instalacja na Hostingu Współdzielonym"
echo "--------------------------------------------------------"

# 1. Wykrycie wersji Pythona
PYTHON_BIN=""
for cmd in python3.12 python3.11 python3; do
    if command -v "$cmd" &> /dev/null; then
        PY_VER=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        PY_MAJOR=$("$cmd" -c "import sys; print(sys.version_info.major)")
        PY_MINOR=$("$cmd" -c "import sys; print(sys.version_info.minor)")
        if [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -ge 11 ]; then
            PYTHON_BIN="$cmd"
            echo "[OK] Wykryto Python $PY_VER ($PYTHON_BIN)"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "[BŁĄD] Wymagany jest Python >= 3.11 (zalecany 3.12)."
    echo "W panelu cPanel wybierz 'Setup Python App' i utwórz środowisko z Python 3.12."
    exit 1
fi

# 2. Tworzenie lub weryfikacja środowiska wirtualnego .venv
if [ ! -d ".venv" ]; then
    echo "[...] Tworzenie środowiska wirtualnego w katalogu .venv..."
    $PYTHON_BIN -m venv .venv
fi

# 3. Aktywacja środowiska
echo "[...] Aktywacja środowiska wirtualnego..."
source .venv/bin/activate

# 4. Aktualizacja pip i instalacja zależności
echo "[...] Instalacja zależności wirtualnego środowiska..."
pip install --upgrade pip
pip install -e .

# 5. Weryfikacja działania WSGI
echo "[...] Testowanie punktu wejścia Passenger WSGI..."
python -c "
import passenger_wsgi
from a2wsgi import ASGIMiddleware
assert hasattr(passenger_wsgi, 'application'), 'Brak zmiennej application w passenger_wsgi.py'
print('[OK] passenger_wsgi.py ładuje się poprawnie i eksportuje obiekt WSGI application!')
"

# 6. Przygotowanie katalogu tmp dla Passenger (restart trigger)
mkdir -p tmp
touch tmp/restart.txt

echo "--------------------------------------------------------"
echo "  ✅ Sukces! Aplikacja WULF LEAD.ER jest gotowa."
echo "  Przeładowano Passenger przez tmp/restart.txt"
echo "--------------------------------------------------------"
