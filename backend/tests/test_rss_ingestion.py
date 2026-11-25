"""Deterministic RSS ingestion and staging boundary tests; all networks are mocked."""
import asyncio
from datetime import datetime, timedelta, timezone
import gzip
import json
from types import SimpleNamespace
from unittest.mock import Mock

import feedparser
import pytest

from app.services.news import manual_ingestion, rss, rss_processing, rss_registry, safe_rss
from app.services.news.rss_registry import SOURCES
from app.services.news.safe_rss import FetchResult

NOW = datetime.now(timezone.utc).replace(microsecond=0)
TECH = next(source for source in SOURCES if source.source_id == "techcrunch")


@pytest.fixture(autouse=True)
def isolate_rss_runtime_state(tmp_path, monkeypatch):
    """Keep persisted feed cooldowns and caches from making tests order-dependent."""
    monkeypatch.setattr(rss_registry, "HEALTH_PATH", tmp_path / "rss-health.json")
    for source in SOURCES:
        monkeypatch.setitem(
            rss_registry.HEALTH,
            source.source_id,
            {
                "last_attempt": None,
                "last_success": None,
                "last_http_status": None,
                "failure_category": "not_checked",
                "parsed": 0,
                "inserted": 0,
                "duplicates": 0,
                "rejected": 0,
                "retry_after_epoch": None,
            },
        )
    monkeypatch.setattr(safe_rss, "_CACHE", {})


@pytest.mark.parametrize("body", [
    b'''<?xml version="1.0"?><rss version="2.0"><channel><title>Test</title><item><title>OpenAI releases a new machine learning tool</title><link>https://example.com/story/?utm_source=rss</link><guid>story-1</guid><pubDate>Sun, 15 Nov 2026 10:00:00 GMT</pubDate><description><![CDATA[<p>AI <b>news</b></p><script>alert(1)</script>]]></description><author>A. Writer</author></item></channel></rss>''',
    b'''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Atom</title><entry><title>OpenAI releases a new machine learning tool</title><link rel="alternate" href="https://example.com/story/"/><id>tag:example.com,2026:story-1</id><updated>2026-11-15T10:00:00+00:00</updated><summary>AI news</summary></entry></feed>''',
])
def test_parses_rss_and_atom_without_executing_or_retaining_active_html(body):
    entries = safe_rss.parse_feed(body, TECH)
    assert entries[0]["title"] == "OpenAI releases a new machine learning tool"
    assert entries[0]["published_raw"]
    assert "alert" not in (entries[0]["description"] or "")


@pytest.mark.parametrize(('body', 'expected'), [
    (b'''<rss xmlns:media="http://search.yahoo.com/mrss/"><channel><item><title>Story</title><link>https://example.org/story</link><media:thumbnail url="https://cdn.example.org/media.jpg"/></item></channel></rss>''', 'https://cdn.example.org/media.jpg'),
    (b'''<rss><channel><item><title>Story</title><link>https://example.org/story</link><enclosure url="https://cdn.example.org/enclosure.jpg" type="image/jpeg"/></item></channel></rss>''', 'https://cdn.example.org/enclosure.jpg'),
    (b'''<rss><channel><item><title>Story</title><link>https://example.org/story</link><description><![CDATA[<p>Summary</p><img src="https://cdn.example.org/summary.jpg">]]></description></item></channel></rss>''', 'https://cdn.example.org/summary.jpg'),
])
def test_feed_images_are_captured_from_reviewed_rss_metadata(body, expected):
    assert safe_rss.parse_feed(body, TECH)[0]['image_url'] == expected


def test_legacy_ingestion_preserves_feed_images(monkeypatch):
    body = b'''<rss xmlns:media="http://search.yahoo.com/mrss/"><channel><item><title>Story</title><link>https://example.org/story</link><pubDate>Sun, 15 Nov 2026 10:00:00 GMT</pubDate><media:thumbnail url="https://cdn.example.org/story.jpg"/></item></channel></rss>'''
    monkeypatch.setattr(rss, "_fetch_feed_bytes", lambda _url: body)
    assert rss.fetch_rss_feed("https://example.org/feed")[0]["image_url"] == "https://cdn.example.org/story.jpg"


