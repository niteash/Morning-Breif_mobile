from app.services.news.cleanup import cleanup_category


CATEGORIES = [
    "tech",
    "business",
    "football",
    "world",
    "myanmar",
]


def main():
    print("\n==============================")
    print("NEWS DATABASE CLEANUP")
    print("==============================\n")

    for category in CATEGORIES:

        try:
            result = cleanup_category(
                category
            )

            print(
                f"{category}: "
                f"checked={result['total_checked']} "
                f"kept={result['kept']} "
                f"deleted={result['deleted']}"
            )

        except Exception as error:

            print(
                f"{category}: ERROR"
            )

            print(error)

    print(
        "\nCleanup completed."
    )


if __name__ == "__main__":
    main()