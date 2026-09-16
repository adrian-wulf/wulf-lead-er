from typing import Any, Literal
from pydantic import BaseModel, Field, HttpUrl


WebsiteKind = Literal["none", "own", "facebook", "instagram", "directory", "other"]
LeadSource = Literal["osm", "ceidg", "offeneregister", "manual", "google_maps"]
RegistryStatus = Literal["active", "unknown", "inactive"]
Verdict = Literal["hot", "warm", "skip"]
CountryCode = Literal["PL", "DE"]
PhoneType = Literal["mobile", "landline", "unknown"]


OpportunityType = Literal[
    "broken_website",      # Awaria / błąd strony (4xx/5xx/timeout/SSL)
    "critical_redesign",   # Pilny redesign (brak RWD / HTTP / stary CMS)
    "social_only",         # Tylko profil w mediach społecznościowych
    "directory_only",      # Tylko wizytówka w katalogu
    "no_website",          # Prawdopodobny brak strony w rejestrach/OSM
    "suspect_unverified",  # Spółka kapitałowa (GmbH/Sp. z o.o.) bez strony w OSM (wymaga weryfikacji)
    "modern_active",       # Posiada działającą, nowoczesną stronę
    "corporate_enterprise", # Spółka akcyjna / korporacja / rebranding / fuzja (wykluczona z prostego outreachu)
]


class AuditResult(BaseModel):
    """Result of auditing a website URL."""
    reachable: bool = False
    status_code: int | None = None
    final_url: str | None = None
    is_https: bool = False
    title: str | None = None
    meta_description: str | None = None
    generator: str | None = None
    has_viewport: bool = False
    has_impressum: bool = False
    extracted_phones: list[str] = Field(default_factory=list)
    extracted_emails: list[str] = Field(default_factory=list)
    representative_name: str | None = None
    social_links: dict[str, str] = Field(default_factory=dict)
    detected_pixels: list[str] = Field(default_factory=list)
    ttfb_ms: float | None = None
    error_message: str | None = None
    is_placeholder: bool = False
    placeholder_reason: str | None = None
    entity_match: bool = False
    entity_match_score: int = 0
    matched_signals: list[str] = Field(default_factory=list)


class GeminiIntel(BaseModel):
    """Structured intelligence retrieved from Google Search via Gemini API."""
    checked: bool = False
    found_in_google: bool = False
    google_rating: float | None = None
    google_reviews_count: int | None = None
    discovered_website: str | None = None
    social_profiles: list[str] = Field(default_factory=list)
    summary: str | None = None
    ai_pitch: str | None = None
    search_queries: list[str] = Field(default_factory=list)
    grounding_sources: list[dict[str, str]] = Field(default_factory=list)
    model: str = "gemini-3.8-flash"
    error: str | None = None


class CanonicalLead(BaseModel):
    """Canonical lead data model used across all country adapters and pipeline stages."""
    country: CountryCode
    name: str
    lat: float | None = None
    lon: float | None = None
    address: str | None = None
    street: str | None = None
    city: str | None = None
    postcode: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    website_kind: WebsiteKind = "none"
    website_source: Literal["osm_website", "email_domain", "candidate_discovery", "wikipedia_discovery", "google_osint", "google_maps", "none"] = "none"
    opportunity_type: OpportunityType = "no_website"
    primary_issue: str | None = None
    confidence: Literal["high", "medium", "low"] = "high"
    qa_status: Literal["verified", "placeholder", "mismatch", "unverified"] = "unverified"
    qa_notes: str | None = None
    source: LeadSource = "osm"
    source_id: str = ""
    industry_code: str | None = None  # PKD or WZ
    industry_label: str
    registry_status: RegistryStatus = "unknown"
    score: int = Field(default=0, ge=0, le=100)
    verdict: Verdict = "skip"
    hooks: list[str] = Field(default_factory=list)
    rating: float | None = None
    reviews_count: int | None = None
    raw_tags: dict[str, Any] = Field(default_factory=dict)
    status_kontaktu: str | None = None
    notatki: str | None = None
    data_kontaktu: str | None = None
    audit: AuditResult | None = None
    gemini_intel: GeminiIntel | None = None
    wikipedia_intel: Any | None = None
    owner_name: str | None = None
    nip: str | None = None
    regon: str | None = None
    phone_type: Literal["mobile", "landline", "unknown"] = "unknown"
    whatsapp_url: str | None = None
    google_maps_url: str | None = None
    open_state: str | None = None



class CountryVerticalConfig(BaseModel):
    query: str
    label: str
    pkd: list[str] = Field(default_factory=list)
    wz: list[str] = Field(default_factory=list)
    osm: list[str] = Field(default_factory=list)


class VerticalAliases(BaseModel):
    pl: list[str] = Field(default_factory=list)
    de: list[str] = Field(default_factory=list)


class VerticalDefinition(BaseModel):
    id: str
    name: str
    aliases: VerticalAliases = Field(default_factory=VerticalAliases)
    pl: CountryVerticalConfig
    de: CountryVerticalConfig