def test_gzip_feed_body_is_parsed_after_bounded_decompression():
    body = b"<rss version='2.0'><channel><title>News</title><item><title>Title</title><link>https://example.org/a</link></item></channel></rss>"
    class Response:
        def __init__(self): self.body = gzip.compress(body)
        def getheader(self, key):
            return {"Content-Encoding": "gzip", "Content-Length": str(len(self.body))}.get(key)
        def read(self, size):
            chunk, self.body = self.body[:size], self.body[size:]
            return chunk
    assert safe_rss.parse_feed(safe_rss._read_limited(Response()), TECH)[0]["title"] == "Title"


def test_invalid_and_empty_xml_are_rejected():
    with pytest.raises(safe_rss.FeedFailure, match="malformed_feed"):
        safe_rss.parse_feed(b"<rss><item>", TECH)
    assert feedparser.parse(b"<rss version='2.0'><channel></channel></rss>").entries == []
    assert safe_rss.parse_feed(b"<rss version='2.0'><channel></channel></rss>", TECH) == []


def test_oversized_gzip_and_compressed_bomb_are_bounded():
    class Response:
        def __init__(self, body, encoding="identity"):
            self.body = body
            self.encoding = encoding
            self.headers = {"Content-Length": str(len(body))}
        def getheader(self, key):
            return self.encoding if key == "Content-Encoding" else self.headers.get(key)
        def read(self, size):
            chunk, self.body = self.body[:size], self.body[size:]
            return chunk
    payload = b"x" * (safe_rss.MAX_RESPONSE_BYTES + 50)
    with pytest.raises(safe_rss.FeedFailure, match="feed_too_large"):
        safe_rss._read_limited(Response(gzip.compress(payload), "gzip"))
    with pytest.raises(safe_rss.FeedFailure, match="feed_too_large"):
        safe_rss._read_limited(Response(b"a" * (safe_rss.MAX_RESPONSE_BYTES + 1)))


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/rss", "http://169.254.169.254/latest/meta-data", "https://[::1]/feed",
    "https://user:password@example.com/feed", "file:///etc/passwd", "https://example.com:8443/feed",
])
def test_rejects_unsafe_or_ambiguous_feed_and_redirect_urls(url):
    with pytest.raises(safe_rss.FeedFailure):
        safe_rss._check_url(url, TECH)


def test_slashdot_uses_verified_https_and_preserves_http_candidate_for_audit(monkeypatch):
    source = next(item for item in SOURCES if item.source_id == "slashdot")
    assert source.url == "https://rss.slashdot.org/Slashdot/slashdotMain"
    assert source.candidate_url == "http://rss.slashdot.org/Slashdot/slashdotMain"
    assert source.enabled is True and source.fetch_interval_minutes >= 30
    assert safe_rss._check_url(source.url, source)[0] == "rss.slashdot.org"
    with pytest.raises(safe_rss.FeedFailure, match="insecure_or_invalid_url"):
        safe_rss._check_url(source.candidate_url, source)


def test_redirects_get_public_address_validation_on_every_hop(monkeypatch):
    calls = []
    responses = iter([
        _HttpResponse(302, {"location": "https://example.org/feed"}),
        _HttpResponse(200),
    ])
    monkeypatch.setattr(safe_rss, "_resolve_public", lambda host, port: calls.append((host, port)) or "93.184.216.34")
    monkeypatch.setattr(safe_rss, "_PinnedHTTPSConnection", lambda *args, **kwargs: _Connection(next(responses)))
    safe_rss._fetch_once(TECH.url, TECH)
    assert calls[0][0] == "techcrunch.com"


def test_redirect_to_private_dns_address_is_blocked(monkeypatch):
    monkeypatch.setattr(safe_rss, "_resolve_public", lambda host, _port: "10.0.0.2")
    with pytest.raises(safe_rss.FeedFailure, match="non_public_address"):
        safe_rss._fetch_once(TECH.url, TECH)


