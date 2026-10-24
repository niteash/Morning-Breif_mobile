from app.services.news.relevance import (
    calculate_relevance_score,
    is_relevant,
)


TEST_CASES = [
    (
        "tech",
        "OpenAI announces a new large language model",
        "The company introduced new AI capabilities.",
        True,
    ),
    (
        "business",
        "Central bank cuts interest rates",
        "The decision could affect borrowing costs and financial markets.",
        True,
    ),
    (
        "football",
        "UEFA Champions League match ends in dramatic victory",
        "The winning club advances to the next round.",
        True,
    ),
    (
        "myanmar",
        "Flooding affects communities in Mandalay",
        "Heavy rainfall has affected local communities.",
        True,
    ),
    (
        "tech",
        "Local restaurant announces a new menu",
        "The restaurant will open its new dining area next week.",
        False,
    ),
    (
        "football",
        "NFL quarterback signs a new contract",
        "The American football player agreed to a new deal.",
        False,
    ),
    (
        "business",
        "Football club wins a dramatic final",
        "The team celebrates its championship victory.",
        False,
    ),
    (
        "tech",
        "Government announces a new diplomatic agreement",
        "International leaders met to discuss foreign policy.",
        False,
    ),
]


def main():
    failures = 0

    for category, title, description, expected in TEST_CASES:
        actual = is_relevant(category, title, description)
        score = calculate_relevance_score(
            category, title, description
        )

        passed = actual == expected

        print(
            f"{'PASS' if passed else 'FAIL'} | "
            f"category={category:8} | "
            f"relevant={actual!s:5} | "
            f"expected={expected!s:5} | "
            f"score={score:2} | "
            f"title={title}"
        )

        if not passed:
            failures += 1

    print(f"\nResults: {len(TEST_CASES) - failures}/{len(TEST_CASES)} passed")

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()


