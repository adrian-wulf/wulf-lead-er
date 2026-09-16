"""German OffeneRegister Local SQLite Dump Adapter.

Enriches German leads (GmbH, UG, e.K.) using an offline SQLite database dump
from OffeneRegister.de, without any live scraping of handelsregister.de.
"""

from pathlib import Path
import os
import sqlite3
import logging
from wulf_web_leader.models import CanonicalLead

logger = logging.getLogger(__name__)


class OffeneRegisterAdapter:
    """Adapter for offline German commercial register queries via SQLite dump."""

    def __init__(self, db_path: str | Path | None = None):
        env_path = os.environ.get("OFFENEREGISTER_DB_PATH")
        target_path = db_path or env_path
        self.db_path = Path(target_path) if target_path else None

    def is_available(self) -> bool:
        """Returns True if the local SQLite file exists."""
        return bool(self.db_path and self.db_path.is_file())

    def enrich_lead(self, lead: CanonicalLead) -> CanonicalLead:
        """Query local SQLite database for company status."""
        if not self.is_available():
            return lead

        try:
            with sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True) as conn:
                cursor = conn.cursor()
                query = "SELECT current_status, company_number FROM company WHERE name LIKE ? COLLATE NOCASE LIMIT 1"
                cursor.execute(query, (f"%{lead.name}%",))
                row = cursor.fetchone()
                if not row:
                    cursor.execute(
                        "SELECT current_status, company_number FROM company WHERE name = ? COLLATE NOCASE LIMIT 1",
                        (lead.name,),
                    )
                    row = cursor.fetchone()

                if row:
                    status_raw, company_number = row
                    status_lower = (status_raw or "").lower()

                    if any(
                        term in status_lower
                        for term in ("cancelled", "gelöscht", "aufgelöst", "in liquidation", "erloschen", "beendet")
                    ):
                        lead.registry_status = "inactive"
                    elif any(
                        term in status_lower
                        for term in ("currently registered", "eingetragen", "aktiv", "besteht")
                    ):
                        lead.registry_status = "active"

                    if company_number:
                        lead.source_id = f"hr/{company_number}"
        except Exception as e:
            logger.debug("Error querying OffeneRegister SQLite for %s: %s", lead.name, e)

        return lead

    def enrich_leads(self, leads: list[CanonicalLead]) -> list[CanonicalLead]:
        """Enrich a batch of leads using local SQLite queries."""
        if not self.is_available() or not leads:
            return leads

        for lead in leads:
            self.enrich_lead(lead)
        return leads
