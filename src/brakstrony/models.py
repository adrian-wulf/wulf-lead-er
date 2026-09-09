from typing import Literal
from pydantic import BaseModel, Field, HttpUrl


WebsiteKind = Literal["none", "own", "facebook", "instagram", "directory", "other"]
LeadSource = Literal["osm", "ceidg", "offeneregister", "manual"]
RegistryStatus = Literal["active", "unknown", "inactive"]
Verdict = Literal["hot", "warm", "skip"]
CountryCode = Literal["PL", "DE"]


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
    error_message: str | None = None


class CanonicalLead(BaseModel):
    """Canonical lead data model used across all country adapters and pipeline stages."""
    country: CountryCode
    name: str
    lat: float | None = None
    lon: float | None = None
    address: str | None = None
    city: str | None = None
    postcode: str | None = None
    phone: str | None = None
    website: str | None = None
    website_kind: WebsiteKind = "none"
    source: LeadSource = "osm"
    source_id: str
    industry_code: str | None = None  # PKD or WZ
    industry_label: str
    registry_status: RegistryStatus = "unknown"
    score: int = Field(default=0, ge=0, le=100)
    verdict: Verdict = "skip"
    hooks: list[str] = Field(default_factory=list)
    audit: AuditResult | None = None


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
