import re
from typing import Optional


CATEGORY_ALIASES = {
    "technology": "tech",
    "football": "football",
    "business": "business",
    "world": "world",
    "myanmar": "myanmar",
}


CATEGORY_STRONG_KEYWORDS = {
    "tech": {
        "artificial intelligence",
        "generative ai",
        "large language model",
        "machine learning",
        "openai",
        "google deepmind",
        "anthropic",
        "nvidia",
        "software update",
        "cybersecurity",
        "semiconductor",
        "cloud computing",
        "technology",
        "tech industry",
        "smartphone",
        "robotics",
    },
    "business": {
        "central bank",
        "interest rates",
        "stock market",
        "financial markets",
        "quarterly earnings",
        "corporate earnings",
        "initial public offering",
        "venture capital",
        "private equity",
        "merger",
        "acquisition",
        "inflation",
        "economic growth",
        "trade deal",
        "startup funding",

        "business activity",

        "economic activity",

        "price pressures",

        "consumer spending",

        "retail sales",

        "manufacturing output",

        "industrial production",

        "job growth",

        "unemployment rate",

        "trade deficit",

        "trade surplus",

        "market volatility",

        "banking regulation",

        "financial regulation",

        "tokenization",

        "corporate restructuring",
    },
    "football": {
        "premier league",
        "champions league",
        "fifa",
        "uefa",
        "world cup",
        "football club",
        "football match",
        "transfer window",
        "football manager",
        "goalkeeper",
        "striker",
        "penalty shootout",
        "footballer",
        "soccer",
    },
    "world": {
        "international relations",
        "united nations",
        "security council",
        "international summit",
        "diplomatic talks",
        "foreign policy",
        "ceasefire",
        "peace agreement",
        "international conflict",
        "world leaders",
        "nato",
        "european union",
    },
    "myanmar": {
        "myanmar",
        "burma",
        "yangon",
        "naypyidaw",
        "mandalay",
        "sagaing",
        "shan state",
        "kachin state",
        "rakhine state",
        "karen state",
        "chin state",
        "ayeyarwady",
        "tanintharyi",
        "mon state",
        "myanmar military",
    },
}


CATEGORY_SUPPORTING_KEYWORDS = {
    "tech": {
        "ai",
        "model",
        "software",
        "hardware",
        "chip",
        "processor",
        "data center",
        "developer",
        "programming",
        "robot",
        "automation",
        "startup",
        "app",
        "platform",
        "internet",
        "digital",
        "electric vehicle",
    },
    "business": {
        "company",
        "companies",
        "revenue",
        "profit",
        "investment",
        "investor",
        "shares",
        "stocks",
        "bank",
        "economy",
        "economic",
        "market",
        "trade",
        "export",
        "import",
        "business",
        "funding",
        "acquisition",
        "ceo",
    },
    "football": {
        "goal",
        "goals",
        "match",
        "fixture",
        "league",
        "club",
        "manager",
        "coach",
        "striker",
        "midfielder",
        "defender",
        "goalkeeper",
        "transfer",
        "penalty",
        "tournament",
        "football",
        "soccer",
    },
    "world": {
        "country",
        "countries",
        "government",
        "president",
        "minister",
        "parliament",
        "diplomacy",
        "international",
        "border",
        "conflict",
        "war",
        "sanctions",
        "election",
        "treaty",
        "military",
        "refugees",
    },
    "myanmar": {
        "myanmar",
        "burma",
        "yangon",
        "naypyidaw",
        "mandalay",
        "sagaing",
        "myitkyina",
        "taunggyi",
        "bago",
        "pyay",
        "magway",
        "moulmein",
        "pathein",
        "kachin",
        "shan",
        "rakhine",
        "karen",
        "kayin",
        "chin",
        "mon state",
        "ayeyarwady",
        "tanintharyi",
    },
}


CATEGORY_EXCLUSIONS = {
    "football": {
        "american football",
        "national football league",
        "nfl",
        "college football",
        "rugby football",
    },
}


