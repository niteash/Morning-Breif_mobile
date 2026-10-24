import re

from .ranker import title_similarity
from .relevance import normalize_text


EVENT_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "by",
    "for", "from", "has", "have", "in", "into", "is", "it",
    "its", "of", "on", "or", "that", "the", "their", "this",
    "to", "was", "were", "will", "with", "after", "amid",
    "over", "under", "new", "says", "say", "said", "how",
    "why", "what", "when", "who", "could", "would", "should",
    "latest", "live", "update", "updates", "explained",
    "report", "reports", "according", "announces", "announced",
}

GENERIC_EVENT_WORDS = {
    "government", "country", "countries", "world", "international",
    "global", "officials", "official", "minister", "president",
    "leaders", "leader", "meeting", "talks", "news", "report",
    "reports", "crisis", "conflict", "war", "security",
    "diplomatic", "diplomacy", "relations", "grounds",
    "concerns", "intensify", "intensifies", "intensified",
}

EVENT_ACTIONS = {
    "expel", "expels", "expelled", "deport", "deports", "deported",
    "attack", "attacks", "attacked", "strike", "strikes", "struck",
    "kill", "kills", "killed", "arrest", "arrests", "arrested",
    "sign", "signs", "signed", "agree", "agrees", "agreed",
    "resume", "resumes", "resumed", "suspend", "suspends", "suspended",
    "ban", "bans", "banned", "sanction", "sanctions", "sanctioned",
    "elect", "elects", "elected", "resign", "resigns", "resigned",
    "ceasefire", "invade", "invades", "invaded", "launch", "launches",
    "launched", "postpone", "postpones", "postponed", "condemn",
    "condemns", "condemned", "urge", "urges", "urged",
}

# Variants that should be treated as the same action.
ACTION_NORMALIZATION = {
    "expels": "expel",
    "expelled": "expel",
    "deports": "deport",
    "deported": "deport",
    "attacks": "attack",
    "attacked": "attack",
    "strikes": "strike",
    "struck": "strike",
    "kills": "kill",
    "killed": "kill",
    "arrests": "arrest",
    "arrested": "arrest",
    "signs": "sign",
    "signed": "sign",
    "agrees": "agree",
    "agreed": "agree",
    "resumes": "resume",
    "resumed": "resume",
    "suspends": "suspend",
    "suspended": "suspend",
    "bans": "ban",
    "banned": "ban",
    "sanctions": "sanction",
    "sanctioned": "sanction",
    "elects": "elect",
    "elected": "elect",
    "resigns": "resign",
    "resigned": "resign",
    "invades": "invade",
    "invaded": "invade",
    "launches": "launch",
    "launched": "launch",
    "postpones": "postpone",
    "postponed": "postpone",
    "condemns": "condemn",
    "condemned": "condemn",
    "urges": "urge",
    "urged": "urge",
}


def _tokens(title: str) -> set[str]:
    normalized = normalize_text(title or "")
    return {
        token
        for token in re.findall(r"[a-z0-9]+", normalized)
        if len(token) > 1 and token not in EVENT_STOP_WORDS
    }


def _specific_tokens(title: str) -> set[str]:
    return _tokens(title) - GENERIC_EVENT_WORDS


def _normalized_actions(title: str) -> set[str]:
    actions = _tokens(title) & EVENT_ACTIONS
    return {
        ACTION_NORMALIZATION.get(action, action)
        for action in actions
    }


def _jaccard_similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0

    union = a | b
    return len(a & b) / len(union)


def _same_event(
    title_a: str,
    title_b: str,
    similarity_threshold: float,
) -> bool:
    tokens_a = _tokens(title_a)
    tokens_b = _tokens(title_b)

    if not tokens_a or not tokens_b:
        return False

    # Very similar headlines are likely reports about the same event.
    if title_similarity(title_a, title_b) >= max(
        similarity_threshold,
        0.68,
    ):
        return True

    specific_a = _specific_tokens(title_a)
    specific_b = _specific_tokens(title_b)
    shared = specific_a & specific_b

    actions_a = _normalized_actions(title_a)
    actions_b = _normalized_actions(title_b)

    # If both headlines identify an action but the actions differ,
    # do not automatically merge them.
    if actions_a and actions_b and actions_a.isdisjoint(actions_b):
        return False

    # Match stories with a shared action and several distinctive
    # terms, even if one headline contains extra location details.
    shared_actions = actions_a & actions_b

    if shared_actions and len(shared) >= 3:
        return True

    # A strong overlap of distinctive terms is also useful when
    # both headlines describe the event in slightly different ways.
    if (
        len(shared) >= 3
        and _jaccard_similarity(specific_a, specific_b) >= 0.50
    ):
        return True

    return False


def cluster_stories(
    stories: list[dict],
    similarity_threshold: float = 0.45,
) -> list[list[dict]]:
    """
    Group likely duplicate coverage of the same event.

    Input stories should be ranked first. The first story in each
    cluster is retained as the preferred representative by the selector.
    """
    clusters: list[list[dict]] = []

    for story in stories:
        title = (story.get("title") or "").strip()

        if not title:
            continue

        matching_cluster = None

        for cluster in clusters:
            representative_title = (
                cluster[0].get("title") or ""
            ).strip()

            if _same_event(
                title,
                representative_title,
                similarity_threshold,
            ):
                matching_cluster = cluster
                break

        if matching_cluster is None:
            clusters.append([story])
        else:
            matching_cluster.append(story)

    return clusters