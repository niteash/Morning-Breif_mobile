# Staging RSS dry run — 20261114T184251Z

Read-only staging run. Database inserts: **0**. AI, audio, notifications and scheduler: disabled.

Sources: 19 successful; 4 failed or intentionally disabled out of 23.
Parsed: 606; valid: 298; duplicates: 0; rejected: 34; proposed inserts (capped): 100; over cap: 198.

| Source | URL | HTTP | Parse | Enabled | Parsed | Valid | Duplicates | Rejected | Failure |
|---|---|---:|---|---:|---:|---:|---:|---:|---|
| Hacker News | https://news.ycombinator.com/rss | 200 | ok | True | 30 | 20 |  |  |  |
| TechCrunch | https://techcrunch.com/feed/ | 200 | ok | True | 20 | 20 |  |  |  |
| The Verge | https://www.theverge.com/rss/index.xml | 200 | ok | True | 10 | 10 |  |  |  |
| Wired | https://www.wired.com/feed/rss | 200 | ok | True | 50 | 20 |  |  |  |
| Ars Technica | https://feeds.arstechnica.com/arstechnica/index | 200 | ok | True | 20 | 20 |  |  |  |
| MIT Technology Review | https://www.technologyreview.com/feed/ | 200 | ok | True | 10 | 10 |  |  |  |
| VentureBeat | https://venturebeat.com/feed/ | 429 | failed | True |  |  |  |  | http_error |
| Engadget | https://www.engadget.com/rss.xml | 200 | ok | True | 20 | 20 |  |  |  |
| CNET | https://www.cnet.com/rss/all/ | 200 | ok | True | 25 | 14 |  | 6 |  |
| NYT Technology | https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml | 200 | ok | True | 40 | 20 |  |  |  |
| DEV Community | https://dev.to/feed | 200 | ok | True | 12 | 12 |  |  |  |
| The Next Web | https://thenextweb.com/latest/feed | 404 | failed | True |  |  |  |  | http_error |
| Slashdot | http://rss.slashdot.org/Slashdot/slashdotMain |  | not_attempted |  |  |  |  |  | disabled_insecure_http_pending_review |
| BBC Sport Football | https://feeds.bbci.co.uk/sport/football/rss.xml | 200 | ok | True | 66 | 20 |  |  |  |
| The Guardian Football | https://www.theguardian.com/football/rss | 200 | ok | True | 57 | 16 |  | 4 |  |
| Forbes Business | https://www.forbes.com/business/feed/ | 200 | ok | True | 25 | 20 |  |  |  |
| CNBC Finance | https://www.cnbc.com/id/10000664/device/rss/rss.html | 200 | ok | True | 30 | 16 |  | 4 |  |
| The Irrawaddy | https://www.irrawaddy.com/feed | 200 | ok | True | 10 | 10 |  |  |  |
| Global New Light of Myanmar | https://www.gnlm.com.mm/feed/rss/ | 200 | ok | True | 10 | 10 |  |  |  |
| Nikkei Asia | https://asia.nikkei.com/rss/feed/nar | 200 | ok | True | 50 | 20 |  |  |  |
| e27 | https://e27.co/index_wp.php/feed | 403 | failed | True |  |  |  |  | http_error |
| The Diplomat | https://thediplomat.com/feed | 200 | ok | True | 96 | 20 |  |  |  |
| ABA Journal | https://feeds.feedburner.com/abajournal/dailynews | 200 | ok | True | 25 |  |  | 20 |  |

The companion JSON contains the exact proposed article metadata (title, publisher, canonical URL, category and publication timestamp) for review before any staging write.

Category limitation: the connected staging database has only Myanmar, Technology, Football, Business and World. Asia-Pacific sources and legal-topic stories are classified into those available categories; the missing category axes are recorded as metadata in the dry-run only and are not persisted.

Runtime: 7778 ms. Run ID: 3fe37ded-80d2-40f7-becf-e6fd01624a5f.