def normalize_text(text: Optional[str]) -> str:
    """Normalize text while preserving meaningful word boundaries."""
    if not text:
        return ""

    text = text.lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9\s'-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def keyword_matches(text: str, keywords: set[str]) -> list[str]:
    """Return keywords found as complete words or phrases."""
    matches = []

    for keyword in keywords:
        normalized_keyword = normalize_text(keyword)

        if not normalized_keyword:
            continue

        pattern = (
            r"(?<![a-z0-9])"
            + re.escape(normalized_keyword)
            + r"(?![a-z0-9])"
        )

        if re.search(pattern, text):
            matches.append(normalized_keyword)

    return matches


def count_keyword_matches(text: str, keywords: set[str]) -> int:
    return len(keyword_matches(text, keywords))


def _normalize_category(category_slug: str) -> str:
    category = normalize_text(category_slug).replace(" ", "_")
    return CATEGORY_ALIASES.get(category, category)


def _is_excluded(category: str, text: str) -> bool:
    exclusions = CATEGORY_EXCLUSIONS.get(category, set())
    return bool(keyword_matches(text, exclusions))


def calculate_relevance_score(
    category_slug: str,
    title: str,
    description: Optional[str] = None,
) -> int:
    """
    Calculate how relevant an article is to its assigned category.

    Title matches receive more weight than description matches.
    Strong category-specific terms receive additional weight.
    """
    category = _normalize_category(category_slug)

    if category not in CATEGORY_STRONG_KEYWORDS:
        return 0

    title_text = normalize_text(title)
    description_text = normalize_text(description)

    combined_text = f"{title_text} {description_text}".strip()

    if not title_text:
        return 0

    if _is_excluded(category, combined_text):
        return 0

    strong_keywords = CATEGORY_STRONG_KEYWORDS[category]
    supporting_keywords = CATEGORY_SUPPORTING_KEYWORDS[category]

    strong_title = count_keyword_matches(title_text, strong_keywords)
    strong_description = count_keyword_matches(
        description_text, strong_keywords
    )

    supporting_title = count_keyword_matches(
        title_text, supporting_keywords
    )
    supporting_description = count_keyword_matches(
        description_text, supporting_keywords
    )

    score = (
        strong_title * 8
        + strong_description * 3
        + supporting_title * 3
        + supporting_description
    )

    return score


