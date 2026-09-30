import re


# ============================================================
# CATEGORY KEYWORDS
# ============================================================

CATEGORY_KEYWORDS = {

    # --------------------------------------------------------
    # FOOTBALL
    # --------------------------------------------------------

    "football": {
        "football",
        "soccer",
        "fifa",
        "uefa",
        "premier league",
        "champions league",
        "europa league",
        "conference league",
        "la liga",
        "serie a",
        "bundesliga",
        "ligue 1",
        "fa cup",
        "efl cup",
        "carabao cup",
        "world cup",
        "club world cup",
        "afc champions league",
        "afc cup",
        "asian cup",
        "football club",
        "football team",
        "footballer",
        "goalkeeper",
        "striker",
        "midfielder",
        "defender",
        "transfer",
        "transfer window",
        "signing",
    },

    # --------------------------------------------------------
    # BUSINESS
    # --------------------------------------------------------

    "business": {
        "business",
        "economy",
        "economic",
        "market",
        "markets",
        "finance",
        "financial",
        "stock",
        "stocks",
        "investment",
        "investor",
        "company",
        "companies",
        "startup",
        "corporate",
        "trade",
        "bank",
        "banking",
        "inflation",
        "interest rate",
        "gdp",
        "revenue",
        "profit",
        "merger",
        "acquisition",
        "ipo",
        "earnings",
        "shareholders",
        "shares",
        "venture capital",
        "private equity",
    },

    # --------------------------------------------------------
    # TECHNOLOGY
    # IMPORTANT: database slug is "tech", not "technology"
    # --------------------------------------------------------

    "tech": {
        "technology",
        "tech",
        "artificial intelligence",
        "ai",
        "machine learning",
        "generative ai",
        "genai",
        "openai",
        "chatgpt",
        "google ai",
        "gemini",
        "microsoft",
        "apple",
        "meta",
        "nvidia",
        "chip",
        "chips",
        "semiconductor",
        "software",
        "cybersecurity",
        "robotics",
        "cloud computing",
        "cloud",
        "data center",
        "data centre",
        "startup",
        "smartphone",
        "iphone",
        "android",
        "computer",
        "developer",
        "programming",
    },

    # --------------------------------------------------------
    # WORLD
    # --------------------------------------------------------

    "world": {
        "world",
        "international",
        "global",
        "geopolitics",
        "diplomacy",
        "international relations",
        "foreign policy",
        "president",
        "government",
        "election",
        "war",
        "conflict",
        "sanctions",
        "united nations",
        "nato",
        "europe",
        "asia",
        "middle east",
        "africa",
        "ukraine",
        "russia",
        "china",
        "united states",
        "iran",
        "israel",
        "palestine",
    },

    # --------------------------------------------------------
    # MYANMAR
    # --------------------------------------------------------

    "myanmar": {
        "myanmar",
        "burma",
        "yangon",
        "mandalay",
        "naypyidaw",
        "rakhine",
        "shan",
        "kachin",
        "karen",
        "chin",
        "mon",
        "sagaing",
        "magway",
        "ayeyarwady",
        "myawaddy",
        "tanintharyi",
        "bago",
        "kayin",
    },
}


# ============================================================
# CATEGORY EXCLUDED KEYWORDS
# ============================================================

CATEGORY_EXCLUDED_KEYWORDS = {

    "football": {
        "flag football",
        "high school football",
        "college football",
        "american football",
        "nfl",
        "ncaa football",
        "touchdown",
        "quarterback",
        "running back",
        "wide receiver",
        "super bowl",
    },

}


# ============================================================
# NORMALIZE TEXT
# ============================================================

def normalize_text(text: str) -> str:
    """
    Normalize text before keyword matching.
    """

    text = text.lower()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# ============================================================
# FOOTBALL RELEVANCE
# ============================================================

def is_football_relevant(text: str) -> bool:
    """
    Football-specific relevance check.

    Strong football terms are enough by themselves.

    Generic football terms require stronger context.
    """

    # -----------------------------------------
    # Strong football terms
    # -----------------------------------------

    strong_keywords = {
        "soccer",
        "fifa",
        "uefa",
        "premier league",
        "champions league",
        "europa league",
        "conference league",
        "la liga",
        "serie a",
        "bundesliga",
        "ligue 1",
        "fa cup",
        "efl cup",
        "carabao cup",
        "world cup",
        "club world cup",
        "afc champions league",
        "afc cup",
        "asian cup",
        "footballer",
        "football club",
        "football team",
        "goalkeeper",
        "striker",
        "midfielder",
        "defender",
        "transfer window",
    }

    if any(
        keyword in text
        for keyword in strong_keywords
    ):
        return True

    # -----------------------------------------
    # Medium football terms
    # -----------------------------------------

    medium_keywords = {
        "football",
        "transfer",
        "signing",
        "manager",
        "coach",
        "fixture",
        "league",
        "cup",
        "goal",
        "goals",
        "player",
        "match",
    }

    matches = sum(
        keyword in text
        for keyword in medium_keywords
    )

    # Require at least 2 generic football
    # signals to reduce false positives.
    return matches >= 2


# ============================================================
# MAIN RELEVANCE FUNCTION
# ============================================================

def is_relevant(
    category_slug: str,
    title: str,
    description: str | None = None,
) -> bool:
    """
    Determine whether an article belongs to
    the requested category.
    """

    # -----------------------------------------
    # Combine title + description
    # -----------------------------------------

    text = normalize_text(
        f"{title} {description or ''}"
    )

    # -----------------------------------------
    # Reject explicitly excluded content
    # -----------------------------------------

    excluded_keywords = (
        CATEGORY_EXCLUDED_KEYWORDS.get(
            category_slug,
            set(),
        )
    )

    for keyword in excluded_keywords:

        if keyword in text:
            return False

    # -----------------------------------------
    # Football has special logic
    # -----------------------------------------

    if category_slug == "football":
        return is_football_relevant(text)

    # -----------------------------------------
    # Get category keywords
    # -----------------------------------------

    keywords = CATEGORY_KEYWORDS.get(
        category_slug,
        set(),
    )

    # -----------------------------------------
    # Unknown category
    # -----------------------------------------

    if not keywords:
        return True

    # -----------------------------------------
    # Normal keyword matching
    # -----------------------------------------

    return any(
        keyword in text
        for keyword in keywords
    )