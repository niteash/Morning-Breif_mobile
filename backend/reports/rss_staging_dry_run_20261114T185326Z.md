# Staging RSS dry run — 20261114T185326Z

Read-only staging pass. **Database writes: 0**. AI, TTS, notifications, scheduler, and trial claims stayed disabled.

- Sources: 20 parsed successfully; 3 failed or disabled of 23.
- Parsed: 618; valid: 313; duplicates: 3; rejected: 34.
- Proposed rows in this bounded review: 100; global cap: 100; over cap: 210.
- Category counts for the proposed subset: {"business": 7, "football": 0, "myanmar": 0, "technology": 92, "world": 1}.
- Run ID: `0ee2213b-bdd0-47c4-8f44-18e25b89582b`; runtime: 8636 ms.

| Source | Candidate URL | HTTP | Parse | Enabled | Failure category | Verified replacement URL | Parsed | Valid | Duplicates | Rejected |
|---|---|---:|---|---|---|---|---:|---:|---:|---:|
| Hacker News | https://news.ycombinator.com/rss | 200 | ok | yes | — | — | 30 | 20 | 0 | 0 |
| TechCrunch | https://techcrunch.com/feed/ | 200 | ok | yes | — | — | 20 | 20 | 0 | 0 |
| The Verge | https://www.theverge.com/rss/index.xml | 200 | ok | yes | — | — | 10 | 10 | 0 | 0 |
| Wired | https://www.wired.com/feed/rss | 200 | ok | yes | — | — | 50 | 20 | 0 | 0 |
| Ars Technica | https://feeds.arstechnica.com/arstechnica/index | 200 | ok | yes | — | — | 20 | 20 | 0 | 0 |
| MIT Technology Review | https://www.technologyreview.com/feed/ | 200 | ok | yes | — | — | 10 | 10 | 0 | 0 |
| VentureBeat | https://venturebeat.com/feed/ | 429 | not_retried_after_recent_failure | yes | source_cooldown | — | 0 | 0 | 0 | 0 |
| Engadget | https://www.engadget.com/rss.xml | 200 | ok | yes | — | — | 20 | 20 | 0 | 0 |
| CNET | https://www.cnet.com/rss/all/ | 200 | ok | yes | — | — | 25 | 14 | 0 | 6 |
| NYT Technology | https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml | 200 | ok | yes | — | — | 40 | 20 | 0 | 0 |
| DEV Community | https://dev.to/feed | 200 | ok | yes | — | — | 12 | 12 | 0 | 0 |
| The Next Web | https://thenextweb.com/latest/feed | — | not_attempted | no | http_404_no_verified_publisher_replacement | — | 0 | 0 | 0 | 0 |
| Slashdot | http://rss.slashdot.org/Slashdot/slashdotMain | 200 | ok | yes | — | https://rss.slashdot.org/Slashdot/slashdotMain | 15 | 15 | 3 | 0 |
| BBC Sport Football | https://feeds.bbci.co.uk/sport/football/rss.xml | 200 | ok | yes | — | — | 63 | 20 | 0 | 0 |
| The Guardian Football | https://www.theguardian.com/football/rss | 200 | ok | yes | — | — | 57 | 16 | 0 | 4 |
| Forbes Business | https://www.forbes.com/business/feed/ | 200 | ok | yes | — | — | 25 | 20 | 0 | 0 |
| CNBC Finance | https://www.cnbc.com/id/10000664/device/rss/rss.html | 200 | ok | yes | — | — | 30 | 16 | 0 | 4 |
| The Irrawaddy | https://www.irrawaddy.com/feed | 200 | ok | yes | — | — | 10 | 10 | 0 | 0 |
| Global New Light of Myanmar | https://www.gnlm.com.mm/feed/rss/ | 200 | ok | yes | — | — | 10 | 10 | 0 | 0 |
| Nikkei Asia | https://asia.nikkei.com/rss/feed/nar | 200 | ok | yes | — | — | 50 | 20 | 0 | 0 |
| e27 | https://e27.co/index_wp.php/feed | — | not_attempted | no | http_403_publisher_access_unavailable | — | 0 | 0 | 0 | 0 |
| The Diplomat | https://thediplomat.com/feed | 200 | ok | yes | — | — | 96 | 20 | 0 | 0 |
| ABA Journal | https://feeds.feedburner.com/abajournal/dailynews | 200 | ok | yes | — | — | 25 | 0 | 0 | 20 |

## Replacement checks

- Slashdot HTTPS feed `https://rss.slashdot.org/Slashdot/slashdotMain`: HTTP 200 and 15 entries parsed. The original HTTP candidate is retained as `candidate_url`; the HTTPS source now runs no more frequently than the publisher's documented 30-minute interval.
- The Next Web publisher-hosted candidate returned HTTP 404. Its publisher-documented historical Feedburner endpoint `https://feeds2.feedburner.com/thenextweb` also returned HTTP 404; it remains disabled because no working publisher-approved replacement was verified.
- e27's supplied feed returned HTTP 403 and remains disabled. No alternate endpoint or scraping workaround was attempted.
- VentureBeat returned HTTP 429 on the initial validation. Rate limiting now stops in-run retries and records a bounded `Retry-After` cooldown. This dry-run does not bypass a current cooldown.

The JSON sidecar contains the exact proposed public article metadata (publisher, title, canonical URL, category and publication time). Review that file before approving any staging write. No staging write command was run.

The staging schema exposes only Myanmar, Technology, Football, Business and World categories. Asia-Pacific and Legal are mapped deterministically onto available primary categories; `topic_group` is audit-only and is not persisted in the current schema.
