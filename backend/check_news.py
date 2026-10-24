from app.lib.supabase import admin_supabase


def main():
    print("\n========== NEWS DATABASE DIAGNOSTIC ==========")

    categories = (
        admin_supabase
        .table("categories")
        .select("id, slug, name_en")
        .execute()
    )

    for category in categories.data or []:
        print(f"\nCATEGORY: {category['name_en']} ({category['slug']})")

        try:
            result = (
                admin_supabase
                .table("news_items")
                .select("id, title, source, published_at, category_id")
                .eq("category_id", category["id"])
                .order("published_at", desc=True)
                .limit(5)
                .execute()
            )

            stories = result.data or []
            print("STORED STORIES:", len(stories))

            for story in stories:
                print("TITLE:", story.get("title"))
                print("SOURCE:", story.get("source"))
                print("PUBLISHED:", story.get("published_at"))
                print("---")

        except Exception as error:
            print("DATABASE QUERY FAILED:", repr(error))

    print("\n========== DIAGNOSTIC COMPLETE ==========")


if __name__ == "__main__":
    main()
