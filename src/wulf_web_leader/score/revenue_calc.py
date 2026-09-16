"""
WULF LEAD.ER // Kalkulator Utraconych Przychodów i Strat Konwersji (Revenue Loss Estimator).

Przekłada usterki techniczne (czas ładowania, brak RWD, błędy SSL, brak witryny)
na konkretne, bezlitosne liczby finansowe, stanowiące twardy argument w rozmowie z klientem.
"""

from typing import Dict, Any, Optional

# Benchmarki branżowe dla lokalnego rynku (Polska / Niemcy)
VERTICAL_BENCHMARKS: Dict[str, Dict[str, Any]] = {
    "plumbers": {
        "label": "Usługi hydrauliczne",
        "avg_order_value_pln": 420,
        "avg_order_value_eur": 180,
        "est_monthly_searches": 450,
        "urgency_factor": 1.4,  # nagłe awarie, klient nie czeka na wolną stronę
    },
    "auto_repair": {
        "label": "Warsztat samochodowy",
        "avg_order_value_pln": 580,
        "avg_order_value_eur": 240,
        "est_monthly_searches": 550,
        "urgency_factor": 1.2,
    },
    "hair": {
        "label": "Salon fryzjerski / Barber",
        "avg_order_value_pln": 150,
        "avg_order_value_eur": 55,
        "est_monthly_searches": 800,
        "urgency_factor": 1.0,
    },
    "electricians": {
        "label": "Usługi elektryczne",
        "avg_order_value_pln": 460,
        "avg_order_value_eur": 190,
        "est_monthly_searches": 400,
        "urgency_factor": 1.3,
    },
    "restaurant": {
        "label": "Gastronomia / Restauracja",
        "avg_order_value_pln": 120,
        "avg_order_value_eur": 45,
        "est_monthly_searches": 1200,
        "urgency_factor": 1.1,
    },
    "bakery": {
        "label": "Piekarnia / Cukiernia",
        "avg_order_value_pln": 65,
        "avg_order_value_eur": 25,
        "est_monthly_searches": 600,
        "urgency_factor": 0.9,
    },
    "veterinary": {
        "label": "Gabinet weterynaryjny",
        "avg_order_value_pln": 240,
        "avg_order_value_eur": 95,
        "est_monthly_searches": 500,
        "urgency_factor": 1.3,
    },
    "gym": {
        "label": "Klub fitness / Siłownia",
        "avg_order_value_pln": 190,
        "avg_order_value_eur": 60,
        "est_monthly_searches": 650,
        "urgency_factor": 1.0,
    },
}

DEFAULT_BENCHMARK: Dict[str, Any] = {
    "label": "Usługi lokalne",
    "avg_order_value_pln": 300,
    "avg_order_value_eur": 120,
    "est_monthly_searches": 500,
    "urgency_factor": 1.0,
}


def calculate_lost_revenue(
    vertical: Optional[str] = None,
    country: str = "PL",
    has_website: bool = True,
    is_https: bool = True,
    has_viewport: bool = True,
    load_time_seconds: Optional[float] = None,
    http_error: bool = False,
    is_placeholder: bool = False,
) -> Dict[str, Any]:
    """
    Oblicza estymowaną miesięczną i roczną stratę przychodów spowodowaną usterkami www.
    """
    v_key = (vertical or "").lower().strip()
    bench = VERTICAL_BENCHMARKS.get(v_key, DEFAULT_BENCHMARK)

    is_de = country.upper() == "DE"
    currency = "EUR" if is_de else "PLN"
    avg_ticket = bench["avg_order_value_eur"] if is_de else bench["avg_order_value_pln"]
    monthly_pool = bench["est_monthly_searches"]
    urgency = bench["urgency_factor"]

    # 1. Obliczenie współczynnika utraty ruchu (Leak Rate 0.0 - 0.95)
    leak_rate = 0.0

    if not has_website:
        # Brak witryny = 65% szukających w Google wybiera konkurencję z bezpośrednią stroną
        leak_rate = 0.65
    elif http_error or is_placeholder:
        # Awaria strony lub parking domeny = 85% ucieka natychmiast
        leak_rate = 0.85
    else:
        # Analiza usterek na działającej stronie
        if not is_https:
            leak_rate += 0.22  # Ostrzeżenie "Niezabezpieczona" odstrasza 22% użytkowników
        if not has_viewport:
            leak_rate += 0.38  # Nieczytelna na smartfonie odstrasza 38% mobilnych klientów
        
        # Wpływ prędkości ładowania
        lt = load_time_seconds if load_time_seconds is not None else 3.5
        if lt > 2.0:
            # Badania Google: każda sekunda powyżej 2s podnosi bounce rate o 8-12%
            extra_seconds = min(lt - 2.0, 8.0)
            leak_rate += extra_seconds * 0.08 * urgency

    leak_rate = min(max(leak_rate, 0.05), 0.92)

    # 2. Przeliczenie na utraconych klientów (zakładamy konserwatywną konwersję bazową 3.5%)
    base_conversion = 0.035
    total_potential_clients = monthly_pool * base_conversion
    lost_clients_monthly = max(1, round(total_potential_clients * leak_rate))
    lost_revenue_monthly = round(lost_clients_monthly * avg_ticket)
    lost_revenue_annual = lost_revenue_monthly * 12

    # 3. Gotowy pitch sprzedażowy
    if not has_website:
        pitch = (
            f"Brak własnej witryny kosztuje firmę szacunkowo ok. {lost_clients_monthly} klientów miesięcznie. "
            f"To oznacza wyciek ok. {lost_revenue_monthly:,} {currency} utraconego przychodu każdego miesiąca.".replace(",", " ")
        )
    elif http_error or is_placeholder:
        pitch = (
            f"Awaria strony odcina firmę od ok. {lost_clients_monthly} klientów miesięcznie. "
            f"Szacowana bezpośrednia strata zysku: {lost_revenue_monthly:,} {currency} / miesięcznie.".replace(",", " ")
        )
    elif not has_viewport or not is_https:
        defects = []
        if not has_viewport: defects.append("brak wersji mobilnej")
        if not is_https: defects.append("brak certyfikatu SSL")
        defect_str = " oraz ".join(defects)
        pitch = (
            f"Przez {defect_str} firma traci szacunkowo ok. {lost_clients_monthly} zleceń w miesiącu. "
            f"Roczny ubytek przychodów wynosi ok. {lost_revenue_annual:,} {currency}.".replace(",", " ")
        )
    else:
        pitch = (
            f"Optymalizacja witryny pozwoli odzyskać ok. {lost_clients_monthly} zleceń miesięcznie "
            f"(dodatkowe ok. {lost_revenue_monthly:,} {currency}/miesiąc).".replace(",", " ")
        )

    return {
        "currency": currency,
        "avg_ticket": avg_ticket,
        "leak_percentage": round(leak_rate * 100, 1),
        "lost_clients_monthly": lost_clients_monthly,
        "lost_revenue_monthly": lost_revenue_monthly,
        "lost_revenue_annual": lost_revenue_annual,
        "pitch": pitch,
    }
