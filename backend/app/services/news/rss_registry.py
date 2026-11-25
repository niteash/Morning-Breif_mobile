"""Reviewed feed candidates for the manual staging reader.

This registry deliberately does not change the existing scheduler's feed set or
production ingestion settings. Health counters are process-local and are never
used as proof that a source is operational between runs.
"""
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
import threading
import time


@dataclass(frozen=True)
class FeedSource:
    source_id: str
    name: str
    url: str
    publisher_domain: str
    primary_category: str
    secondary_categories: tuple[str, ...] = ()
    language: str = "en"
    geographic_relevance: str = "global"
    enabled: bool = True
    fetch_interval_minutes: int = 60
    max_entries: int = 100
    candidate_url: str | None = None
    disabled_reason: str | None = None
    article_domains: tuple[str, ...] = ()
    external_article_urls: bool = False


SOURCES = (
    FeedSource("hacker_news", "Hacker News", "https://news.ycombinator.com/rss", "news.ycombinator.com", "technology", external_article_urls=True),
    FeedSource("techcrunch", "TechCrunch", "https://techcrunch.com/feed/", "techcrunch.com", "technology", ("business",)),
    FeedSource("the_verge", "The Verge", "https://www.theverge.com/rss/index.xml", "theverge.com", "technology"),
    FeedSource("wired", "Wired", "https://www.wired.com/feed/rss", "wired.com", "technology"),
    FeedSource("ars_technica", "Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", "feeds.arstechnica.com", "technology", article_domains=("arstechnica.com",)),
    FeedSource("mit_technology_review", "MIT Technology Review", "https://www.technologyreview.com/feed/", "technologyreview.com", "technology"),
    FeedSource("venturebeat", "VentureBeat", "https://venturebeat.com/feed/", "venturebeat.com", "technology", ("business",)),
    FeedSource("engadget", "Engadget", "https://www.engadget.com/rss.xml", "engadget.com", "technology"),
    FeedSource("cnet", "CNET", "https://www.cnet.com/rss/all/", "cnet.com", "technology"),
    FeedSource("nyt_technology", "NYT Technology", "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml", "rss.nytimes.com", "technology", article_domains=("nytimes.com",)),
    FeedSource("dev_community", "DEV Community", "https://dev.to/feed", "dev.to", "technology"),
    FeedSource("the_next_web", "The Next Web", "https://thenextweb.com/latest/feed", "thenextweb.com", "technology",
               enabled=False, candidate_url="https://thenextweb.com/latest/feed",
               disabled_reason="http_404_no_verified_publisher_replacement"),
    FeedSource("slashdot", "Slashdot", "https://rss.slashdot.org/Slashdot/slashdotMain", "rss.slashdot.org", "technology", article_domains=("slashdot.org",),
               fetch_interval_minutes=30, candidate_url="http://rss.slashdot.org/Slashdot/slashdotMain"),
    FeedSource("bbc_football", "BBC Sport Football", "https://feeds.bbci.co.uk/sport/football/rss.xml", "feeds.bbci.co.uk", "football", article_domains=("bbc.co.uk", "bbc.com"), geographic_relevance="United Kingdom"),
    FeedSource("guardian_football", "The Guardian Football", "https://www.theguardian.com/football/rss", "www.theguardian.com", "football", geographic_relevance="United Kingdom"),
    FeedSource("forbes_business", "Forbes Business", "https://www.forbes.com/business/feed/", "www.forbes.com", "business"),
    FeedSource("bbc_business", "BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml", "feeds.bbci.co.uk", "business", article_domains=("bbc.co.uk", "bbc.com"), geographic_relevance="United Kingdom"),
    FeedSource("the_irrawaddy", "The Irrawaddy", "https://www.irrawaddy.com/feed", "www.irrawaddy.com", "myanmar", language="en", geographic_relevance="Myanmar"),
    FeedSource("gnlm", "Global New Light of Myanmar", "https://www.gnlm.com.mm/feed/rss/", "www.gnlm.com.mm", "myanmar", language="en", geographic_relevance="Myanmar"),
    FeedSource("nikkei_asia", "Nikkei Asia", "https://asia.nikkei.com/rss/feed/nar", "asia.nikkei.com", "business", geographic_relevance="Asia-Pacific"),
    FeedSource("coindesk", "CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/", "www.coindesk.com", "crypto"),
    FeedSource("cointelegraph", "Cointelegraph", "https://cointelegraph.com/rss", "cointelegraph.com", "crypto"),
    FeedSource("decrypt", "Decrypt", "https://decrypt.co/feed", "decrypt.co", "crypto"),
    FeedSource("sciencedaily_psychology", "ScienceDaily Psychology", "https://www.sciencedaily.com/rss/mind_brain/psychology.xml", "www.sciencedaily.com", "psychology"),
    FeedSource("apa_news", "APA News", "https://www.apa.org/news/apa/rss.xml", "www.apa.org", "psychology"),
    FeedSource("apa_psycport", "APA PsycPORT", "https://www.apa.org/news/psycport/psycport-rss.xml", "www.apa.org", "psychology", external_article_urls=True),
    FeedSource("ht_horoscope", "Hindustan Times Horoscope", "https://www.hindustantimes.com/feeds/rss/astrology/horoscope/rssfeed.xml", "www.hindustantimes.com", "horoscope", geographic_relevance="India"),
    FeedSource("ht_astrology", "Hindustan Times Astrology", "https://www.hindustantimes.com/feeds/rss/astrology/rssfeed.xml", "www.hindustantimes.com", "horoscope", geographic_relevance="India"),
    FeedSource("e27", "e27", "https://e27.co/index_wp.php/feed", "e27.co", "business", ("technology",),
               geographic_relevance="Asia-Pacific", enabled=False,
               disabled_reason="http_403_publisher_access_unavailable"),
    FeedSource("the_diplomat", "The Diplomat", "https://thediplomat.com/feed", "thediplomat.com", "world", geographic_relevance="Asia-Pacific"),
    FeedSource("aba_journal", "ABA Journal", "https://feeds.feedburner.com/abajournal/dailynews", "feeds.feedburner.com", "world", article_domains=("abajournal.com",), geographic_relevance="United States"),
)

