"""Bounded RSS/Atom reader with per-hop public-address checks and pinned DNS."""
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import gzip
import http.client
import ipaddress
import random
import re
import socket
import ssl
import threading
import time
from urllib.parse import urljoin, urlsplit
import zlib

import certifi
import feedparser
from html.parser import HTMLParser
from html import unescape

from .rss_registry import FeedSource, record_health

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 4
MAX_RETRIES = 2
REQUEST_TIMEOUT_SECONDS = 8
MAX_RETRY_AFTER_SECONDS = 24 * 60 * 60
USER_AGENT = "NayThitNewsReader/1.0 (+https://naythit.app; RSS metadata only)"
APPROVE_HTTP_SLASHDOT = False
APPROVED_HTTP_SOURCE = "slashdot"
_CACHE: dict[str, tuple[bytes, str | None, str | None]] = {}
_CACHE_LOCK = threading.Lock()
_TRACKING = {"fbclid", "gclid", "dclid", "mc_cid", "mc_eid", "igshid"}


class FeedFailure(RuntimeError):
    def __init__(self, category: str, status: int | None = None,
                 retry_after_seconds: float | None = None):
        super().__init__(category)
        self.category, self.status = category, status
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class FetchResult:
    status: int
    body: bytes
    headers: dict[str, str]
    elapsed_ms: int


def _check_url(url: str, source: FeedSource) -> tuple[str, str, int]:
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").rstrip(".").lower()
        port = parsed.port
    except ValueError:
        raise FeedFailure("invalid_url") from None
    try:
        literal = ipaddress.ip_address(host)
        if not literal.is_global:
            raise FeedFailure("non_public_address")
    except ValueError:
        # A ValueError here means the hostname is DNS-resolved and checked below
        # immediately before a pinned connection is opened.
        pass
    allowed_http = (APPROVE_HTTP_SLASHDOT and source.source_id == APPROVED_HTTP_SOURCE
                    and source.url == "http://rss.slashdot.org/Slashdot/slashdotMain" and source.enabled)
    if (parsed.scheme != "https" and not (parsed.scheme == "http" and allowed_http)) or not host or parsed.username or parsed.password:
        raise FeedFailure("insecure_or_invalid_url")
    if port not in (None, 80 if parsed.scheme == "http" else 443):
        raise FeedFailure("nonstandard_port")
    if parsed.fragment:
        parsed = parsed._replace(fragment="")
    return host, parsed.path or "/", (80 if parsed.scheme == "http" else 443)