class _Connection:
    def __init__(self, response): self.response = response
    def request(self, *args, **kwargs): pass
    def getresponse(self): return self.response
    def close(self): pass


class _HttpResponse:
    def __init__(self, status, headers=None): self.status, self.headers = status, headers or {}
    def getheaders(self): return list(self.headers.items())
    def getheader(self, key): return self.headers.get(key)
    def read(self, _size=-1): return b""


def test_http_304_reuses_validator_cache_and_429_uses_bounded_retry_after_cooldown(monkeypatch):
    safe_rss._CACHE[TECH.source_id] = (b"cached-feed", "etag-1", None)
    monkeypatch.setattr(safe_rss, "_fetch_once", lambda *_: safe_rss.FetchResult(304, b"", {}, 4))
    assert safe_rss.fetch_feed(TECH).body == b"cached-feed"
    safe_rss._CACHE.pop(TECH.source_id, None)
    calls = []
    monkeypatch.setattr(safe_rss, "_fetch_once", lambda *_: calls.append(1) or safe_rss.FetchResult(429, b"", {"retry-after": "12"}, 1))
    sleeps = []
    monkeypatch.setattr(safe_rss.time, "sleep", sleeps.append)
    with pytest.raises(safe_rss.FeedFailure) as failure:
        safe_rss.fetch_feed(TECH)
    assert (failure.value.category, failure.value.retry_after_seconds) == ("rate_limited", 12)
    assert len(calls) == 1 and sleeps == []


def test_403_is_not_retried_and_errors_are_classified(monkeypatch):
    calls = []
    def denied(*_args):
        calls.append(1)
        return safe_rss.FetchResult(403, b"", {}, 1)
    monkeypatch.setattr(safe_rss, "_fetch_once", denied)
    with pytest.raises(safe_rss.FeedFailure) as failure:
        safe_rss.fetch_feed(TECH)
    assert (failure.value.category, failure.value.status) == ("http_403", 403)
    assert len(calls) == 1


def test_retry_and_network_failures_are_bounded_and_redacted(monkeypatch):
    calls, sleeps = [], []
    monkeypatch.setattr(safe_rss, "_fetch_once", lambda *_: _raise_timeout(calls))
    monkeypatch.setattr(safe_rss.time, "sleep", sleeps.append)
    with pytest.raises(safe_rss.FeedFailure, match="network_error"):
        safe_rss.fetch_feed(TECH)
    assert len(calls) == safe_rss.MAX_RETRIES + 1
    assert len(sleeps) == safe_rss.MAX_RETRIES


def _raise_timeout(calls):
    calls.append(1)
    raise TimeoutError("do-not-print-this-host-or-token")


def test_canonical_urls_preserve_distinct_story_queries_and_remove_trackers():
    a = rss_processing.canonical_article_url("HTTPS://Example.com/news/?utm_source=rss&id=1#top")
    b = rss_processing.canonical_article_url("https://example.com/news?id=1")
    c = rss_processing.canonical_article_url("https://example.com/news?id=2")
    assert a == b and c != b


def test_missing_and_timezone_naive_publication_dates_are_not_fabricated():
    assert safe_rss.normalize_published(None) is None
    assert safe_rss.normalize_published("2026-11-15T10:00:00") is None
    assert safe_rss.normalize_published("2026-11-15T15:30:00+05:30") == datetime(2026, 11, 15, 10, tzinfo=timezone.utc)


def _entry(title, url="https://techcrunch.com/a", date=NOW.isoformat()):
    return {"title": title, "url": url, "guid": None, "published_raw": date, "description": None,
            "author": None, "image_url": None}


def test_burmese_unicode_normalization_dedup_and_category_classification():
    item = rss_processing.normalize_entry(_entry("မြန်မာသတင်း ရန်ကုန်အကြောင်း"), TECH, {"myanmar", "technology", "business", "football", "world"}, NOW)
    assert item["category_slug"] == "myanmar"
    assert item["language"] == "my"
    assert item["url"] == "https://techcrunch.com/a"
    article = rss_processing.normalize_entry(_entry("OpenAI releases a new machine learning tool"), TECH,
        {"myanmar", "technology", "business", "football", "world"}, NOW)
    assert article["category_slug"] == "technology"
    assert article["published_at"].endswith("+00:00")
    assert rss_processing.similar_story(article, dict(article, title="OpenAI releases a new machine learning tools"))
    assert not rss_processing.similar_story(article, dict(article, title="OpenAI releases a new machine learning tool", published_at=(NOW-timedelta(days=2)).isoformat()))


