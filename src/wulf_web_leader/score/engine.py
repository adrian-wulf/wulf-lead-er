from wulf_web_leader.models import CanonicalLead, Verdict
from wulf_web_leader.adapters.osm import is_corporate_entity, is_joint_stock_or_enterprise


def calculate_lead_score(lead: CanonicalLead) -> tuple[int, Verdict]:
    """Deterministically calculate a lead score (0-100), verdict ('hot' | 'warm' | 'skip'),
    and assign opportunity_type, primary_issue, and confidence.
    """
    if lead.registry_status == "inactive":
        lead.score = 0
        lead.verdict = "skip"
        lead.opportunity_type = "no_website"
        lead.primary_issue = "Podmiot wyrejestrowany / nieaktywny"
        lead.confidence = "high"
        return 0, "skip"

    # Enterprise & Corporate Gate (S.A., AG, SE, KGaA, large holding / Wikipedia enterprise)
    is_enterprise = is_joint_stock_or_enterprise(lead.name)
    if hasattr(lead, "wikipedia_intel") and lead.wikipedia_intel:
        if isinstance(lead.wikipedia_intel, dict) and lead.wikipedia_intel.get("is_enterprise"):
            is_enterprise = True
        elif getattr(lead.wikipedia_intel, "is_enterprise", False):
            is_enterprise = True

    if is_enterprise:
        lead.score = 0
        lead.verdict = "skip"
        lead.confidence = "high"
        if lead.website_kind == "own" and lead.audit and lead.audit.reachable:
            lead.opportunity_type = "modern_active"
            lead.primary_issue = "Podmiot korporacyjny (S.A. / AG) — posiada działającą stronę"
        else:
            lead.opportunity_type = "corporate_enterprise"
            lead.primary_issue = "Podmiot korporacyjny (S.A. / AG) — potencjalny rebranding, fuzja lub domena archiwalna"
        return 0, "skip"

    score = 0
    has_phone = bool(lead.phone and len(lead.phone.strip()) >= 7)
    phone_bonus = 20 if has_phone else 0

    # 0. Placeholder / Parked domain detected by QA
    if lead.qa_status == "placeholder" or (lead.audit and lead.audit.is_placeholder):
        score = 65 + phone_bonus
        lead.opportunity_type = "broken_website"
        reason = (lead.audit.placeholder_reason if lead.audit and lead.audit.placeholder_reason else "Zaślepka serwera / parking")
        lead.primary_issue = f"Nieaktywna domena ({reason})"
        lead.confidence = "high"

    # 0b. Entity mismatch (domain does not belong to company)
    elif lead.qa_status == "mismatch":
        score = 45 + phone_bonus
        lead.opportunity_type = "suspect_unverified"
        lead.primary_issue = "Domena nie zawiera danych firmy (rozbieżność tożsamości)"
        lead.confidence = "low"

    # 1. Broken / Unreachable website
    elif lead.website_kind == "own" and lead.audit and not lead.audit.reachable:
        err = lead.audit.error_message or (f"kod {lead.audit.status_code}" if lead.audit.status_code else "brak odpowiedzi")
        err_lower = err.lower()
        # Differentiate network deadness / timeout / DNS resolution error from active server errors
        is_network_dead = any(
            term in err_lower
            for term in ("connecttimeout", "timed out", "timeout", "nameresolutionerror", "connection refused", "nxdomain", "gaierror")
        )
        if is_network_dead:
            if is_corporate_entity(lead.name):
                score = 25 + (15 if has_phone else 0)
                lead.opportunity_type = "suspect_unverified"
                lead.primary_issue = f"Domena nie odpowiada ({err}) — spółka kapitałowa, prawdopodobnie wygaszona lub nieaktualna"
                lead.confidence = "low"
            else:
                score = 40 + (15 if has_phone else 0)
                lead.opportunity_type = "suspect_unverified"
                lead.primary_issue = f"Domena nie odpowiada ({err}) — podejrzenie wygaszenia lub błąd DNS"
                lead.confidence = "medium"
        else:
            # Active web server application error (500, 502, 503, 404, SSL failure)
            score = 65 + phone_bonus
            lead.opportunity_type = "broken_website"
            lead.primary_issue = f"Awaria strony ({err})"
            lead.confidence = "high"


    # 2. Reachable website with technical / mobile / security flaws
    elif lead.website_kind == "own" and lead.audit and lead.audit.reachable:
        flaws = []
        flaw_pts = 0

        if not lead.audit.has_viewport:
            flaw_pts += 35
            flaws.append("brak wersji na smartfony (RWD)")

        if not lead.audit.is_https:
            flaw_pts += 15
            flaws.append("brak certyfikatu SSL (HTTP)")

        if lead.audit.generator and any(
            old in lead.audit.generator.lower()
            for old in ("joomla", "drupal 7", "typo3 4", "frontpage", "html editor")
        ):
            flaw_pts += 15
            flaws.append(f"stary generator ({lead.audit.generator})")

        if not lead.audit.has_impressum and lead.country == "DE":
            flaw_pts += 10
            flaws.append("brak Impressum")

        score = flaw_pts + phone_bonus

        if flaw_pts >= 50:
            lead.opportunity_type = "critical_redesign"
            lead.primary_issue = f"Pilny redesign: {', '.join(flaws)}"
            lead.confidence = "high"
        elif flaw_pts > 0:
            lead.opportunity_type = "critical_redesign"
            lead.primary_issue = f"Wymaga modernizacji: {', '.join(flaws)}"
            lead.confidence = "medium"
        else:
            lead.opportunity_type = "modern_active"
            lead.primary_issue = "Nowoczesna, działająca witryna"
            lead.confidence = "high"

    # 3. Social media only
    elif lead.website_kind in ("facebook", "instagram"):
        score = 50 + phone_bonus
        lead.opportunity_type = "social_only"
        lead.primary_issue = f"Tylko profil w mediach społecznościowych ({lead.website_kind.capitalize()})"
        lead.confidence = "high"

    # 4. Directory listing only
    elif lead.website_kind == "directory":
        score = 45 + phone_bonus
        lead.opportunity_type = "directory_only"
        lead.primary_issue = "Tylko wpis w katalogu firm"
        lead.confidence = "medium"

    # 5. No website in OSM
    elif lead.website_kind == "none":
        if is_corporate_entity(lead.name) or lead.opportunity_type == "suspect_unverified":
            # Corporate entities (GmbH, Sp. z o.o.) almost always have a website outside OSM.
            # Cap at WARM (max 50 with phone, 30 without) to avoid polluting the high-priority HOT calling list.
            score = 30 + (20 if has_phone else 0)
            lead.opportunity_type = "suspect_unverified"
            lead.primary_issue = "Spółka kapitałowa bez strony w OSM (wymaga weryfikacji)"
            lead.confidence = "low"
        else:
            score = 50 + phone_bonus
            lead.opportunity_type = "no_website"
            lead.primary_issue = "Brak witryny www w rejestrach OpenStreetMap"
            lead.confidence = "medium"

    else:  # other
        score = 20 + phone_bonus
        lead.opportunity_type = "no_website"
        lead.primary_issue = "Nietypowy lub nieokreślony adres www"
        lead.confidence = "low"

    # Clamp score between 0 and 100
    score = max(0, min(100, score))

    if score >= 70:
        verdict = "hot"
    elif score >= 45:
        verdict = "warm"
    else:
        verdict = "skip"

    lead.score = score
    lead.verdict = verdict
    return score, verdict
