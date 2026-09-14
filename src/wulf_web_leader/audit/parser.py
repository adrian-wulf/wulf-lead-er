from html.parser import HTMLParser
import re
from urllib.parse import urlparse

CANDIDATE_SUBPAGE_KEYWORDS = (
    "/kontakt",
    "/contact",
    "/impressum",
    "/o-nas",
    "/about",
    "/ueber-uns",
    "/firma",
    "/team",
)

EXCLUDED_EXTENSIONS = (
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".svg",
    ".gif",
    ".zip",
    ".doc",
    ".docx",
    ".css",
    ".js",
    ".xml",
    ".mp4",
    ".mp3",
)

REPRESENTATIVE_PATTERNS = [
    re.compile(
        r"(?i:vertreten\s+durch(?:\s+(?:die|den|das))?(?:\s+gesch(?:ä|ae|a)ftsf(?:ü|ue|u)hr(?:er(?:in)?)?)?):?\s*"
        r"(?:(?i:dr\.|prof\.|dipl\.-[a-z0-9]+)[ \t]+)?"
        r"([A-ZÄÖÜ][a-zäöüß]+(?:[- \t]+(?:(?i:von|van|de|zu)[ \t]+)?[A-ZÄÖÜ][a-zäöüß]+)+)"
    ),
    re.compile(
        r"(?i:gesch(?:ä|ae|a)ftsf(?:ü|ue|u)hr(?:er(?:in)?|ung)):?\s*"
        r"(?:(?i:dr\.|prof\.|dipl\.-[a-z0-9]+)[ \t]+)?"
        r"([A-ZÄÖÜ][a-zäöüß]+(?:[- \t]+(?:(?i:von|van|de|zu)[ \t]+)?[A-ZÄÖÜ][a-zäöüß]+)+)"
    ),
    re.compile(
        r"(?i:inhaber(?:in)?):?\s*"
        r"(?:(?i:dr\.|prof\.|dipl\.-[a-z0-9]+)[ \t]+)?"
        r"([A-ZÄÖÜ][a-zäöüß]+(?:[- \t]+(?:(?i:von|van|de|zu)[ \t]+)?[A-ZÄÖÜ][a-zäöüß]+)+)"
    ),
    re.compile(
        r"(?i:vorstand):?\s*"
        r"(?:(?i:dr\.|prof\.|dipl\.-[a-z0-9]+)[ \t]+)?"
        r"([A-ZÄÖÜ][a-zäöüß]+(?:[- \t]+(?:(?i:von|van|de|zu)[ \t]+)?[A-ZÄÖÜ][a-zäöüß]+)+)"
    ),
]

FORBIDDEN_NAME_WORDS = {
    "gmbh",
    "ag",
    "gbr",
    "ug",
    "kg",
    "ek",
    "e.k.",
    "register",
    "amtsgericht",
    "hrb",
    "hra",
    "ust",
    "telefon",
    "telefax",
    "email",
    "e-mail",
    "haftung",
    "datenschutz",
}


