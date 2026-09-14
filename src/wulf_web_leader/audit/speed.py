"""
WULF LEAD.ER // Audyt Prędkości i Wydajności Mobilnej (Speed & Core Web Vitals Auditor).

Pobiera dane z oficjalnego Google PageSpeed Insights API (jeśli klucz jest dostępny)
lub wykonuje bezpośredni, precyzyjny pomiar sieciowy TTFB, czasu pobierania i wagi zasobów.
"""

import os
import time
from typing import Dict, Any, Optional
import httpx


def audit_website_speed(url: str, google_api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Sprawdza prędkość i kondycję techniczną strony mobilnej.
    Zwraca ustandaryzowany słownik ze statystykami i oceną wydajności.
    """
    if not url or not isinstance(url, str) or not url.strip():
        return {
            "source": "none",
            "score": 0,
            "mobile_score": 0,
            "performance_score": 0,
            "lcp_seconds": 0.0,
            "ttfb_ms": 0,
            "total_time_ms": 0,
            "page_weight_kb": 0.0,
            "grade": "BRAK STRONY",
            "status_color": "red",
        }

    clean_url = url.strip()
    if not clean_url.startswith(("http://", "https://")):
        clean_url = f"https://{clean_url}"

    key = google_api_key or os.environ.get("GOOGLE_PAGESPEED_API_KEY")

    # 1. Próba z oficjalnym Google PageSpeed Insights API (jeśli skonfigurowany)
    if key:
        try:
            api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={clean_url}&category=PERFORMANCE&strategy=MOBILE&key={key}"
            with httpx.Client(timeout=15.0, verify=False) as client:
                r = client.get(api_url)
                if r.status_code == 200:
                    data = r.json()
                    lh = data.get("lighthouseResult", {})
                    raw_score = lh.get("categories", {}).get("performance", {}).get("score")
                    score = round(raw_score * 100) if raw_score is not None else 50
                    lcp_audit = lh.get("audits", {}).get("largest-contentful-paint", {})
                    lcp_sec = (lcp_audit.get("numericValue", 3500)) / 1000.0

                    grade = "DOBRA" if score >= 85 else ("ŚREDNIA" if score >= 50 else "KRYTYCZNA")
                    status_color = "green" if score >= 85 else ("amber" if score >= 50 else "red")

                    return {
                        "source": "google_api",
                        "score": score,
                        "mobile_score": score,
                        "performance_score": score,
                        "lcp_seconds": round(lcp_sec, 2),
                        "ttfb_ms": round(lh.get("audits", {}).get("server-response-time", {}).get("numericValue", 0)),
                        "total_time_ms": round(lcp_sec * 1000),
                        "page_weight_kb": round(lh.get("audits", {}).get("total-byte-weight", {}).get("numericValue", 0) / 1024.0, 1),
                        "grade": grade,
                        "status_color": status_color,
                    }
        except Exception:
            pass

    # 2. Bezpośredni, niezawodny audyt sieciowy (Direct Probe)
    start_time = time.perf_counter()
    ttfb_ms = 0
    total_time_ms = 0
    page_weight_kb = 0.0

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
        }
        with httpx.Client(timeout=8.0, follow_redirects=True, verify=False) as client:
            req_start = time.perf_counter()
            resp = client.get(clean_url, headers=headers)
            ttfb_ms = round((time.perf_counter() - req_start) * 1000)
            total_time_ms = round((time.perf_counter() - start_time) * 1000)
            page_weight_kb = round(len(resp.content) / 1024.0, 1)

            # Szacowanie Core Web Vitals (LCP) na podstawie TTFB i wagi strony
            lcp_seconds = round((total_time_ms / 1000.0) * 1.35, 2)

            # Obliczanie punktacji 0-100
            score = 100
            if ttfb_ms > 800:
                score -= min(40, int((ttfb_ms - 800) / 40))
            if total_time_ms > 2000:
                score -= min(45, int((total_time_ms - 2000) / 60))
            if page_weight_kb > 1500:
                score -= min(25, int((page_weight_kb - 1500) / 100))

            score = max(10, min(95, score))
            grade = "DOBRA" if score >= 80 else ("ŚREDNIA" if score >= 50 else "KRYTYCZNA")
            status_color = "green" if score >= 80 else ("amber" if score >= 50 else "red")

            return {
                "source": "network_probe",
                "score": score,
                "mobile_score": score,
                "performance_score": score,
                "lcp_seconds": lcp_seconds,
                "ttfb_ms": ttfb_ms,
                "total_time_ms": total_time_ms,
                "page_weight_kb": page_weight_kb,
                "grade": grade,
                "status_color": status_color,
            }
    except Exception:
        return {
            "source": "network_probe_fail",
            "score": 15,
            "mobile_score": 15,
            "performance_score": 15,
            "lcp_seconds": 9.9,
            "ttfb_ms": 0,
            "total_time_ms": 0,
            "page_weight_kb": 0.0,
            "grade": "AWARIA POŁĄCZENIA",
            "status_color": "red",
        }
