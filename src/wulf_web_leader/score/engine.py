from wulf_web_leader.models import CanonicalLead, Verdict


def calculate_lead_score(lead: CanonicalLead) -> tuple[int, Verdict]:
    """Deterministically calculate a lead score (0-100) and verdict ('hot' | 'warm' | 'skip').

    Scoring Logic:
    - Base: 0
    - Dissolved / Inactive registry status: -100 (Immediate disqualification)
    - No website (website_kind == 'none'): +50
    - Social profile or directory listing only: +35
    - Phone number present (actionable outreach): +20
    - Website listed but completely unreachable: +40
    - Website reachable but HTTP-only (no HTTPS): +10
    - Website reachable but missing mobile viewport: +15
    - Website reachable with outdated CMS/generator: +10
    - Public reviews > 10 without own website (if data present): +15
    - Registered < 12 months (if data present): +10

    Verdicts:
    - >= 70: 'hot'
    - >= 45: 'warm'
    - < 45:  'skip'
    """
    if lead.registry_status == "inactive":
        return 0, "skip"

    score = 0

    # 1. Website status
    if lead.website_kind == "none":
        score += 50
    elif lead.website_kind in ("facebook", "instagram", "directory"):
        score += 35
    elif lead.website_kind == "own":
        if lead.audit:
            if not lead.audit.reachable:
                # Broken or abandoned website is a prime prospect
                score += 40
            else:
                if not lead.audit.is_https:
                    score += 10
                if not lead.audit.has_viewport:
                    score += 15
                if lead.audit.generator and any(
                    old in lead.audit.generator.lower()
                    for old in ("joomla", "drupal 7", "typo3 4", "frontpage")
                ):
                    score += 10
    else:  # 'other'
        score += 20

    # 2. Contactability boost (phone present)
    if lead.phone and len(lead.phone.strip()) >= 7:
        score += 20

    # Clamp between 0 and 100
    score = max(0, min(100, score))

    if score >= 70:
        verdict = "hot"
    elif score >= 45:
        verdict = "warm"
    else:
        verdict = "skip"

    return score, verdict
