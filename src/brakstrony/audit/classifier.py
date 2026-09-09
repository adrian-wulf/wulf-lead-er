from urllib.parse import urlparse
from brakstrony.models import WebsiteKind

FACEBOOK_DOMAINS = {
    "facebook.com",
    "www.facebook.com",
    "m.facebook.com",
    "fb.com",
    "www.fb.com",
    "fb.me",
}

INSTAGRAM_DOMAINS = {
    "instagram.com",
    "www.instagram.com",
    "instagr.am",
}

DIRECTORY_DOMAINS = {
    # Polish directories
    "panoramafirm.pl",
    "www.panoramafirm.pl",
    "pkt.pl",
    "www.pkt.pl",
    "favore.pl",
    "www.favore.pl",
    "oferteo.pl",
    "www.oferteo.pl",
    "aleo.com",
    "www.aleo.com",
    "cylex-polska.pl",
    "www.cylex-polska.pl",
    "zumi.pl",
    "www.zumi.pl",
    "znanylekarz.pl",
    "www.znanylekarz.pl",
    "booksy.com",
    "www.booksy.com",
    "trojmiasto.pl",
    "www.trojmiasto.pl",
    # German directories
    "gelbeseiten.de",
    "www.gelbeseiten.de",
    "dasoertliche.de",
    "www.dasoertliche.de",
    "dastelefonbuch.de",
    "www.dastelefonbuch.de",
    "11880.com",
    "www.11880.com",
    "cylex.de",
    "www.cylex.de",
    "golocal.de",
    "www.golocal.de",
    "jameda.de",
    "www.jameda.de",
    "doctolib.de",
    "www.doctolib.de",
    "kennstdueinen.de",
    "www.kennstdueinen.de",
    "meine-stadt.de",
    "meinestadt.de",
    "www.meinestadt.de",
    # International directory / social platforms
    "yelp.com",
    "www.yelp.com",
    "yelp.pl",
    "yelp.de",
    "tripadvisor.com",
    "tripadvisor.pl",
    "tripadvisor.de",
    "foursquare.com",
    "www.foursquare.com",
    "yellowpages.com",
    "linkedin.com",
    "www.linkedin.com",
}


def classify_website_kind(url: str | None) -> WebsiteKind:
    """Classify website URL into canonical categories: none, own, facebook, instagram, directory, other."""
    if not url or not url.strip():
        return "none"

    cleaned_url = url.strip()
    if not (cleaned_url.startswith("http://") or cleaned_url.startswith("https://")):
        cleaned_url = f"https://{cleaned_url}"

    try:
        parsed = urlparse(cleaned_url)
        hostname = (parsed.hostname or "").lower()
    except Exception:
        return "other"

    if not hostname:
        return "other"

    if hostname in FACEBOOK_DOMAINS or any(hostname.endswith("." + d) for d in FACEBOOK_DOMAINS):
        return "facebook"

    if hostname in INSTAGRAM_DOMAINS or any(hostname.endswith("." + d) for d in INSTAGRAM_DOMAINS):
        return "instagram"

    if hostname in DIRECTORY_DOMAINS or any(hostname.endswith("." + d) for d in DIRECTORY_DOMAINS):
        return "directory"

    # Common generic domain patterns (e.g. valid domain with at least a second level domain)
    if "." in hostname and len(hostname) >= 4:
        return "own"

    return "other"
