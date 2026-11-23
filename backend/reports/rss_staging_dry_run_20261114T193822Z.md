# RSS staging dry run — 20261114T193822Z

Environment: staging. Database inserts: **0**. AI, TTS, notifications, scheduler and trial claims remain disabled.

Sources: 20 parseable; 3 failed or disabled of 23. Parsed: 616; evaluated (per-feed cap): 347; valid within 24h: 171; undated: 20; rejected: 156; duplicates: 1; eligible: 190; proposals: 100; over cap: 90; database writes: 0.

| Source | Candidate URL | HTTP | Parse | Enabled | Failure category | Verified replacement URL | Parsed | Evaluated | Valid ≤24h | Undated | Rejected | Duplicates | Eligible | Proposed |
|---|---|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Hacker News | https://news.ycombinator.com/rss | 200 | ok | yes | — | — | 30 | 20 | 14 | 0 | 6 | 0 | 14 | 7 |
| TechCrunch | https://techcrunch.com/feed/ | 200 | ok | yes | — | — | 20 | 20 | 8 | 0 | 12 | 0 | 8 | 7 |
| The Verge | https://www.theverge.com/rss/index.xml | 200 | ok | yes | — | — | 10 | 10 | 10 | 0 | 0 | 0 | 10 | 7 |
| Wired | https://www.wired.com/feed/rss | 200 | ok | yes | — | — | 50 | 20 | 20 | 0 | 0 | 0 | 20 | 7 |
| Ars Technica | https://feeds.arstechnica.com/arstechnica/index | 200 | ok | yes | — | — | 20 | 20 | 8 | 0 | 12 | 0 | 8 | 7 |
| MIT Technology Review | https://www.technologyreview.com/feed/ | 200 | ok | yes | — | — | 10 | 10 | 0 | 0 | 10 | 0 | 0 | 0 |
| VentureBeat | https://venturebeat.com/feed/ | 429 | failed | yes | rate_limited | — | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Engadget | https://www.engadget.com/rss.xml | 200 | ok | yes | — | — | 20 | 20 | 20 | 0 | 0 | 0 | 20 | 7 |
| CNET | https://www.cnet.com/rss/all/ | 200 | ok | yes | — | — | 25 | 20 | 13 | 0 | 7 | 0 | 13 | 7 |
| NYT Technology | https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml | 200 | ok | yes | — | — | 40 | 20 | 5 | 0 | 15 | 0 | 5 | 5 |
| DEV Community | https://dev.to/feed | 200 | ok | yes | — | — | 12 | 12 | 12 | 0 | 0 | 0 | 12 | 7 |
| The Next Web | https://thenextweb.com/latest/feed | 404 | not_attempted | no | http_404_no_verified_publisher_replacement | — | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Slashdot | http://rss.slashdot.org/Slashdot/slashdotMain | 200 | ok | yes | — | https://rss.slashdot.org/Slashdot/slashdotMain | 15 | 15 | 13 | 0 | 2 | 1 | 12 | 7 |
| BBC Sport Football | https://feeds.bbci.co.uk/sport/football/rss.xml | 200 | ok | yes | — | — | 61 | 20 | 16 | 0 | 4 | 0 | 16 | 7 |
| The Guardian Football | https://www.theguardian.com/football/rss | 200 | ok | yes | — | — | 57 | 20 | 8 | 0 | 12 | 0 | 8 | 7 |
| Forbes Business | https://www.forbes.com/business/feed/ | 200 | ok | yes | — | — | 25 | 20 | 20 | 0 | 0 | 0 | 20 | 7 |
| CNBC Finance | https://www.cnbc.com/id/10000664/device/rss/rss.html | 200 | ok | yes | — | — | 30 | 20 | 3 | 0 | 17 | 0 | 3 | 3 |
| The Irrawaddy | https://www.irrawaddy.com/feed | 200 | ok | yes | — | — | 10 | 10 | 0 | 0 | 10 | 0 | 0 | 0 |
| Global New Light of Myanmar | https://www.gnlm.com.mm/feed/rss/ | 200 | ok | yes | — | — | 10 | 10 | 1 | 0 | 9 | 0 | 1 | 1 |
| Nikkei Asia | https://asia.nikkei.com/rss/feed/nar | 200 | ok | yes | — | — | 50 | 20 | 0 | 20 | 0 | 0 | 20 | 7 |
| e27 | https://e27.co/index_wp.php/feed | 403 | not_attempted | no | http_403_publisher_access_unavailable | — | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| The Diplomat | https://thediplomat.com/feed | 200 | ok | yes | — | — | 96 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| ABA Journal | https://feeds.feedburner.com/abajournal/dailynews | 200 | ok | yes | — | — | 25 | 20 | 0 | 0 | 20 | 0 | 0 | 0 |

## Category totals

| Category | Valid ≤24h | Undated | Rejected | Duplicates | Eligible | Proposed |
|---|---:|---:|---:|---:|---:|---:|
| business | 31 | 12 | 18 | 0 | 43 | 19 |
| football | 25 | 0 | 16 | 0 | 25 | 14 |
| myanmar | 1 | 0 | 17 | 0 | 1 | 1 |
| technology | 110 | 4 | 69 | 1 | 113 | 63 |
| world | 4 | 4 | 36 | 0 | 8 | 3 |

The JSON sidecar contains per-source and per-category counts plus exact proposed database metadata. A staging write requires explicit approval of that report and its run ID; the live proposal set is rechecked before any database mutation.