def is_relevant(
    category: str,
    title: str,
    description: str | None = None,
) -> bool:
    """
    Determine whether an article is relevant to its category.

    World news should prioritize actual international developments,
    not generic World headlines, rankings, expos, or holiday listicles.
    """
    category_slug = CATEGORY_ALIASES.get(
        normalize_text(category),
        normalize_text(category),
    )

    title_text = normalize_text(title or "")
    description_text = normalize_text(description or "")

    if not title_text:
        return False

    combined_text = f"{title_text} {description_text}"

    # Reject obvious spam and low-value headlines before keyword matching.
    if category_slug == "football":
        football_spam_patterns = [
            r"\blivestreams?\b",
            r"\blive\s+streams?\b",
            r"\bfree\s+(?:live\s+)?streams?\b",
            r"\bwatch\s+(?:the\s+)?(?:match|game)\s+live\b",
            r"\blive\s+on\s+(?:tv|television)\b",
            r"\btv\s+channel\s+free\b",
            r"\bstreaming\s+links?\b",
        ]

        if any(re.search(pattern, title_text) for pattern in football_spam_patterns):
            return False

        # Exclude broadcast schedules rather than football reporting.
        if (
            re.search(r"\bwhat channel\b", title_text)
            and re.search(
                r"\b(?:live stream|tv coverage|kick[- ]off time)\b",
                title_text,
            )
        ):
            return False

    if category_slug == "business":
        business_low_value_patterns = [
            r"\bspeed networking\b",
            r"\bsmall business month\b",
            r"\bwomen'?s small business month\b",
            r"\b(?:business|commercial) (?:park|district) helps drive\b",
            r"\b(?:school|college) of business\b",
            r"\b(?:restaurant|bar|shop) closing\b",
            r"\bfaces cleanup after\b",
            r"\b(?:business owner|owner of a business) arrested\b",
            r"\bbusiness owner linked to\b",
        ]

        if any(re.search(pattern, title_text) for pattern in business_low_value_patterns):
            return False

    # Reject obvious non-news content for the World category.
    if category_slug == "world":
        low_value_patterns = [
            r"\b\d+\s+(interesting\s+)?facts?\b",
            r"\bworld university rankings?\b",
            r"\buniversity rankings?\b",
            r"\bdairy expo\b",
            r"\bexpo returns\b",
            r"\bhistory objectives\b",
            r"\bhow to celebrate\b",
            r"\bwishes and messages\b",
            r"\bquotes for\b",
            r"\bessay on\b",
            r"\bspeech on\b",
            r"\bposter making\b",
            r"\bcelebrated on\b",
            r"\bobserved on\b",

            r"\b(united nations|un) day\b",

            r"\binternational day of\b",

            r"\bworld day of\b",

            r"\bholiday wishes\b",
        ]

        if any(
            re.search(pattern, title_text)
            for pattern in low_value_patterns
        ):
            return False

        generic_appeal_patterns = [
            r"^un chief calls for efforts to",
            r"^un chief urges efforts to",
            r"^un chief appeals for",
            r"^un chief calls on .* to",
        ]

        if any(
            re.search(pattern, title_text)
            for pattern in generic_appeal_patterns
        ):
            return False

    strong_keywords = CATEGORY_STRONG_KEYWORDS.get(
        category_slug,
        [],
    )
    supporting_keywords = CATEGORY_SUPPORTING_KEYWORDS.get(
        category_slug,
        [],
    )

    strong_title_matches = count_keyword_matches(
        title_text,
        strong_keywords,
    )

    strong_description_matches = count_keyword_matches(
        description_text,
        strong_keywords,
    )

    supporting_title_matches = count_keyword_matches(
        title_text,
        supporting_keywords,
    )

    supporting_description_matches = count_keyword_matches(
        description_text,
        supporting_keywords,
    )

    # A strong headline match normally indicates relevance.
    if strong_title_matches > 0:
        return True

    # For World news, recognize concrete international developments
    # even when the title does not contain an existing strong keyword.
    if category_slug == "world":
        world_development_patterns = [
            r"\b(expels?|expelled|deports?|deported)\b",
            r"\b(diplomat|diplomats|diplomacy|diplomatic)\b",
            r"\b(trilateral talks|peace talks|peace negotiations)\b",
            r"\b(resume talks|restart talks|negotiations resume)\b",
            r"\b(airstrikes?|missile strikes?|drone attacks?)\b",
            r"\b(ceasefire|armed conflict|humanitarian crisis)\b",
            r"\b(refugees?|displaced people|humanitarian aid)\b",
            r"\b(sanctions?|espionage|foreign ministry)\b",
            r"\b(border clashes|military offensive|peace agreement)\b",
            r"\b(election results|coup|international tribunal)\b",

            r"\b(un chief|un secretary-general|secretary-general|secretary general)\b",

            r"\b(nominates?|nomination|appoints?|appointed)\b.*\b(un|united nations|secretary-general|secretary general)\b",

            r"\b(postpones?|postponed|delays?|delayed)\b.*\b(forum|summit|meeting|talks|election)\b",

            r"\b(stop|halt|end|expand|expanding)\b.*\b(conflicts?|wars?|violence)\b",

            r"\b(scrutiny|probe|investigation|allegations?)\b.*\b(chemical weapons?|un|united nations|army|military)\b",

            r"\b(regional tensions|security council)\b",
        ]

        if any(
            re.search(pattern, combined_text)
            for pattern in world_development_patterns
        ):
            return True

    # A strong keyword in the description requires additional context.
    if strong_description_matches > 0:
        return (
            supporting_title_matches >= 1
            or supporting_description_matches >= 2
        )

    # Supporting terms alone need multiple signals in the headline.
    return (
        supporting_title_matches >= 2
        and calculate_relevance_score(
            category_slug,
            title,
            description or "",
        ) >= 6
    )