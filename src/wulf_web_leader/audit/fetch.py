import ipaddress
import re
import socket
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


async def audit_website(
    url: str | None,
    lead_name: str | None = None,
    city: str | None = None,
    phone: str | None = None,
    address: str | None = None,
) -> AuditResult:
    """Safely fetch and audit a business homepage."""
    if not url or not url.strip():
        return AuditResult(reachable=False, error_message="Empty URL")

    target_url = url.strip()
    if not (target_url.startswith("http://") or target_url.startswith("https://")):
        target_url = f"https://{target_url}"

    current_url = target_url
    redirect_count = 0
    final_url = current_url
    last_status = None

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

                async with client.stream("GET", current_url, headers=headers) as response:
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
                    parser = SafeWebsiteHTMLParser()
                    try:
                        parser.feed(content_text)
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

                    emails = set(parser.extracted_emails)
                    if not emails:
                        raw_matches = re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", content_text)
                        for em in raw_matches:
                            em_low = em.lower()
                            if not any(em_low.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".css", ".js")):
                                emails.add(em_low)

                    return AuditResult(
                        reachable=True,
                        status_code=last_status,
                        final_url=final_url,
                        is_https=is_https,
                        title=parser.title,
                        meta_description=parser.meta_description,
                        generator=detected_generator,
                        has_viewport=parser.has_viewport,
                        has_impressum=parser.has_impressum,
                        extracted_phones=sorted(parser.extracted_phones),
                        extracted_emails=sorted(emails),
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
                error_message="Too many redirects",
            )

    except httpx.HTTPError as e:
        return AuditResult(
            reachable=False,
            final_url=final_url,
            status_code=last_status,
            error_message=f"HTTP connection failed: {e.__class__.__name__}",
        )
    except Exception as e:
        return AuditResult(
            reachable=False,
            final_url=final_url,
            status_code=last_status,
            error_message=f"Audit failed: {str(e)}",
        )
