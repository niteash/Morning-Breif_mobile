from uuid import UUID

CATEGORY_IDS = {
    "technology": UUID("bd5d3262-e705-4595-859b-1b63e775e445"),
    "business": UUID("0be82b81-4a28-4456-9c2f-83b185777846"),
    "football": UUID("51d3202c-890e-4732-ab10-dbf7f3431d73"),
    "world": UUID("b96b933b-7fa4-4bbd-ae82-2b653ffdc1bb"),
    "myanmar": UUID("fc9d5cba-d415-4515-a2b5-b5d03d9d7666"),
}

NEWS_SOURCES = [
    # Technology
    {"name": "Hacker News", "url": "https://news.ycombinator.com/rss", "category": "technology"},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "category": "technology"},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "category": "technology"},
    {"name": "Wired", "url": "https://www.wired.com/feed/rss", "category": "technology"},
    {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index", "category": "technology"},
    {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/feed/", "category": "technology"},
    {"name": "VentureBeat", "url": "https://venturebeat.com/feed/", "category": "technology"},
    {"name": "Engadget", "url": "https://www.engadget.com/rss.xml", "category": "technology"},
    {"name": "CNET", "url": "https://www.cnet.com/rss/all/", "category": "technology"},
    {"name": "NYT Technology", "url": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml", "category": "technology"},
    {"name": "DEV Community", "url": "https://dev.to/feed", "category": "technology"},
    {"name": "The Next Web", "url": "https://thenextweb.com/latest/feed", "category": "technology"},
    {"name": "Slashdot", "url": "http://rss.slashdot.org/Slashdot/slashdotMain", "category": "technology"},
    {"name": "e27", "url": "https://e27.co/index_wp.php/feed", "category": "technology"},

    # Business and finance
    {"name": "Forbes Business", "url": "https://www.forbes.com/business/feed/", "category": "business"},
    {"name": "CNBC Finance", "url": "https://www.cnbc.com/id/10000664/device/rss/rss.html", "category": "business"},
    {"name": "Nikkei Asia", "url": "https://asia.nikkei.com/rss/feed/nar", "category": "business"},

    # Football
    {"name": "BBC Sport Football", "url": "https://feeds.bbci.co.uk/sport/football/rss.xml", "category": "football"},
    {"name": "The Guardian Football", "url": "https://www.theguardian.com/football/rss", "category": "football"},

    # World and international affairs
    {"name": "The Diplomat", "url": "https://thediplomat.com/feed", "category": "world"},
    {"name": "ABA Journal", "url": "https://feeds.feedburner.com/abajournal/dailynews", "category": "world"},

    # Myanmar
    {"name": "The Irrawaddy", "url": "https://www.irrawaddy.com/feed", "category": "myanmar"},
    {"name": "Global New Light of Myanmar", "url": "https://www.gnlm.com.mm/feed/rss/", "category": "myanmar"},
]

HEADLINES_PER_SOURCE = 4
MAX_HEADLINE_AGE_HOURS = 36