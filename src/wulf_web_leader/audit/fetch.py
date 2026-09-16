import ipaddress
import re
import socket
import time
from urllib.parse import urlparse
import httpx

from wulf_web_leader.models import AuditResult
from wulf_web_leader.audit.parser import SafeWebsiteHTMLParser
from wulf_web_leader.audit.verifier import check_is_placeholder, verify_entity_match

FORBIDDEN_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("::ffff:0:0/96"),
]

MAX_BODY_BYTES = 1_048_576  # 1MB
MAX_REDIRECTS = 5
AUDIT_TIMEOUT = httpx.Timeout(connect=3.0, read=5.0, write=3.0, pool=3.0)
AUDIT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 (compatible; wulf-bot/0.3.0)"

_MX_CACHE: dict[str, bool] = {}


def is_ip_allowed(ip_str: str) -> bool:
    """Verify IP is public and not an internal/private/link-local address."""
    try:
        ip = ipaddress.ip_address(ip_str)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
        for net in FORBIDDEN_NETWORKS:
            if ip in net:
                return False
        return True
    except ValueError:
        return False


def validate_url_safety(url: str) -> tuple[bool, str | None]:
    """Validate that the URL scheme and resolved IP address are safe from SSRF."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False, f"Unsupported scheme '{parsed.scheme}'"

        hostname = parsed.hostname
        if not hostname:
            return False, "Missing hostname"

        # Resolve host to verify against forbidden IPs
        try:
            addr_info = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            return False, f"Could not resolve host '{hostname}'"

        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            if not is_ip_allowed(ip_str):
                return False, f"IP '{ip_str}' is in private or restricted network"

        return True, None
    except Exception as e:
        return False, str(e)


def verify_email_domain_has_mx(domain: str) -> bool:
    """Verify that an email domain has valid mail exchange (MX) or routable address records."""
    cleaned = domain.strip().lower().rstrip(".")
    if not cleaned or "." not in cleaned:
        return False

    if cleaned in _MX_CACHE:
        return _MX_CACHE[cleaned]

    # Reject obvious invalid, reserved or test domains (RFC 2606)
    if any(cleaned.endswith(tld) for tld in (".invalid", ".test", ".example", ".localhost")):
        _MX_CACHE[cleaned] = False
        return False

    if cleaned in ("localhost", "invalid", "example.com", "example.org", "test.com"):
        _MX_CACHE[cleaned] = False
        return False

    # 1. Local DNS resolution via socket.getaddrinfo (RFC 5321 fallback to A/AAAA)
    try:
        addr_info = socket.getaddrinfo(cleaned, None)
        has_allowed_ip = False
        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            if is_ip_allowed(ip_str):
                has_allowed_ip = True
                break
        if has_allowed_ip:
            _MX_CACHE[cleaned] = True
            return True
    except (socket.gaierror, socket.timeout, OSError):
        pass

    # 2. Fallback to Cloudflare DNS over HTTPS (DoH) for MX records
    try:
        with httpx.Client(timeout=1.5) as client:
            resp = client.get(
                f"https://cloudflare-dns.com/dns-query?name={cleaned}&type=MX",
                headers={"Accept": "application/dns-json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("Status") == 0 and data.get("Answer"):
                    if any(ans.get("type") in (15, 1) for ans in data["Answer"]):
                        _MX_CACHE[cleaned] = True
                        return True
    except Exception:
        pass

    _MX_CACHE[cleaned] = False
    return False


def validate_email_mx(email: str) -> bool:
    """Validate whether an email address has a routable domain."""
    if not email or "@" not in email:
        return False
    parts = email.strip().split("@")
    if len(parts) != 2:
        return False
    user, domain = parts
    if not user or not domain:
        return False
    # Check invalid extensions (static asset files captured as fake emails)
    if any(domain.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".css", ".js")):
        return False
    return verify_email_domain_has_mx(domain)


def filter_emails_with_mx(emails: list[str]) -> list[str]:
    """Filter out emails with invalid or non-routable domains."""
    return [e for e in emails if validate_email_mx(e)]


async def audit_website(
    url: str | None,
    lead_name: str | None = None,
    city: str | None = None,
    phone: str | None = None,
    address: str | None = None,
    country: str | None = None,
) -> AuditResult:
    """Safely fetch and audit a business homepage, with deep-crawling of candidate subpages."""
    if not url or not url.strip():
        return AuditResult(reachable=False, error_message="Empty URL")

    target_url = url.strip()
    if not (target_url.startswith("http://") or target_url.startswith("https://")):
        target_url = f"https://{target_url}"

    current_url = target_url
    redirect_count = 0
    final_url = current_url
    last_status = None
    ttfb_ms: float | None = None

    headers = {
        "User-Agent": AUDIT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pl,de,en-US,en;q=0.9",
    }

    try:
        # verify=False is intentional: many SMB target sites have expired, self-signed, or
        # untrusted SSL certificates. The audit engine specifically evaluates SSL health as a
        # scoring criterion (flagging HTTPS issues) rather than aborting the connection.
        async with httpx.AsyncClient(timeout=AUDIT_TIMEOUT, verify=False, follow_redirects=False) as client:
            while redirect_count <= MAX_REDIRECTS:
                # SSRF guard on every hop
                is_safe, err_msg = validate_url_safety(current_url)
                if not is_safe:
                    return AuditResult(
                        reachable=False,
                        final_url=current_url,
                        error_message=f"SSRF protection blocked: {err_msg}",
                    )

                req_start = time.perf_counter()
                async with client.stream("GET", current_url, headers=headers) as response:
                    measured_ttfb = round((time.perf_counter() - req_start) * 1000)
                    if ttfb_ms is None:
                        ttfb_ms = float(measured_ttfb)

                    last_status = response.status_code
                    final_url = str(response.url)

                    # Handle Redirects manually to ensure SSRF validation on every step
                    if response.is_redirect:
                        redirect_count += 1
                        location = response.headers.get("Location")
                        if not location:
                            break
                        # Join relative URLs
                        current_url = str(httpx.URL(current_url).join(location))
                        continue

                    is_success = (last_status is not None and 200 <= last_status < 400)
                    if not is_success:
                        return AuditResult(
                            reachable=False,
                            status_code=last_status,
                            final_url=final_url,
                            error_message=f"HTTP {last_status}",
                        )

                    # Read streamed body up to MAX_BODY_BYTES
                    content_bytes = bytearray()
                    async for chunk in response.aiter_bytes():
                        content_bytes.extend(chunk)
                        if len(content_bytes) >= MAX_BODY_BYTES:
                            break

                    is_https = final_url.lower().startswith("https://")
                    content_text = content_bytes.decode("utf-8", errors="replace")

                    # Parse HTML safely
                    parser = SafeWebsiteHTMLParser(base_url=final_url)
                    try:
                        parser.feed(content_text)
                        parser.close()
                    except Exception:
                        pass

                    detected_generator = parser.generator
                    if not detected_generator and parser.cms_hints:
                        detected_generator = ", ".join(sorted(parser.cms_hints))

                    # QA Verification: check placeholder and entity match
                    is_placeholder, placeholder_reason = check_is_placeholder(content_text, parser.title)

                    entity_match = False
                    entity_match_score = 0
                    matched_signals = []

                    if lead_name:
                        match_score, signals, _ = verify_entity_match(
                            lead_name=lead_name,
                            city=city,
                            phone=phone,
                            address=address,
                            html_text=content_text,
                        )
                        entity_match_score = match_score
                        matched_signals = signals
                        entity_match = (match_score >= 35)

                    is_de = (country is not None and country.upper() == "DE") or (
                        final_url is not None and (urlparse(final_url).hostname or "").endswith(".de")
                    )

                    phones = set(parser.extracted_phones)
                    raw_emails = set(parser.extracted_emails)
                    if not raw_emails:
                        raw_matches = re.findall(
                            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", content_text
                        )
                        for em in raw_matches:
                            em_low = em.lower()
                            if not any(em_low.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".css", ".js")):
                                raw_emails.add(em_low)

                    site_hostname = (urlparse(final_url).hostname or "").lower()
                    verified_emails: set[str] = set()
                    for em in raw_emails:
                        domain = em.split("@")[-1].lower() if "@" in em else ""
                        if site_hostname and (domain == site_hostname or domain.endswith("." + site_hostname)):
                            verified_emails.add(em)
                        elif validate_email_mx(em):
                            verified_emails.add(em)

                    representative_name = parser.representative_name
                    social_links = dict(parser.social_links)
                    has_impressum = parser.has_impressum

                    # Safe deep-crawling: if missing email, phone, or (in DE) representative_name
                    needs_deep_crawl = (not verified_emails) or (not phones) or (is_de and not representative_name)

                    if needs_deep_crawl and parser.candidate_subpages:
                        def _candidate_priority(sub_path: str) -> tuple[int, str]:
                            sub_low = sub_path.lower()
                            if is_de and not representative_name and "impressum" in sub_low:
                                return (0, sub_path)
                            if "kontakt" in sub_low or "contact" in sub_low:
                                return (1, sub_path)
                            if "impressum" in sub_low:
                                return (2, sub_path)
                            if any(k in sub_low for k in ("ueber-uns", "uber-uns", "about", "o-nas")):
                                return (3, sub_path)
                            return (4, sub_path)

                        sorted_candidates = sorted(parser.candidate_subpages, key=_candidate_priority)
                        candidates_to_crawl = sorted_candidates[:2]

                        for sub_path in candidates_to_crawl:
                            try:
                                subpage_url = str(httpx.URL(final_url).join(sub_path))
                                parsed_sub = urlparse(subpage_url)
                                parsed_final = urlparse(final_url)

                                # Enforce same hostname check
                                if (parsed_sub.hostname or "").lower() != (parsed_final.hostname or "").lower():
                                    continue

                                # Enforce SSRF check
                                is_sub_safe, _ = validate_url_safety(subpage_url)
                                if not is_sub_safe:
                                    continue

                                # Fetch subpage with timeout=3.0s, follow_redirects=False, max size 1MB
                                async with client.stream(
                                    "GET",
                                    subpage_url,
                                    headers=headers,
                                    timeout=httpx.Timeout(connect=3.0, read=3.0, write=3.0, pool=3.0),
                                ) as sub_resp:
                                    if not (200 <= sub_resp.status_code < 300):
                                        continue

                                    sub_bytes = bytearray()
                                    async for chunk in sub_resp.aiter_bytes():
                                        sub_bytes.extend(chunk)
                                        if len(sub_bytes) >= MAX_BODY_BYTES:
                                            break

                                    sub_text = sub_bytes.decode("utf-8", errors="replace")
                                    sub_parser = SafeWebsiteHTMLParser(base_url=subpage_url)
                                    try:
                                        sub_parser.feed(sub_text)
                                        sub_parser.close()
                                    except Exception:
                                        pass

                                    # Merge extracted phones
                                    phones.update(sub_parser.extracted_phones)

                                    # Merge extracted emails
                                    sub_raw_emails = set(sub_parser.extracted_emails)
                                    if not sub_raw_emails:
                                        sub_matches = re.findall(
                                            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", sub_text
                                        )
                                        for em in sub_matches:
                                            em_low = em.lower()
                                            if not any(em_low.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".css", ".js")):
                                                sub_raw_emails.add(em_low)

                                    for em in sub_raw_emails:
                                        domain = em.split("@")[-1].lower() if "@" in em else ""
                                        if site_hostname and (domain == site_hostname or domain.endswith("." + site_hostname)):
                                            verified_emails.add(em)
                                        elif validate_email_mx(em):
                                            verified_emails.add(em)

                                    # Merge social links
                                    for platform, link in sub_parser.social_links.items():
                                        if platform not in social_links:
                                            social_links[platform] = link

                                    # Merge representative name
                                    if not representative_name and sub_parser.representative_name:
                                        representative_name = sub_parser.representative_name

                                    if sub_parser.has_impressum:
                                        has_impressum = True

                                    parser.detected_pixels.update(sub_parser.detected_pixels)

                                    # Stop early if we have gathered all missing contact & representative data
                                    if verified_emails and phones and (not is_de or representative_name):
                                        break
                            except Exception:
                                pass

                    return AuditResult(
                        reachable=True,
                        status_code=last_status,
                        final_url=final_url,
                        is_https=is_https,
                        title=parser.title,
                        meta_description=parser.meta_description,
                        generator=detected_generator,
                        has_viewport=parser.has_viewport,
                        has_impressum=has_impressum,
                        extracted_phones=sorted(phones),
                        extracted_emails=sorted(verified_emails),
                        representative_name=representative_name,
                        social_links=social_links,
                        detected_pixels=sorted(parser.detected_pixels),
                        ttfb_ms=ttfb_ms,
                        is_placeholder=is_placeholder,
                        placeholder_reason=placeholder_reason,
                        entity_match=entity_match,
                        entity_match_score=entity_match_score,
                        matched_signals=matched_signals,
                    )

            # Exceeded redirect loop
            return AuditResult(
                reachable=False,
                status_code=last_status,
                final_url=final_url,
                ttfb_ms=ttfb_ms,
                error_message="Too many redirects",
            )

    except httpx.HTTPError as e:
        return AuditResult(
            reachable=False,
            final_url=final_url,
            status_code=last_status,
            ttfb_ms=ttfb_ms,
            error_message=f"HTTP connection failed: {e.__class__.__name__}",
        )
    except Exception as e:
        return AuditResult(
            reachable=False,
            final_url=final_url,
            status_code=last_status,
            ttfb_ms=ttfb_ms,
            error_message=f"Audit failed: {str(e)}",
        )