@pytest.mark.parametrize("title,category", [
    ("Myanmar business bank announces new Yangon investment", "myanmar"),
    ("Premier League football club confirms striker transfer", "football"),
    ("Central bank adjusts interest rates after inflation", "business"),
    ("Software company releases cybersecurity update", "technology"),
])
def test_classifier_uses_content_keywords_and_available_categories(title, category):
    article = rss_processing.normalize_entry(_entry(title), TECH, {"myanmar", "technology", "business", "football", "world"}, NOW)
    assert article["category_slug"] == category


def test_legal_topics_map_to_existing_world_category_and_undated_is_explicit():
    source = next(item for item in SOURCES if item.source_id == "aba_journal")
    story = _entry("Supreme court hears major legislation appeal", "https://abajournal.com/story", None)
    normalized = rss_processing.normalize_entry(story, source, {"world", "technology", "business", "football", "myanmar"}, NOW)
    assert normalized["category_slug"] == "world"
    assert normalized["topic_group"] == "legal"
    assert normalized["published_at"] is None and normalized["publication_date_unknown"] is True


def test_source_registry_contains_all_31_exact_candidates():
    assert len(SOURCES) == len({s.source_id for s in SOURCES}) == 31
    assert all(s.url.startswith(("http://", "https://")) and s.publisher_domain for s in SOURCES)
    assert all(s.fetch_interval_minutes >= 5 and s.max_entries <= 100 for s in SOURCES)
    from app.services.news.sources import NEWS_SOURCES
    assert {s.candidate_url or s.url for s in SOURCES} == {s["url"] for s in NEWS_SOURCES}
    assert next(s for s in SOURCES if s.source_id == "the_next_web").enabled is False
    assert next(s for s in SOURCES if s.source_id == "e27").enabled is False


@pytest.mark.parametrize(("title", "category"), [
    ("Bitcoin ETF demand lifts the cryptocurrency market", "crypto"),
    ("Psychology study links mindfulness with emotional wellbeing", "psychology"),
    ("Daily horoscope for Aries, Taurus and Gemini", "horoscope"),
])
def test_new_categories_are_classified_without_leaking_into_existing_topics(title, category):
    source = next(item for item in SOURCES if item.primary_category == category)
    available = {"myanmar", "technology", "business", "football", "world", "crypto", "psychology", "horoscope"}
    normalized = rss_processing.normalize_entry(
        _entry(title, f"https://{source.publisher_domain}/story"),
        source,
        available,
        NOW,
    )
    assert normalized and normalized["category_slug"] == category


def test_source_health_persistence_stores_only_counters_and_is_owner_only(tmp_path, monkeypatch):
    import stat
    from app.services.news import rss_registry
    path = tmp_path / "rss-health.json"
    monkeypatch.setattr(rss_registry, "HEALTH_PATH", path)
    # This test deliberately exercises persistent, process-global feed health.
    # Isolate the entry so its active 429 cooldown cannot leak into later dry-run
    # tests and make their mocked feed fetches order-dependent.
    monkeypatch.setitem(
        rss_registry.HEALTH,
        TECH.source_id,
        dict(rss_registry.HEALTH[TECH.source_id]),
    )
    rss_registry.record_health(TECH.source_id, attempted=NOW, http_status=429,
                               failure_category="rate_limited", parsed=5, duplicates=2, rejected=1)
    rss_registry.save_health()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert b"access_token" not in path.read_bytes()
    rss_registry.HEALTH[TECH.source_id]["parsed"] = 0
    rss_registry.load_health()
    assert rss_registry.HEALTH[TECH.source_id]["parsed"] == 5
    assert rss_registry.HEALTH[TECH.source_id]["retry_after_epoch"] > NOW.timestamp()


