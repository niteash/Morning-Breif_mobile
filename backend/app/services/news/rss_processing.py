"""Schema-compatible normalization, conservative dedupe and category mapping."""
from datetime import datetime, timedelta
from difflib import SequenceMatcher
import hashlib
import ipaddress
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .relevance import calculate_relevance_score
from .safe_rss import normalize_published

TRACKING_KEYS = {"fbclid", "gclid", "dclid", "mc_cid", "mc_eid", "igshid"}
PROMOTIONAL_TEXT = re.compile(
    r"\b(?:sponsored\s+(?:content|post|story)|paid\s+partnership|advertisement|advertorial|promoted\s+post)\b",
    re.IGNORECASE,
)
TOPICS = {
    "technology": (r"\b(?:ai|artificial intelligence|machine learning|software|cybersecurity|technology|chip|semiconductor|smartphone|robotics|openai|nvidia|startup|app)\b",),
    "business": (r"\b(?:business|company|companies|economy|finance|markets?|stocks?|earnings|investment|investors?|funding|revenue|bank|trade|ceo|ipo)\b",),
    "football": (r"\b(?:football|soccer|premier league|champions league|fifa|uefa|goalkeeper|striker|transfer window|matchday)\b",),
    "myanmar": (r"\b(?:myanmar|burma|yangon|mandalay|naypyidaw|rakhine|shan state|kachin|sagaing)\b|မြန်မာ|ရန်ကုန်|မန္တလေး|နေပြည်တော်",),
    "world": (r"\b(?:government|president|parliament|diplomacy|international|conflict|ceasefire|election|treaty|geopolitics|asia|pacific|japan|korea|indonesia|thailand|vietnam|philippines)\b",),
    "crypto": (r"\b(?:crypto(?:currency)?|bitcoin|ethereum|blockchain|stablecoin|defi|web3|altcoin|digital asset|coinbase|binance|solana|xrp)\b",),
    "psychology": (r"\b(?:psychology|psychological|mental health|behavioral science|cognition|psychotherapy|human behavior|anxiety|depression|wellbeing|mindfulness)\b",),
    "horoscope": (r"\b(?:horoscope|astrology|astrological|zodiac|birth chart|sun sign|moon sign|aries|taurus|gemini|cancer|leo|virgo|libra|scorpio|sagittarius|capricorn|aquarius|pisces)\b",),
    "legal": (r"\b(?:court|judge|lawsuit|legal|lawyer|legislation|supreme court|appeal|litigation|bar association)\b",),
}


def canonical_article_url(value: str) -> str | None:
    try:
        parts = urlsplit(value.strip())
        host = (parts.hostname or "").rstrip(".").lower()
        if parts.scheme.lower() not in {"http", "https"} or not host or parts.username or parts.password:
            return None
        try:
            address = ipaddress.ip_address(host)
            if not address.is_global:
                return None
        except ValueError:
            if host == "localhost" or not re.fullmatch(r"(?=.{1,253}$)[a-z0-9.-]+", host):
                return None
        port = parts.port
        if port and port not in (80 if parts.scheme.lower() == "http" else 443,):
            return None
        netloc = host if not port or port in (80, 443) else f"{host}:{port}"
        query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                           if not k.lower().startswith("utm_") and k.lower() not in TRACKING_KEYS], doseq=True)
        path = re.sub(r"/{2,}", "/", parts.path or "/").rstrip("/") or "/"
        return urlunsplit((parts.scheme.lower(), netloc, path, query, ""))
    except (ValueError, UnicodeError):
        return None


def article_url_allowed(value: str, source) -> bool:
    """Accept canonical public article links from this registry source."""
    canonical = canonical_article_url(value)
    if not canonical:
        return False
    if getattr(source, "external_article_urls", False):
        return True
    host = (urlsplit(canonical).hostname or "").lower().rstrip(".")
    domains = getattr(source, "article_domains", ()) or (source.publisher_domain,)
    domains = tuple(domain.lower().removeprefix("www.") for domain in domains)
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def _title_key(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"[\w]+", text, flags=re.UNICODE))


def title_fingerprint(title: str) -> str:
    return hashlib.sha256(_title_key(title).encode("utf-8")).hexdigest()


