"""Small, transparent ranking bonuses for explicit user interests."""
import re

CRYPTO_TERMS = {
    'BTC': ('bitcoin', 'btc'), 'ETH': ('ethereum', 'ether', 'eth'),
    'SOL': ('solana', 'sol'), 'XRP': ('xrp', 'ripple'), 'BNB': ('bnb', 'binance coin'),
    'DOGE': ('dogecoin', 'doge'), 'ADA': ('cardano', 'ada'),
    'AVAX': ('avalanche', 'avax'), 'DOT': ('polkadot', 'dot'), 'LINK': ('chainlink', 'link'),
}


def interest_bonus(story: dict, category_slug: str, profile: dict | None) -> int:
    """Boost a matching story; never exclude other current stories."""
    if not profile:
        return 0
    text = f"{story.get('title') or ''} {story.get('description') or ''}".casefold()
    terms: tuple[str, ...] = ()
    if category_slug == 'horoscope' and profile.get('horoscope_sign'):
        terms = (str(profile['horoscope_sign']).casefold(),)
    elif category_slug == 'crypto':
        symbols = profile.get('crypto_watchlist') or []
        terms = tuple(term for symbol in symbols for term in CRYPTO_TERMS.get(str(symbol).upper(), ()))
    return 16 if any(re.search(rf'(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])', text) for term in terms) else 0
