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
    {"name": "BBC Business", "url": "https://feeds.bbci.co.uk/news/business/rss.xml", "category": "business"},
    {"name": "Nikkei Asia", "url": "https://asia.nikkei.com/rss/feed/nar", "category": "business"},

    # Cryptocurrency and digital assets
    {"name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "category": "crypto"},
    {"name": "Cointelegraph", "url": "https://cointelegraph.com/rss", "category": "crypto"},
    {"name": "Decrypt", "url": "https://decrypt.co/feed", "category": "crypto"},

    # Psychology and behavioral science
    {"name": "ScienceDaily Psychology", "url": "https://www.sciencedaily.com/rss/mind_brain/psychology.xml", "category": "psychology"},
    {"name": "APA News", "url": "https://www.apa.org/news/apa/rss.xml", "category": "psychology"},
    {"name": "APA PsycPORT", "url": "https://www.apa.org/news/psycport/psycport-rss.xml", "category": "psychology"},

    # Horoscope and astrology (presented as entertainment, not factual advice)
    {"name": "Hindustan Times Horoscope", "url": "https://www.hindustantimes.com/feeds/rss/astrology/horoscope/rssfeed.xml", "category": "horoscope"},
    {"name": "Hindustan Times Astrology", "url": "https://www.hindustantimes.com/feeds/rss/astrology/rssfeed.xml", "category": "horoscope"},

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