def test_retry_after_is_recorded_as_a_bounded_source_cooldown(monkeypatch):
    import time
    from app.services.news import rss_registry
    source = TECH.source_id
    monkeypatch.setitem(rss_registry.HEALTH, source, dict(rss_registry.HEALTH[source]))
    before = time.time()
    rss_registry.record_health(source, attempted=NOW, http_status=429,
                               failure_category="rate_limited", retry_after_seconds=10**9)
    cooldown = rss_registry.HEALTH[source]["retry_after_epoch"] - before
    assert rss_registry.COOLDOWN_SECONDS["rate_limited"] <= cooldown <= 24 * 60 * 60 + 1


def test_explicit_failed_source_retry_never_bypasses_an_active_rate_limit(monkeypatch):
    import time
    from app.services.news import rss_registry
    source_id = TECH.source_id
    monkeypatch.setattr(manual_ingestion, "SOURCES", (TECH,))
    monkeypatch.setattr(manual_ingestion, "load_health", lambda: None)
    monkeypatch.setattr(manual_ingestion, "save_health", lambda: None)
    monkeypatch.setitem(rss_registry.HEALTH, source_id, {
        **rss_registry.HEALTH[source_id], "last_http_status":429,
        "failure_category":"rate_limited", "retry_after_epoch":time.time()+3600})
    monkeypatch.setattr(manual_ingestion, "_load_reference_data", lambda _client: (
        {"technology":"tech", "business":"biz", "football":"foot", "myanmar":"mm", "world":"world"}, []))
    fetch = Mock(side_effect=AssertionError("active Retry-After must not be bypassed"))
    monkeypatch.setattr(manual_ingestion, "fetch_feed", fetch)
    result = asyncio.run(manual_ingestion.run_manual_ingestion(write=False, retry_failed_sources=True))
    assert result["sources"][0]["failure_category"] == "source_cooldown"
    assert result["sources"][0]["http_status"] == 429
    fetch.assert_not_called()


def test_manual_dry_run_requires_authenticated_rls_reads_before_database_or_feed_access(monkeypatch):
    monkeypatch.delenv("RSS_IMPORT_ACCESS_TOKEN", raising=False)
    reference_read = Mock(side_effect=AssertionError("must not query without authenticated RLS"))
    feed_read = Mock(side_effect=AssertionError("must not fetch without authenticated RLS preflight"))
    monkeypatch.setattr(manual_ingestion, "_load_reference_data", reference_read)
    monkeypatch.setattr(manual_ingestion, "fetch_feed", feed_read)
    with pytest.raises(manual_ingestion.IngestionDiagnosticError,
                       match="authenticated_operator_access_token_missing"):
        asyncio.run(manual_ingestion.run_manual_ingestion(write=False))
    reference_read.assert_not_called()
    feed_read.assert_not_called()


def test_cli_rejects_non_staging_environment_before_invoking_pipeline(monkeypatch, capsys):
    from app.services.news import cli
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("SUPABASE_URL", "https://kobsywjfynjvhcarbqxo.supabase.co")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    invoked = Mock(side_effect=AssertionError("rejected target must not run"))
    monkeypatch.setattr(cli, "run_manual_ingestion", invoked)
    assert cli.main(["--environment", "staging", "--dry-run"]) == 1
    invoked.assert_not_called()
    error = json.loads(capsys.readouterr().err)
    assert error["stage"] == "environment_guard"
    assert error["error_category"] == "wrong_staging_target"
    assert error["database_write_attempted"] is False
    assert "service-role" not in json.dumps(error)


def test_cli_requires_workers_and_public_trial_claims_disabled(monkeypatch):
    from app.services.news import cli
    for name, value in {"APP_ENV":"staging", "SUPABASE_URL":cli.STAGING_URL, "GEMINI_API_KEY":"",
        "AZURE_SPEECH_KEY":"", "FIREBASE_SERVICE_ACCOUNT_PATH":"", "INGESTION_OPERATOR_IDS":"",
        "SCHEDULER_ENABLED":"false", "NEWS_INGESTION_ENABLED":"false", "PUSH_DELIVERY_ENABLED":"false",
        "ACCOUNT_DELETION_ENABLED":"false", "ACCOUNT_DELETION_WORKER_ENABLED":"false",
        "TRIAL_STAGING_ACCOUNT_ENABLED":"true"}.items(): monkeypatch.setenv(name,value)
    assert cli.main(["--environment","staging","--dry-run"]) == 1