def _resolve_public(host: str, port: int) -> str:
    try:
        literal = ipaddress.ip_address(host)
        addresses = [literal]
    except ValueError:
        try:
            addresses = [ipaddress.ip_address(item[4][0].split("%", 1)[0])
                         for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)]
        except (OSError, ValueError):
            raise FeedFailure("dns_failure") from None
    if not addresses or any(not addr.is_global for addr in addresses):
        raise FeedFailure("non_public_address")
    return str(addresses[0])


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, address: str, timeout: int):
        super().__init__(host, port, timeout=timeout)
        self._address = address

    def connect(self):
        self.sock = socket.create_connection((self._address, self.port), self.timeout)
        if self._tunnel_host:
            self._tunnel()


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, port: int, address: str, timeout: int):
        super().__init__(host, port, timeout=timeout, context=ssl.create_default_context(cafile=certifi.where()))
        self._address = address

    def connect(self):
        sock = socket.create_connection((self._address, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def _read_limited(response) -> bytes:
    length = response.getheader("Content-Length")
    if length:
        try:
            if int(length) > MAX_RESPONSE_BYTES:
                raise FeedFailure("feed_too_large")
        except ValueError:
            raise FeedFailure("invalid_content_length") from None
    raw = bytearray()
    while len(raw) <= MAX_RESPONSE_BYTES:
        block = response.read(min(65536, MAX_RESPONSE_BYTES + 1 - len(raw)))
        if not block:
            break
        raw.extend(block)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise FeedFailure("feed_too_large")
    encoding = (response.getheader("Content-Encoding") or "").lower()
    if encoding in {"", "identity"}:
        return bytes(raw)
    if encoding == "gzip":
        inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
        try:
            expanded = inflater.decompress(raw, MAX_RESPONSE_BYTES + 1)
            if len(expanded) > MAX_RESPONSE_BYTES or inflater.unconsumed_tail:
                raise FeedFailure("feed_too_large")
            expanded += inflater.flush(MAX_RESPONSE_BYTES + 1 - len(expanded))
        except zlib.error:
            raise FeedFailure("invalid_compression") from None
        if len(expanded) > MAX_RESPONSE_BYTES:
            raise FeedFailure("feed_too_large")
        return expanded
    raise FeedFailure("unsupported_content_encoding")


def _retry_after(headers: dict[str, str]) -> float | None:
    value = headers.get("retry-after")
    if not value:
        return None
    try:
        return min(MAX_RETRY_AFTER_SECONDS, max(0.0, float(value)))
    except ValueError:
        try:
            dt = parsedate_to_datetime(value)
            if dt.tzinfo is None:
                return None
            return min(MAX_RETRY_AFTER_SECONDS, max(0.0, (dt - datetime.now(timezone.utc)).total_seconds()))
        except (TypeError, ValueError, OverflowError):
            return None


def _fetch_once(url: str, source: FeedSource) -> FetchResult:
    start = time.monotonic()
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        host, path, port = _check_url(current, source)
        address = _resolve_public(host, port)
        try:
            if not ipaddress.ip_address(address.split("%", 1)[0]).is_global:
                raise FeedFailure("non_public_address")
        except ValueError:
            raise FeedFailure("dns_failure") from None
        parsed = urlsplit(current)
        conn_cls = _PinnedHTTPSConnection if parsed.scheme == "https" else _PinnedHTTPConnection
        conn = conn_cls(host, port, address, REQUEST_TIMEOUT_SECONDS)
        headers = {"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.1",
                   "Accept-Encoding": "gzip", "Connection": "close"}
        with _CACHE_LOCK:
            cached = _CACHE.get(source.source_id)
        if current == source.url and cached:
            if cached[1]: headers["If-None-Match"] = cached[1]
            if cached[2]: headers["If-Modified-Since"] = cached[2]
        try:
            conn.request("GET", path + (("?" + parsed.query) if parsed.query else ""), headers=headers)
            response = conn.getresponse()
            response_headers = {key.lower(): value for key, value in response.getheaders()}
            if response.status in (301, 302, 303, 307, 308):
                location = response_headers.get("location")
                response.read(1024)
                conn.close()
                if not location:
                    raise FeedFailure("redirect_without_location", response.status)
                current = urljoin(current, location)
                # Revalidate scheme, credentials, DNS and address on every hop.
                _check_url(current, source)
                continue
            body = _read_limited(response) if response.status != 304 else b""
            result = FetchResult(response.status, body, response_headers, round((time.monotonic()-start)*1000))
            conn.close()
            return result
        except FeedFailure:
            conn.close()
            raise
        except (OSError, ssl.SSLError, http.client.HTTPException, TimeoutError):
            conn.close()
            raise
    raise FeedFailure("too_many_redirects")


def fetch_feed(source: FeedSource) -> FetchResult:
    """Fetch a configured source with validators, bounded retries and safe redirects."""
    started = datetime.now(timezone.utc)
    last: FeedFailure | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = _fetch_once(source.url, source)
            if result.status == 304:
                with _CACHE_LOCK:
                    cached = _CACHE.get(source.source_id)
                if not cached:
                    raise FeedFailure("not_modified_without_cache", 304)
                return FetchResult(304, cached[0], result.headers, result.elapsed_ms)
            if result.status == 429:
                # Do not hammer a rate-limiting publisher with in-run retries.
                # Persist Retry-After as a cooldown for the next operator run.
                raise FeedFailure("rate_limited", 429, _retry_after(result.headers))
            if result.status >= 500:
                if attempt < MAX_RETRIES:
                    time.sleep(min(4.0, 0.5 * (2 ** attempt) + random.uniform(0, 0.25)))
                    continue
                raise FeedFailure("upstream_server_error", result.status)
            if result.status < 200 or result.status >= 300:
                category = f"http_{result.status}" if 400 <= result.status < 500 else "http_error"
                raise FeedFailure(category, result.status)
            with _CACHE_LOCK:
                _CACHE[source.source_id] = (result.body, result.headers.get("etag"), result.headers.get("last-modified"))
            return result
        except FeedFailure as error:
            last = error
            if error.category != "upstream_server_error":
                break
            if attempt < MAX_RETRIES:
                time.sleep(min(4.0, 0.5 * (2 ** attempt) + random.uniform(0, 0.25)))
        except (OSError, ssl.SSLError, http.client.HTTPException, TimeoutError):
            last = FeedFailure("network_error")
            if attempt < MAX_RETRIES:
                time.sleep(min(4.0, 0.5 * (2 ** attempt) + random.uniform(0, 0.25)))
    if last is None:
                raise FeedFailure("http_error", result.status)
    raise last


class _TextOnly(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._blocked = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "iframe", "object", "svg"}:
            self._blocked += 1

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "iframe", "object", "svg"} and self._blocked:
            self._blocked -= 1

    def handle_data(self, data):
        if not self._blocked:
            self.parts.append(data)


class _FirstImage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.url = None

    def handle_starttag(self, tag, attrs):
        if self.url is not None or tag.casefold() != 'img':
            return
        values = {key.casefold(): value for key, value in attrs if value}
        self.url = values.get('src') or values.get('data-src')


def _html_image(value: object) -> str | None:
    if not value:
        return None
    parser = _FirstImage()
    try:
        parser.feed(unescape(str(value)))
        parser.close()
    except Exception:
        return None
    return parser.url


def extract_feed_image(entry) -> str | None:
    media = list(entry.get('media_thumbnail') or []) + list(entry.get('media_content') or [])
    enclosures = list(entry.get('enclosures') or [])
    links = [item for item in (entry.get('links') or []) if item.get('rel') == 'enclosure']
    image = entry.get('image') or {}
    content_image = next((
        _html_image(item.get('value')) for item in (entry.get('content') or [])
        if isinstance(item, dict) and _html_image(item.get('value'))
    ), None)
    candidates = [
        *(item.get('url') for item in media
          if item.get('url') and (not item.get('type') or str(item.get('type')).startswith('image/'))),
        *(item.get('href') or item.get('url') for item in enclosures + links
          if (item.get('href') or item.get('url')) and str(item.get('type') or '').startswith('image/')),
        image.get('href') or image.get('url') if isinstance(image, dict) else None,
        _html_image(entry.get('summary') or entry.get('description')),
        content_image,
    ]
    return next((str(value).strip() for value in candidates if value and str(value).strip()), None)


def clean_feed_text(value: object, limit: int) -> str | None:
    if value is None:
        return None
    parser = _TextOnly()
    try:
        parser.feed(unescape(str(value)))
        parser.close()
    except Exception:
        return None
    text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
    return text[:limit] or None


def parse_feed(body: bytes, source: FeedSource) -> list[dict]:
    if not body or len(body) > MAX_RESPONSE_BYTES:
        raise FeedFailure("empty_or_oversized_feed")
    parsed = feedparser.parse(body)
    if parsed.bozo:
        raise FeedFailure("malformed_feed")
    entries = []
    for entry in parsed.entries[:source.max_entries]:
        link = str(entry.get("link") or "").strip()
        published = entry.get("published") or entry.get("updated")
        if not published:
            published = entry.get("published_parsed") or entry.get("updated_parsed")
        entries.append({
            "title": clean_feed_text(entry.get("title"), 500),
            "description": clean_feed_text(entry.get("summary") or entry.get("description"), 1400),
            "url": link,
            "guid": str(entry.get("id") or entry.get("guid") or "")[:1000] or None,
            "guid_is_link": bool(entry.get("guidislink")),
            "published_raw": published,
            "author": clean_feed_text(entry.get("author"), 160),
            "image_url": extract_feed_image(entry),
        })
    return entries


def normalize_published(value: object) -> datetime | None:
    if value is None:
        return None
    try:
        if isinstance(value, (tuple, list)):
            from datetime import timedelta
            from calendar import timegm
            return datetime.fromtimestamp(timegm(value), tz=timezone.utc)
        if isinstance(value, datetime):
            dt = value
        else:
            raw = str(value).strip().replace("Z", "+00:00")
            try:
                dt = datetime.fromisoformat(raw)
            except ValueError:
                dt = parsedate_to_datetime(raw)
        return dt.astimezone(timezone.utc) if dt.tzinfo and dt.utcoffset() is not None else None
    except (TypeError, ValueError, OverflowError, IndexError):
        return None