if len(SOURCES) != 31 or len({source.source_id for source in SOURCES}) != 31:
    raise RuntimeError("RSS registry must contain 31 unique source IDs")

HEALTH: dict[str, dict] = {s.source_id: {"last_attempt": None, "last_success": None,
    "last_http_status": None, "failure_category": "not_checked", "parsed": 0,
    "inserted": 0, "duplicates": 0, "rejected": 0,
    "retry_after_epoch": None} for s in SOURCES}
_HEALTH_LOCK = threading.Lock()
HEALTH_PATH = Path(tempfile.gettempdir()) / "nay-thit-staging-rss-health-v1.json"
COOLDOWN_SECONDS = {"http_403": 21600, "http_404": 21600, "http_410": 21600,
                    "rate_limited": 900, "network_error": 300, "malformed_feed": 3600}


def load_health() -> None:
    """Restore only public feed-health metadata between one-shot CLI runs."""
    try:
        saved = json.loads(HEALTH_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return
    with _HEALTH_LOCK:
        for source_id, state in saved.items():
            if source_id in HEALTH and isinstance(state, dict):
                HEALTH[source_id].update({key: state[key] for key in HEALTH[source_id] if key in state})


def save_health() -> None:
    """Atomically persist bounded counters/cooldowns; never stores feed contents or secrets."""
    with _HEALTH_LOCK:
        payload = json.dumps(HEALTH, sort_keys=True)
    fd, temp_path = tempfile.mkstemp(prefix="nay-thit-rss-", dir=str(HEALTH_PATH.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(payload)
        os.replace(temp_path, HEALTH_PATH)
        os.chmod(HEALTH_PATH, 0o600)
    finally:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass


def record_health(source_id: str, *, attempted: datetime, http_status: int | None,
                  failure_category: str | None, parsed: int = 0, inserted: int = 0,
                  duplicates: int = 0, rejected: int = 0,
                  retry_after_seconds: float | None = None) -> None:
    with _HEALTH_LOCK:
        state = HEALTH[source_id]
        state.update(last_attempt=attempted.isoformat(), last_http_status=http_status,
                     failure_category=failure_category or "none", parsed=parsed,
                     inserted=inserted, duplicates=duplicates, rejected=rejected)
        seconds = COOLDOWN_SECONDS.get(f"http_{http_status}") if http_status else None
        if http_status == 429:
            seconds = COOLDOWN_SECONDS["rate_limited"]
        elif http_status is not None and http_status >= 500:
            seconds = 600
        if failure_category == "rate_limited":
            requested_cooldown = min(24 * 60 * 60, max(0, retry_after_seconds or 0))
            seconds = max(COOLDOWN_SECONDS["rate_limited"], requested_cooldown)
        elif failure_category in {"network_error", "dns_failure", "timeout"}:
            seconds = COOLDOWN_SECONDS["network_error"]
        elif failure_category in {"malformed_feed", "empty_or_oversized_feed"}:
            seconds = COOLDOWN_SECONDS["malformed_feed"]
        state["retry_after_epoch"] = time.time() + seconds if failure_category and seconds else None
        if failure_category is None:
            state["last_success"] = attempted.isoformat()
