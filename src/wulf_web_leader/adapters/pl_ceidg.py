"""Polish CEIDG Hurtownia REST API Adapter (Planned for v1.1).

Uses dane.biznes.gov.pl JWT authentication for enrichment.
Flagged / optional enrichment source.
"""

from wulf_web_leader.models import CanonicalLead


class CEIDGAdapter:
    """Stub adapter for CEIDG Hurtownia REST integration."""

    def __init__(self, api_token: str | None = None):
        self.api_token = api_token

    def is_available(self) -> bool:
        return bool(self.api_token)

    async def enrich_lead(self, lead: CanonicalLead) -> CanonicalLead:
        """Enrich an existing lead with official registration status and PKD codes."""
        if not self.is_available():
            return lead
        # v1.1 implementation will query CEIDG by name / NIP
        return lead