def test_cli_write_cannot_start_without_a_reviewed_report_and_run_id(monkeypatch, capsys):
    from app.services.news import cli
    values = {"APP_ENV":"staging", "SUPABASE_URL":cli.STAGING_URL,
        "GEMINI_API_KEY":"", "AZURE_SPEECH_KEY":"", "FIREBASE_SERVICE_ACCOUNT_PATH":"",
        "INGESTION_OPERATOR_IDS":"", "SCHEDULER_ENABLED":"false", "NEWS_INGESTION_ENABLED":"false",
        "PUSH_DELIVERY_ENABLED":"false", "ACCOUNT_DELETION_ENABLED":"false",
        "ACCOUNT_DELETION_WORKER_ENABLED":"false", "TRIAL_STAGING_ACCOUNT_ENABLED":"false",
        "MANUAL_INGESTION_WRITE":"true"}
    for name, value in values.items(): monkeypatch.setenv(name, value)
    invoked = Mock(side_effect=AssertionError("write must not run without reviewed report"))
    monkeypatch.setattr(cli, "run_manual_ingestion", invoked)
    assert cli.main(["--environment", "staging", "--write", "--confirm-staging-project", cli.STAGING_REF]) == 1
    invoked.assert_not_called()
    error = json.loads(capsys.readouterr().err)
    assert error["error_category"] == "approved_report_required"
    assert error["database_write_attempted"] is False


def test_cli_reports_reference_database_connection_failure_without_exception_details(monkeypatch, capsys):
    from app.services.news import cli
    from app.services.news import manual_ingestion as ingestion
    values = {"APP_ENV":"staging", "SUPABASE_URL":cli.STAGING_URL,
        "GEMINI_API_KEY":"", "AZURE_SPEECH_KEY":"", "FIREBASE_SERVICE_ACCOUNT_PATH":"",
        "INGESTION_OPERATOR_IDS":"", "SCHEDULER_ENABLED":"false", "NEWS_INGESTION_ENABLED":"false",
        "PUSH_DELIVERY_ENABLED":"false", "ACCOUNT_DELETION_ENABLED":"false",
        "ACCOUNT_DELETION_WORKER_ENABLED":"false", "TRIAL_STAGING_ACCOUNT_ENABLED":"false"}
    for name, value in values.items(): monkeypatch.setenv(name, value)
    monkeypatch.setattr(ingestion, "load_health", lambda: None)
    monkeypatch.setattr(ingestion, "_load_reference_data",
                        Mock(side_effect=RuntimeError("dsn=password=never-print-this")))
    monkeypatch.setenv("RSS_IMPORT_ACCESS_TOKEN", "fixture-authenticated-operator-jwt")
    assert cli.main(["--environment", "staging", "--dry-run"]) == 1
    error = json.loads(capsys.readouterr().err)
    assert error["stage"] == "reference_data_read"
    assert error["error_category"] == "database_read_failure"
    assert error["database_write_attempted"] is False
    assert error["rows_committed"] == 0
    assert error["error_type"] == "RuntimeError"
    assert "never-print-this" not in json.dumps(error)


