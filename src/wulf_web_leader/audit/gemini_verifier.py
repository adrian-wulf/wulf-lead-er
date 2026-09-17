"""
Gemini API Verifier with live Google Search Grounding for WULF LEAD.ER.

Uses Google AI Studio Free Tier (gemini-3.8-flash) with built-in google_search tool
to perform live web & Google Maps intelligence, extract reputation signals (ratings/reviews),
detect missing/found websites, and compose hyper-personalized web design sales hooks.
"""

import json
import logging
import os
import re
from typing import Any
import httpx

from wulf_web_leader.models import CanonicalLead, GeminiIntel

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")


def is_gemini_available(api_key: str | None = None) -> bool:
    """Check if a Gemini API key is configured either explicitly or via environment."""
    key = api_key or os.environ.get("GEMINI_API_KEY")
    return bool(key and len(key.strip()) > 10)


def get_gemini_api_key(api_key: str | None = None) -> str | None:
    """Resolve Gemini API key from parameter or environment."""
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if key and key.strip():
        return key.strip()
    return None


async def verify_lead_with_gemini(
    lead: CanonicalLead,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    timeout: float = 30.0,
) -> GeminiIntel:
    """
    Verify a business lead using Google AI Studio Gemini API with live Google Search Grounding.

    Returns a structured GeminiIntel object populated with:
    - Google Search existence status
    - Google Maps ratings & review counts
    - Officially discovered website vs social-only profiles
    - Grounding source links directly from Google
    - Hyper-personalized sales pitch for web designers
    """
    resolved_key = get_gemini_api_key(api_key)
    if not resolved_key:
        return GeminiIntel(
            checked=False,
            error="Brak klucza Gemini API. Podaj klucz z Google AI Studio w ustawieniach lub zmiennej GEMINI_API_KEY.",
            model=model,
        )

    url = f"{GEMINI_API_BASE}/{model}:generateContent?key={resolved_key}"

    prompt = f"""Jesteś doświadczonym analitykiem wywiadu rynkowego B2B i doradcą sprzedaży stron internetowych dla agencji interaktywnej.
Twoim zadaniem jest sprawdzenie w Google podanej firmy i ustalenie jej faktycznej obecności cyfrowej.

DANE FIRMY:
- Nazwa: {lead.name}
- Miasto: {lead.city or 'Nieznane'}, Kraj: {lead.country}
- Adres: {lead.address or lead.street or 'Brak dokładnego adresu'}
- Branża: {lead.industry_label}
- Telefon: {lead.phone or 'Brak'}
- Dotychczas znana strona www: {lead.website or 'Brak strony www'}

UŻYJ WYSZUKIWARKI GOOGLE (Google Search & Google Maps), aby ustalić:
1. Czy ta firma rzeczywiście istnieje i prowadzi działalność w tym mieście?
2. Czy firma posiada oficjalną domenę/stronę www? (jeśli w wynikach Google znajdziesz stronę, której nie ma powyżej, podaj jej pełny adres URL).
3. Czy firma posiada wizytówkę w Google Moja Firma / Google Maps? Jaka jest ocena w gwiazdkach (np. 4.8) i ile posiada opinii (np. 42)? Jeśli brak ocen lub wizytówki, wstaw null.
4. Czy firma posiada profile w mediach społecznościowych (Facebook, Instagram itp.)?
5. Sformułuj zwięzłą (2-3 zdania) diagnozę obecności cyfrowej firmy dla web developera (summary).
6. Sformułuj konkretny, naturalny i perswazyjny pitch sprzedażowy (ai_pitch) dla web designera. Pitch musi nawiązywać do faktów z Google (np. wysokie oceny zadowolonych klientów w Google Maps, a jednocześnie brak własnej strony z ofertą, lub stara strona bez wersji mobilnej).

ODPOWIEDZ WYŁĄCZNIE W FORMACIE CZYSTEGO JSON (bez znaczników markdown ```json, bez wstępów):
{{
  "found_in_google": true,
  "google_rating": 4.8,
  "google_reviews_count": 35,
  "discovered_website": "https://przyklad.pl",
  "social_profiles": ["https://facebook.com/przyklad"],
  "summary": "Firma posiada bardzo dobrą reputację lokalną (ocena 4.8 w Google Maps), ale nie ma własnej domeny, posiłkując się wyłącznie fanpage'em na Facebooku.",
  "ai_pitch": "Dzień dobry! Zauważyłem, że w Google Maps macie znakomitą ocenę 4.8 i mnóstwo pochwał od klientów z Rzeszowa. Szkoda jednak, że szukając Was w sieci, trafiają tylko na Facebooka bez pełnego cennika i formularza wyceny..."
}}
"""

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "tools": [
            {"google_search": {}}
        ],
        "generationConfig": {
            "temperature": 0.2,
        }
    }

    headers = {
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)

            # Check if search grounding hit quota or tier restriction (RESOURCE_EXHAUSTED / 429 / 403)
            if (resp.status_code in (429, 403) or "RESOURCE_EXHAUSTED" in resp.text) and "tools" in payload:
                logger.info("Grounding quota exceeded or blocked; falling back to direct gemini-3.8-flash prompt...")
                payload_fallback = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2},
                }
                resp = await client.post(url, headers=headers, json=payload_fallback)

            if resp.status_code == 429:
                return GeminiIntel(
                    checked=False,
                    error="Przekroczono limit zapytań darmowego API Gemini (15 RPM). Odczekaj chwilę przed kolejnym zapytaniem.",
                    model=model,
                )
            elif resp.status_code == 400:
                err_text = resp.text
                return GeminiIntel(
                    checked=False,
                    error=f"Nieprawidłowy klucz API Gemini lub błąd zapytania (HTTP 400): {err_text[:150]}",
                    model=model,
                )
            elif resp.status_code != 200:
                return GeminiIntel(
                    checked=False,
                    error=f"Google AI Studio zwróciło błąd HTTP {resp.status_code}: {resp.text[:150]}",
                    model=model,
                )

            data = resp.json()

            # Parse candidate response
            candidates = data.get("candidates", [])
            if not candidates:
                return GeminiIntel(
                    checked=False,
                    error="Brak odpowiedzi od modelu Gemini.",
                    model=model,
                )

            first_candidate = candidates[0]
            content = first_candidate.get("content", {})
            parts = content.get("parts", [])
            raw_text = parts[0].get("text", "") if parts else ""

            # Extract search queries & grounding sources
            grounding = first_candidate.get("groundingMetadata", {})
            search_queries = grounding.get("webSearchQueries", [])
            raw_chunks = grounding.get("groundingChunks", [])
            grounding_sources: list[dict[str, str]] = []

            for chunk in raw_chunks:
                web_info = chunk.get("web", {})
                if web_info.get("uri"):
                    grounding_sources.append({
                        "title": web_info.get("title") or web_info.get("uri"),
                        "url": web_info.get("uri"),
                    })

            # Clean JSON text from any markdown fences
            clean_json = raw_text.strip()
            clean_json = re.sub(r"^```(?:json)?\s*", "", clean_json, flags=re.MULTILINE)
            clean_json = re.sub(r"\s*```$", "", clean_json, flags=re.MULTILINE)
            clean_json = clean_json.strip()

            # Extract json object if there is leading/trailing text
            json_match = re.search(r"\{.*\}", clean_json, re.DOTALL)
            if json_match:
                clean_json = json_match.group(0)

            parsed_data: dict[str, Any] = {}
            try:
                parsed_data = json.loads(clean_json)
            except Exception as parse_err:
                logger.warning("Could not parse JSON from Gemini response: %s (Raw: %s)", parse_err, raw_text[:200])
                # Graceful fallback: use raw text as summary
                return GeminiIntel(
                    checked=True,
                    found_in_google=True,
                    summary=raw_text[:300],
                    search_queries=search_queries,
                    grounding_sources=grounding_sources[:5],
                    model=model,
                )

            # Normalizing fields
            found_in_google = bool(parsed_data.get("found_in_google", True))
            raw_rating = parsed_data.get("google_rating")
            rating = None
            if raw_rating is not None:
                try:
                    rating = float(raw_rating)
                except (ValueError, TypeError):
                    rating = None

            raw_reviews = parsed_data.get("google_reviews_count")
            reviews_count = None
            if raw_reviews is not None:
                try:
                    reviews_count = int(raw_reviews)
                except (ValueError, TypeError):
                    reviews_count = None

            discovered_web = parsed_data.get("discovered_website")
            if discovered_web:
                discovered_web = str(discovered_web).strip()
                if discovered_web.lower() in ("brak", "null", "none", "-", ""):
                    discovered_web = None
                elif not discovered_web.startswith(("http://", "https://")) and "." in discovered_web:
                    discovered_web = f"https://{discovered_web}"

            socials = parsed_data.get("social_profiles", [])
            if not isinstance(socials, list):
                socials = [str(socials)] if socials else []

            summary = parsed_data.get("summary") or ""
            ai_pitch = parsed_data.get("ai_pitch") or ""

            return GeminiIntel(
                checked=True,
                found_in_google=found_in_google,
                google_rating=rating,
                google_reviews_count=reviews_count,
                discovered_website=discovered_web if discovered_web and discovered_web.startswith("http") else None,
                social_profiles=[s for s in socials if isinstance(s, str) and s.startswith("http")],
                summary=summary.strip(),
                ai_pitch=ai_pitch.strip(),
                search_queries=search_queries,
                grounding_sources=grounding_sources[:6],
                model=model,
            )

    except httpx.TimeoutException:
        return GeminiIntel(
            checked=False,
            error="Przekroczono limit czasu oczekiwania na odpowiedź Google AI Studio (Timeout 30s).",
            model=model,
        )
    except Exception as exc:
        logger.exception("Error during Gemini lead verification: %s", exc)
        return GeminiIntel(
            checked=False,
            error=f"Błąd komunikacji z Google AI Studio: {exc}",
            model=model,
        )
