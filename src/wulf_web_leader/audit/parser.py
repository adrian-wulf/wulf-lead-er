from html.parser import HTMLParser
import re


class SafeWebsiteHTMLParser(HTMLParser):
    """Non-backtracking streaming HTML parser for website metadata and security signals."""

    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title_parts: list[str] = []
        self.meta_description: str | None = None
        self.has_viewport: bool = False
        self.generator: str | None = None
        self.has_impressum: bool = False
        self.extracted_phones: set[str] = set()
        self.extracted_emails: set[str] = set()
        self.cms_hints: set[str] = set()
        self._current_tag = ""
        self._in_anchor = False
        self._current_anchor_text: list[str] = []
        self._current_anchor_href = ""

    @property
    def title(self) -> str | None:
        raw = " ".join(self.title_parts).strip()
        return raw[:200] if raw else None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        self._current_tag = tag_lower
        attr_dict = {k.lower(): (v or "").strip() for k, v in attrs if k}

        if tag_lower == "title":
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
            href = attr_dict.get("href", "")
            self._in_anchor = True
            self._current_anchor_href = href
            self._current_anchor_text = []

            # Check tel:
            if href.lower().startswith("tel:"):
                phone = href[4:].strip()
                if phone:
                    self.extracted_phones.add(phone)

            # Check mailto:
            elif href.lower().startswith("mailto:"):
                email = href[7:].split("?")[0].strip()
                if email:
                    self.extracted_emails.add(email)

            # Check impressum in href
            if "impressum" in href.lower():
                self.has_impressum = True

        elif tag_lower in ("script", "link"):
            src = attr_dict.get("src", "") or attr_dict.get("href", "")
            if src:
                self._detect_cms_from_string(src)

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower == "title":
            self.in_title = False
        elif tag_lower == "a":
            self._in_anchor = False
            text = " ".join(self._current_anchor_text).lower()
            if "impressum" in text or "anbieterkennzeichnung" in text:
                self.has_impressum = True

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data.strip())
        if self._in_anchor:
            self._current_anchor_text.append(data.strip())

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