def test_dry_run_proposes_articles_but_never_calls_database_writer(monkeypatch):
    monkeypatch.setattr(manual_ingestion, "_load_reference_data", lambda _client: ({"technology": "cat-tech", "business": "cat-biz", "football": "cat-foot", "myanmar": "cat-mm", "world": "cat-world"}, []))
    sources = (TECH,)
    monkeypatch.setattr(manual_ingestion, "SOURCES", sources)
    body_entry = _entry("OpenAI releases a new machine learning tool", "https://techcrunch.com/a")
    def fake_fetch(source):
        from app.services.news.safe_rss import FetchResult
        return FetchResult(200, b"fixture", {}, 1)
    monkeypatch.setattr(manual_ingestion, "fetch_feed", fake_fetch)
    monkeypatch.setattr(manual_ingestion, "parse_feed", lambda *_: [body_entry])
    writer = Mock(side_effect=AssertionError("dry-run must never write"))
    monkeypatch.setattr(manual_ingestion, "create_supabase_client",
                        lambda _token: SimpleNamespace(table=writer))
    summary = asyncio.run(manual_ingestion.run_manual_ingestion(limit_per_feed=2, max_inserts=3, write=False, retry_failed_sources=True))
    assert summary["dry_run"] is True and summary["totals"]["inserted"] == 0
    assert len(summary["proposed"]) == 1
    writer.assert_not_called()


def test_manual_dry_run_rejects_stories_older_than_requested_window_and_reports_by_category(monkeypatch):
    categories = {"technology":"cat-tech", "business":"cat-biz", "football":"cat-foot",
                  "myanmar":"cat-mm", "world":"cat-world"}
    monkeypatch.setattr(manual_ingestion, "_load_reference_data", lambda _client: (categories, []))
    monkeypatch.setattr(manual_ingestion, "SOURCES", (TECH,))
    monkeypatch.setattr(manual_ingestion, "fetch_feed", lambda _: FetchResult(200, b"fixture", {}, 1))
    monkeypatch.setattr(manual_ingestion, "parse_feed", lambda *_: [
        _entry("OpenAI announces a new AI tool", "https://techcrunch.com/recent", (NOW-timedelta(hours=3)).isoformat()),
        _entry("OpenAI announces an older AI tool", "https://techcrunch.com/old", (NOW-timedelta(hours=36)).isoformat()),
        _entry("Central bank cuts interest rates", "https://techcrunch.com/undated", None),
    ])
    result = asyncio.run(manual_ingestion.run_manual_ingestion(write=False, retry_failed_sources=True, max_age_hours=24))
    source = result["sources"][0]
    assert (source["parsed"], source["evaluated"], source["valid_recent"], source["valid_undated"]) == (3, 3, 1, 1)
    assert (source["rejected"], source["eligible"], source["proposed"]) == (1, 1, 1)
    assert source["rejected_by_category"] == {"technology": 1}
    assert result["category_counts"]["technology"]["valid_recent"] == 1
    assert result["category_counts"]["technology"]["rejected"] == 1
    assert result["category_counts"]["business"]["valid_undated"] == 1


def test_global_proposal_cap_rotates_across_sources_in_stable_order():
    candidates = []
    for source_id, count in (("a", 3), ("b", 3), ("c", 2)):
        for index in range(count):
            candidates.append(({"source_id":source_id}, {"title":f"{source_id}-{index}"}, {}))
    selected = manual_ingestion.select_source_balanced(candidates, 5)
    assert [(item[0]["source_id"], item[1]["title"]) for item in selected] == [
        ("a", "a-0"), ("b", "b-0"), ("c", "c-0"), ("a", "a-1"), ("b", "b-1")]


def test_final_proposal_cap_rotates_categories_and_prefers_dated_articles():
    candidates = []
    for source_id, category, count in (("my", "myanmar", 1), ("fb", "football", 2),
                                       ("biz", "business", 2), ("world", "world", 1),
                                       ("tech", "technology", 4)):
        for index in range(count):
            candidates.append(({"source_id":source_id}, {"category_slug":category,
                "published_at":NOW.isoformat(), "title":f"{category}-{index}"}, {}))
    candidates.append(({"source_id":"my"}, {"category_slug":"myanmar", "published_at":None, "title":"undated"}, {}))
    selected = manual_ingestion.select_category_source_balanced(candidates, 6)
    assert [item[1]["category_slug"] for item in selected] == [
        "myanmar", "football", "business", "world", "technology", "football"]
    assert all(item[1]["published_at"] is not None for item in selected)


