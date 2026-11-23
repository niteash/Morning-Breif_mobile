# RSS staging dry run — 20261114T190323Z

Environment: staging. Database inserts: **0**. AI, TTS, notifications, scheduler and trial claims remain disabled.

Sources: 20 parseable; 3 failed or disabled of 23. Parsed: 617; valid: 313; duplicates: 3; rejected: 34; proposals: 100; over cap: 210.

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
| The Next Web | https://thenextweb.com/latest/feed | 404 | not_attempted | no | http_404_no_verified_publisher_replacement | — | 0 | 0 | 0 | 0 |
| Slashdot | http://rss.slashdot.org/Slashdot/slashdotMain | 200 | ok | yes | — | https://rss.slashdot.org/Slashdot/slashdotMain | 15 | 15 | 3 | 0 |
| BBC Sport Football | https://feeds.bbci.co.uk/sport/football/rss.xml | 200 | ok | yes | — | — | 62 | 20 | 0 | 0 |
| The Guardian Football | https://www.theguardian.com/football/rss | 200 | ok | yes | — | — | 57 | 16 | 0 | 4 |
| Forbes Business | https://www.forbes.com/business/feed/ | 200 | ok | yes | — | — | 25 | 20 | 0 | 0 |
| CNBC Finance | https://www.cnbc.com/id/10000664/device/rss/rss.html | 200 | ok | yes | — | — | 30 | 16 | 0 | 4 |
| The Irrawaddy | https://www.irrawaddy.com/feed | 200 | ok | yes | — | — | 10 | 10 | 0 | 0 |
| Global New Light of Myanmar | https://www.gnlm.com.mm/feed/rss/ | 200 | ok | yes | — | — | 10 | 10 | 0 | 0 |
| Nikkei Asia | https://asia.nikkei.com/rss/feed/nar | 200 | ok | yes | — | — | 50 | 20 | 0 | 0 |
| e27 | https://e27.co/index_wp.php/feed | 403 | not_attempted | no | http_403_publisher_access_unavailable | — | 0 | 0 | 0 | 0 |
| The Diplomat | https://thediplomat.com/feed | 200 | ok | yes | — | — | 96 | 20 | 0 | 0 |
| ABA Journal | https://feeds.feedburner.com/abajournal/dailynews | 200 | ok | yes | — | — | 25 | 0 | 0 | 20 |

The JSON sidecar contains exact proposed database metadata. A staging write requires explicit approval of that report and its run ID; the live proposal set is rechecked before any database mutation.

## Follow-up source checks

- Slashdot's verified HTTPS feed returned HTTP 200 and parsed 15 entries. The
  source uses a 30-minute minimum interval, matching its [publisher FAQ](https://tech.slashdot.org/faq).
- The Next Web candidate returned HTTP 404. Its [publisher article](https://thenextweb.com/news/get-tnw-internet-diet)
  documents an older Feedburner URL; that HTTPS endpoint also returned 404 during
  the bounded check. The source remains disabled because no working publisher-approved
  replacement was verified.
- e27's supplied feed returned HTTP 403 during the first dry run. It remains disabled;
  no alternate endpoint or scraping workaround was attempted.
- VentureBeat returned HTTP 429 in the first run. The later dry runs respected the
  resulting cooldown and did not retry it. Retry only after that cooldown expires.

The extra endpoint checks were read-only. Production was not accessed, and no
staging database write was performed.
