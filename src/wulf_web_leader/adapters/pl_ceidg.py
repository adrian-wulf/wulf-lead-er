"""Polish CEIDG Hurtownia REST API Adapter.

Uses dane.biznes.gov.pl JWT authentication for enrichment.
Flagged / optional enrichment source with graceful fallback.
"""

import os
import asyncio
import logging
import httpx
from wulf_web_leader.models import CanonicalLead
from wulf_web_leader.adapters.osm import normalize_phone_number

logger = logging.getLogger(__name__)

CEIDG_API_BASE = "https://dane.biznes.gov.pl/api/ceidg/v2/firmy"


class CEIDGAdapter:
    """Adapter for CEIDG Hurtownia REST integration with JWT authentication."""

    def __init__(
        self,
        api_token: str | None = None,
        base_url: str = CEIDG_API_BASE,
        max_rps: float = 3.0,
    ):
        self.api_token = api_token or os.environ.get("CEIDG_API_TOKEN")
        self.base_url = base_url
        self.max_rps = max_rps
        self._lock = asyncio.Lock()
        self._last_request_time: float = 0.0

    def is_available(self) -> bool:
        return bool(self.api_token and self.api_token.strip())

    async def _throttle(self) -> None:
        if self.max_rps <= 0:
            return
        async with self._lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            min_interval = 1.0 / self.max_rps
            elapsed = now - self._last_request_time
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
            self._last_request_time = loop.time()

    async def enrich_lead(self, lead: CanonicalLead, client: httpx.AsyncClient | None = None) -> CanonicalLead:
        """Enrich an existing lead with official registration status and PKD codes."""
        if not self.is_available():
            return lead

        await self._throttle()

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
            "User-Agent": "wulf-web-leader/0.3.0",
        }

        params = {"nazwa": lead.name}
        if lead.city:
            params["miasto"] = lead.city

        try:
            if client:
                response = await client.get(self.base_url, headers=headers, params=params)
            else:
                async with httpx.AsyncClient(timeout=10.0) as local_client:
                    response = await local_client.get(self.base_url, headers=headers, params=params)

            if response.status_code == 200:
                data = response.json()
                firmy = data.get("firmy", [])
                if firmy:
                    firma = firmy[0]
                    status_str = (firma.get("status") or "").upper()
                    if status_str in ("AKTYWNY", "ACTIVE"):
                        lead.registry_status = "active"
                    elif status_str in ("ZAWIESZONY", "WYKRESLONY", "INACTIVE", "ZAMKNIETY"):
                        lead.registry_status = "inactive"

                    pkd = firma.get("glownyPkd") or firma.get("pkd")
                    if pkd and not lead.industry_code:
                        lead.industry_code = str(pkd)

                    raw_phone = firma.get("telefon")
                    if raw_phone and not lead.phone:
                        lead.phone = normalize_phone_number(raw_phone, "PL")
            elif response.status_code in (429, 503):
                logger.warning("CEIDG API returned status %s, fallback to OSM data without raising", response.status_code)
            else:
                logger.debug("CEIDG returned status %s for %s", response.status_code, lead.name)
        except Exception as e:
            logger.debug("Error querying CEIDG for %s: %s", lead.name, e)

        return lead

    async def enrich_leads(self, leads: list[CanonicalLead]) -> list[CanonicalLead]:
        """Enrich a list of leads in batch, sharing client and respecting throttle limits."""
        if not self.is_available() or not leads:
            return leads

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                for lead in leads:
                    await self.enrich_lead(lead, client=client)
        except Exception as e:
            logger.debug("Error in batch CEIDG enrichment: %s", e)

        return leads
