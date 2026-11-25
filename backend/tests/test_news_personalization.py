from app.services.news.personalization import interest_bonus


def test_crypto_watchlist_boosts_matching_story_without_filtering_others():
    profile = {'crypto_watchlist': ['BTC', 'ETH']}
    assert interest_bonus({'title': 'Bitcoin rises after ETF inflows'}, 'crypto', profile) == 16
    assert interest_bonus({'title': 'Solana developers announce update'}, 'crypto', profile) == 0


def test_horoscope_sign_match_uses_word_boundaries():
    profile = {'horoscope_sign': 'leo'}
    assert interest_bonus({'title': 'Leo daily horoscope'}, 'horoscope', profile) == 16
    assert interest_bonus({'title': 'Napoleon exhibition opens'}, 'horoscope', profile) == 0


def test_interest_does_not_affect_unrelated_category():
    profile = {'horoscope_sign': 'aries', 'crypto_watchlist': ['BTC']}
    assert interest_bonus({'title': 'Bitcoin and Aries'}, 'technology', profile) == 0