def title_specific_tokens(title: str) -> set[str]:
    """Return normalized title terms useful for conservative near-duplicate lookup."""
    return {token for token in _title_key(title).split() if len(token) >= 7}


def classify(entry: dict, source, available_categories: set[str]) -> tuple[str | None, str]:
    text = f"{entry.get('title') or ''} {entry.get('description') or ''}"
    lowered = unicodedata.normalize("NFKC", text).casefold()
    scores: dict[str, int] = {}
    for topic in TOPICS:
        pattern = TOPICS[topic][0]
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            target = "world" if topic == "legal" else topic
            if target in available_categories:
                scores[target] = scores.get(target, 0) + (14 if topic == "myanmar" else 10 if topic in {"football", "legal"} else 6)
    for slug in available_categories:
        try:
            score = calculate_relevance_score(slug, entry.get("title") or "", entry.get("description"))
        except (KeyError, TypeError, ValueError):
            score = 0
        if score:
            scores[slug] = scores.get(slug, 0) + min(score, 24)
    default = source.primary_category
    if default in available_categories:
        scores[default] = scores.get(default, 0) + 3
    if not scores:
        selected = default if default in available_categories else ("world" if "world" in available_categories else None)
        return selected, source.geographic_relevance.lower().replace("-", "_")
    # Stable tie-breaking makes dry runs and repeated ingestion deterministic.
    selected = sorted(scores, key=lambda slug: (-scores[slug], slug))[0]
    topic = "legal" if selected == "world" and re.search(TOPICS["legal"][0], lowered, re.I) else source.geographic_relevance.lower().replace("-", "_")
    return selected, topic


def similar_story(left: dict, right: dict, threshold: float = 0.94) -> bool:
    """Very conservative title match, with a narrow publication-time window."""
    left_key, right_key = _title_key(left.get("title") or ""), _title_key(right.get("title") or "")
    if not left_key or not right_key:
        return False
    a, b = normalize_published(left.get("published_at")), normalize_published(right.get("published_at"))
    if a is None or b is None or abs(a - b) > timedelta(hours=12):
        return False
    if left_key == right_key:
        return True
    # Long shared token is additional evidence; avoids merging titles that merely
    # repeat generic words such as "company", "government" or "update".
    shared_specific = bool(title_specific_tokens(left.get("title") or "")
                           & title_specific_tokens(right.get("title") or ""))
    title_similarity = SequenceMatcher(None, left_key, right_key).ratio()
    if shared_specific and title_similarity >= threshold:
        return True
    if shared_specific and title_similarity >= 0.90:
        left_summary = _title_key(left.get("description") or "")
        right_summary = _title_key(right.get("description") or "")
        if left_summary and right_summary:
            return SequenceMatcher(None, left_summary, right_summary).ratio() >= 0.92
    return False


def normalize_entry(entry: dict, source, available_categories: set[str], now: datetime) -> dict | None:
    title = entry.get("title")
    url = canonical_article_url(entry.get("url") or "")
    if (not isinstance(title, str) or not title.strip() or not url
            or not article_url_allowed(url, source)):
        return None
    description = entry.get("description")
    if PROMOTIONAL_TEXT.search(f"{title} {description or ''}"):
        return None
    published = normalize_published(entry.get("published_raw"))
    if published and (published > now + timedelta(minutes=10) or published < now - timedelta(days=7)):
        return None
    category, topic = classify(entry, source, available_categories)
    if not category:
        return None
    # URL-only identity uses the existing unique content_hash index as an atomic
    # cross-source/cross-worker canonical-URL gate. It is stable when headlines vary.
    content_hash = hashlib.sha256(("rss-url:" + url).encode("utf-8")).hexdigest()
    lang = "my" if re.search(r"[\u1000-\u109f]", title + " " + (description or "")) else source.language
    return {
        "source": source.name, "category_slug": category, "topic_group": topic,
        "title": title.strip()[:500], "description": description, "url": url,
        "author": entry.get("author"), "image_url": canonical_article_url(entry.get("image_url") or ""),
        "published_at": published.isoformat() if published else None,
        "publication_date_unknown": published is None, "language": lang,
        "guid": entry.get("guid"), "content_hash": content_hash,
        "title_hash": title_fingerprint(title),
    }