def test_existing_tracking_url_and_cross_publisher_similar_title_are_deduplicated(monkeypatch):
    old = {"id": "old", "title": "OpenAI releases a new machine learning tool",
           "url": "https://techcrunch.com/a?utm_source=feed", "published_at": NOW.isoformat(),
           "content_hash": "legacy-hash", "title_hash": "legacy-title", "source": "Old Publisher"}
    monkeypatch.setattr(manual_ingestion, "_load_reference_data", lambda _client: (
        {"technology": "cat-tech", "business": "cat-biz", "football": "cat-foot", "myanmar": "cat-mm", "world": "cat-world"}, [old]))
    monkeypatch.setattr(manual_ingestion, "SOURCES", (TECH,))
    monkeypatch.setattr(manual_ingestion, "fetch_feed", lambda _: FetchResult(200, b"fixture", {}, 1))
    monkeypatch.setattr(manual_ingestion, "parse_feed", lambda *_: [
        _entry("OpenAI releases a new machine learning tool", "https://techcrunch.com/a", NOW.isoformat()),
        _entry("OpenAI releases a new machine learning tools", "https://techcrunch.com/b", NOW.isoformat()),
    ])
    summary = asyncio.run(manual_ingestion.run_manual_ingestion(write=False, retry_failed_sources=True))
    assert summary["totals"]["duplicates"] == 2
    assert summary["proposed"] == []


def test_obvious_promotional_copy_is_rejected_but_short_breaking_news_is_kept():
    promotional = rss_processing.normalize_entry(
        {**_entry("New product launch", "https://techcrunch.com/ad"), "description": "Sponsored content from the partner"},
        TECH, {"technology", "business", "football", "myanmar", "world"}, NOW)
    breaking = rss_processing.normalize_entry(
        {**_entry("Flooding closes Yangon highway", "https://techcrunch.com/news"), "description": None},
        TECH, {"technology", "business", "football", "myanmar", "world"}, NOW)
    assert promotional is None
    assert breaking is not None


def test_briefing_selection_caps_a_publisher_when_other_publishers_are_available():
    from app.services.news.selector import select_publisher_balanced
    clusters = [[{"source": source, "title": str(i)}] for i, source in enumerate(
        ["Publisher A"] * 4 + ["Publisher B", "Publisher C"])]
    selected = select_publisher_balanced(clusters, 5)

    assert len(selected) == 5
    assert sum(item["source"] == "Publisher A" for item in selected) == 3
    assert [item["title"] for item in selected] == ["0", "1", "4", "5", "2"]

    # The cap is a preference, not a hard availability rule.
    fallback = select_publisher_balanced(clusters[:3], 3)
    assert len(fallback) == 3


def test_news_api_orders_by_publication_with_deterministic_tie_breaker(monkeypatch):
    from fastapi.testclient import TestClient
    from app.dependencies.auth import get_current_user
    from app.main import app
    from app.routes import news
    db = Mock()
    db.table.return_value = db
    db.select.return_value = db
    db.eq.return_value = db
    db.in_.return_value = db
    db.order.return_value = db
    db.limit.return_value = db
    db.execute.return_value = SimpleNamespace(data=[])
    monkeypatch.setattr(news, "create_supabase_client", lambda _token: db)
    monkeypatch.setitem(app.dependency_overrides, get_current_user,
                        lambda: {"user_id": "staging-user", "access_token": "fixture"})
    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/news?category_id=00000000-0000-0000-0000-000000000001&limit=20").json() == {"news": []}
        db.order.assert_any_call("published_at", desc=True, nullsfirst=False)
        db.order.assert_any_call("id", desc=True)
    finally:
        app.dependency_overrides.clear()


def test_operator_feeds_route_precedes_dynamic_article_route():
    from fastapi.testclient import TestClient
    from app.dependencies.operator import require_operator
    from app.main import app
    from app.services.news.sources import NEWS_SOURCES

    app.dependency_overrides[require_operator] = lambda: {"operator": True}
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/news/feeds")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total_feeds"] == len(NEWS_SOURCES)
        assert payload["feeds"] == [
            {
                "name": feed["name"],
                "category": feed["category"],
                "feed_url": feed["url"],
            }
            for feed in NEWS_SOURCES
        ]
    finally:
        app.dependency_overrides.clear()