class SafeWebsiteHTMLParser(HTMLParser):
    """Non-backtracking streaming HTML parser for website metadata and security signals."""

    def __init__(self, base_url: str | None = None):
        super().__init__()
        self.base_url = base_url
        self.in_title = False
        self.title_parts: list[str] = []
        self.meta_description: str | None = None
        self.has_viewport: bool = False
        self.generator: str | None = None
        self.has_impressum: bool = False
        self.extracted_phones: set[str] = set()
        self.extracted_emails: set[str] = set()
        self.candidate_subpages: set[str] = set()
        self.detected_pixels: set[str] = set()
        self.social_links: dict[str, str] = {}
        self._representative_name: str | None = None
        self.cms_hints: set[str] = set()
        self._current_tag = ""
        self._in_anchor = False
        self._current_anchor_text: list[str] = []
        self._current_anchor_href = ""
        self._in_script_or_style = False
        self._text_chunks: list[str] = []

    @property
    def pixels(self) -> list[str]:
        return sorted(self.detected_pixels)

    def get_detected_pixels(self) -> list[str]:
        return sorted(self.detected_pixels)

    @property
    def title(self) -> str | None:
        raw = " ".join(self.title_parts).strip()
        return raw[:200] if raw else None

    @property
    def representative_name(self) -> str | None:
        if not self._representative_name:
            self._extract_representative_name()
        return self._representative_name

    @representative_name.setter
    def representative_name(self, value: str | None) -> None:
        self._representative_name = value

    def _extract_representative_name(self) -> None:
        if self._representative_name:
            return
        full_text = "\n".join(self._text_chunks)
        for pattern in REPRESENTATIVE_PATTERNS:
            m = pattern.search(full_text)
            if m:
                candidate = m.group(1).strip()
                candidate = re.sub(r"[ \t]+", " ", candidate)
                words = candidate.split()
                if 2 <= len(words) <= 4 and 4 <= len(candidate) <= 60:
                    words_lower = {w.lower().rstrip(".,") for w in words}
                    if not (words_lower & FORBIDDEN_NAME_WORDS):
                        self._representative_name = candidate
                        break

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        self._current_tag = tag_lower
        attr_dict = {k.lower(): (v or "").strip() for k, v in attrs if k}

        for v in attr_dict.values():
            if v:
                self._detect_pixels_from_string(v)

        if tag_lower in ("script", "style"):
            self._in_script_or_style = True

        elif tag_lower == "title":
            self.in_title = True

        elif tag_lower == "meta":
            name = attr_dict.get("name", "").lower()
            prop = attr_dict.get("property", "").lower()
            content = attr_dict.get("content", "").strip()

            if name == "viewport":
                self.has_viewport = True
            elif name in ("description", "og:description") or prop == "og:description":
                if not self.meta_description and content:
                    self.meta_description = content[:300]
            elif name == "generator" and content:
                self.generator = content[:100]
                self._detect_cms_from_string(content)

        elif tag_lower == "a":
            href = attr_dict.get("href", "").strip()
            self._in_anchor = True
            self._current_anchor_href = href
            self._current_anchor_text = []

            href_lower = href.lower()

            # Check tel:
            if href_lower.startswith("tel:"):
                phone = href[4:].strip()
                if phone:
                    self.extracted_phones.add(phone)

            # Check mailto:
            elif href_lower.startswith("mailto:"):
                email = href[7:].split("?")[0].strip()
                if email:
                    self.extracted_emails.add(email)

            # Check impressum in href
            if "impressum" in href_lower:
                self.has_impressum = True

            # Candidate subpages and social media links
            if not href_lower.startswith(("mailto:", "tel:", "javascript:", "#")) and href != "":
                # 1. Social media links
                is_share = any(s in href_lower for s in ("sharer", "share.php", "sharearticle", "intent/tweet", "/share/"))
                if not is_share:
                    platform = None
                    if "facebook.com" in href_lower or "fb.com" in href_lower:
                        platform = "facebook"
                    elif "instagram.com" in href_lower:
                        platform = "instagram"
                    elif "linkedin.com" in href_lower:
                        platform = "linkedin"
                    elif "tiktok.com" in href_lower:
                        platform = "tiktok"
                    elif "youtube.com" in href_lower or "youtu.be" in href_lower:
                        platform = "youtube"

                    if platform:
                        is_generic = href_lower.rstrip("/").endswith(
                            ("facebook.com", "fb.com", "instagram.com", "linkedin.com", "tiktok.com", "youtube.com")
                        )
                        existing = self.social_links.get(platform)
                        if not existing:
                            self.social_links[platform] = href
                        elif not is_generic and existing.rstrip("/").endswith(
                            ("facebook.com", "fb.com", "instagram.com", "linkedin.com", "tiktok.com", "youtube.com")
                        ):
                            self.social_links[platform] = href

                # 2. Candidate subpages
                parsed = urlparse(href)
                path = parsed.path.lower()
                has_bad_ext = any(path.endswith(ext) for ext in EXCLUDED_EXTENSIONS)

                is_external = False
                if parsed.netloc:
                    if self.base_url:
                        base_host = (urlparse(self.base_url).hostname or "").lower()
                        sub_host = (parsed.hostname or "").lower()
                        if base_host != sub_host:
                            is_external = True
                    else:
                        is_external = True

                if not has_bad_ext and not is_external:
                    matches_candidate = (
                        any(kw in href_lower for kw in CANDIDATE_SUBPAGE_KEYWORDS)
                        or any(path.startswith(kw.lstrip("/") + ".") for kw in CANDIDATE_SUBPAGE_KEYWORDS)
                        or path.rstrip("/") in ("kontakt", "contact", "impressum", "o-nas", "about", "ueber-uns", "firma", "team")
                    )
                    if matches_candidate:
                        self.candidate_subpages.add(href)

        elif tag_lower in ("script", "link"):
            src = attr_dict.get("src", "") or attr_dict.get("href", "")
            if src:
                self._detect_cms_from_string(src)

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in ("script", "style"):
            self._in_script_or_style = False
        elif tag_lower in ("p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article"):
            self._text_chunks.append("\n")
        elif tag_lower == "title":
            self.in_title = False
        elif tag_lower == "a":
            self._in_anchor = False
            text = " ".join(self._current_anchor_text).lower()
            if "impressum" in text or "anbieterkennzeichnung" in text:
                self.has_impressum = True

    def handle_data(self, data: str) -> None:
        if data:
            self._detect_pixels_from_string(data)
        if self.in_title:
            self.title_parts.append(data.strip())
        if self._in_anchor:
            self._current_anchor_text.append(data.strip())
        if not self._in_script_or_style:
            stripped = data.strip()
            if stripped:
                self._text_chunks.append(stripped)

    def _detect_pixels_from_string(self, text: str) -> None:
        if not text:
            return
        text_lower = text.lower()

        # Meta Pixel: fbq('init', connect.facebook.net/en_us/fbevents.js, connect.facebook.net, facebook.com/tr
        if (
            "fbq('init'" in text_lower
            or 'fbq("init"' in text_lower
            or "fbq ( 'init'" in text_lower
            or "connect.facebook.net/en_us/fbevents.js" in text_lower
            or "connect.facebook.net" in text_lower
            or "facebook.com/tr" in text_lower
            or bool(re.search(r"fbq\s*\(\s*['\"]init['\"]", text_lower))
        ):
            self.detected_pixels.add("Meta Pixel")

        # Google Analytics 4 (GA4): gtag('config', 'g-, googletagmanager.com/gtag/js?id=g-, google-analytics.com/g/
        if (
            "gtag('config', 'g-" in text_lower
            or 'gtag("config", "g-' in text_lower
            or "googletagmanager.com/gtag/js?id=g-" in text_lower
            or "google-analytics.com/g/" in text_lower
            or bool(re.search(r"gtag\s*\(\s*['\"]config['\"]\s*,\s*['\"]g-", text_lower))
        ):
            self.detected_pixels.add("Google Analytics 4")

        # Google Tag Manager (GTM): googletagmanager.com/gtm.js
        if "googletagmanager.com/gtm.js" in text_lower:
            self.detected_pixels.add("Google Tag Manager")

        # TikTok Pixel: analytics.tiktok.com, ttq.load(
        if (
            "analytics.tiktok.com" in text_lower
            or "ttq.load(" in text_lower
            or bool(re.search(r"ttq\.load\s*\(", text_lower))
        ):
            self.detected_pixels.add("TikTok Pixel")

    def feed(self, data: str) -> None:
        super().feed(data)
        if not self._representative_name:
            self._extract_representative_name()

    def close(self) -> None:
        super().close()
        if not self._representative_name:
            self._extract_representative_name()

    def _detect_cms_from_string(self, text: str) -> None:
        text_lower = text.lower()
        if "wp-content" in text_lower or "wordpress" in text_lower:
            self.cms_hints.add("WordPress")
        elif "wix.com" in text_lower or "wixsite" in text_lower:
            self.cms_hints.add("Wix")
        elif "squarespace" in text_lower:
            self.cms_hints.add("Squarespace")
        elif "shopify" in text_lower:
            self.cms_hints.add("Shopify")
        elif "joomla" in text_lower:
            self.cms_hints.add("Joomla")
        elif "typo3" in text_lower:
            self.cms_hints.add("TYPO3")
        elif "prestashop" in text_lower:
            self.cms_hints.add("PrestaShop")
        elif "drupal" in text_lower:
            self.cms_hints.add("Drupal")
        elif "webflow" in text_lower:
            self.cms_hints.add("Webflow")
