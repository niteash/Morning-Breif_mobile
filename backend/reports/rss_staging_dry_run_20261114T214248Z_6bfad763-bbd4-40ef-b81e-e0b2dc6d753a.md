# RSS staging dry run — 20261114T214248Z

Environment: staging. Batch SHA-256: `d1215ebe763707fcd76201ceebbe849a724d450c365900f184ffaf63f1d4142d`. Approval expires: `2026-11-14T22:42:48+00:00`. No database writes were performed.

Sources: 20 parseable; 3 failed or disabled of 23. Parsed: 621; evaluated (per-feed cap): 347; valid within 24h: 181; undated: 20; rejected: 146; duplicates: 3; eligible: 178; proposals: 100; over cap: 78.

| Source | Candidate URL | HTTP | Parse | Enabled | Failure category | Verified replacement URL | Parsed | Evaluated | Valid ≤24h | Undated | Rejected | Duplicates | Eligible | Proposed |
|---|---|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Hacker News | https://news.ycombinator.com/rss | 200 | ok | yes | — | — | 30 | 20 | 14 | 0 | 6 | 0 | 14 | 3 |
| TechCrunch | https://techcrunch.com/feed/ | 200 | ok | yes | — | — | 20 | 20 | 9 | 0 | 11 | 0 | 9 | 4 |
| The Verge | https://www.theverge.com/rss/index.xml | 200 | ok | yes | — | — | 10 | 10 | 10 | 0 | 0 | 0 | 10 | 3 |
| Wired | https://www.wired.com/feed/rss | 200 | ok | yes | — | — | 50 | 20 | 20 | 0 | 0 | 0 | 20 | 5 |
| Ars Technica | https://feeds.arstechnica.com/arstechnica/index | 200 | ok | yes | — | — | 20 | 20 | 5 | 0 | 15 | 0 | 5 | 5 |
| MIT Technology Review | https://www.technologyreview.com/feed/ | 200 | ok | yes | — | — | 10 | 10 | 0 | 0 | 10 | 0 | 0 | 0 |
| VentureBeat | https://venturebeat.com/feed/ | 429 | failed | yes | rate_limited | — | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Engadget | https://www.engadget.com/rss.xml | 200 | ok | yes | — | — | 20 | 20 | 20 | 0 | 0 | 0 | 20 | 4 |
| CNET | https://www.cnet.com/rss/all/ | 200 | ok | yes | — | — | 25 | 20 | 12 | 0 | 8 | 0 | 12 | 3 |
| NYT Technology | https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml | 200 | ok | yes | — | — | 41 | 20 | 4 | 0 | 16 | 0 | 4 | 3 |
| DEV Community | https://dev.to/feed | 200 | ok | yes | — | — | 12 | 12 | 12 | 0 | 0 | 2 | 10 | 2 |
| The Next Web | https://thenextweb.com/latest/feed | 404 | not_attempted | no | http_404_no_verified_publisher_replacement | — | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Slashdot | http://rss.slashdot.org/Slashdot/slashdotMain | 200 | ok | yes | — | https://rss.slashdot.org/Slashdot/slashdotMain | 15 | 15 | 13 | 0 | 2 | 1 | 12 | 7 |
| BBC Sport Football | https://feeds.bbci.co.uk/sport/football/rss.xml | 200 | ok | yes | — | — | 63 | 20 | 18 | 0 | 2 | 0 | 18 | 18 |
| The Guardian Football | https://www.theguardian.com/football/rss | 200 | ok | yes | — | — | 59 | 20 | 11 | 0 | 9 | 0 | 11 | 11 |
| Forbes Business | https://www.forbes.com/business/feed/ | 200 | ok | yes | — | — | 25 | 20 | 20 | 0 | 0 | 0 | 20 | 19 |
| CNBC Finance | https://www.cnbc.com/id/10000664/device/rss/rss.html | 200 | ok | yes | — | — | 30 | 20 | 3 | 0 | 17 | 0 | 3 | 3 |
| The Irrawaddy | https://www.irrawaddy.com/feed | 200 | ok | yes | — | — | 10 | 10 | 0 | 0 | 10 | 0 | 0 | 0 |
| Global New Light of Myanmar | https://www.gnlm.com.mm/feed/rss/ | 200 | ok | yes | — | — | 10 | 10 | 10 | 0 | 0 | 0 | 10 | 10 |
| Nikkei Asia | https://asia.nikkei.com/rss/feed/nar | 200 | ok | yes | — | — | 50 | 20 | 0 | 20 | 0 | 0 | 0 | 0 |
| e27 | https://e27.co/index_wp.php/feed | 403 | not_attempted | no | http_403_publisher_access_unavailable | — | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| The Diplomat | https://thediplomat.com/feed | 200 | ok | yes | — | — | 96 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| ABA Journal | https://feeds.feedburner.com/abajournal/dailynews | 200 | ok | yes | — | — | 25 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |

## Category totals

| Category | Valid ≤24h | Undated | Rejected | Duplicates | Eligible | Proposed |
|---|---:|---:|---:|---:|---:|---:|
| business | 29 | 12 | 20 | 0 | 29 | 28 |
| football | 29 | 0 | 11 | 0 | 29 | 29 |
| myanmar | 9 | 0 | 9 | 0 | 9 | 9 |
| technology | 108 | 4 | 71 | 3 | 105 | 28 |
| world | 6 | 4 | 35 | 0 | 6 | 6 |

The JSON sidecar contains the immutable database rows, source/category mapping and approval-bound metadata.
