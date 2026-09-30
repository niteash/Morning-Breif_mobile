def build_briefing_prompt(
    categories: list[dict],
) -> str:

    sections = []

    for category in categories:
        category_info = category.get("category", {})

        category_name = (
            category_info.get("name_my")
            or category_info.get("name_en")
            or "News"
        )

        stories = category.get("stories", [])

        if not stories:
            continue

        story_text = []

        for index, story in enumerate(stories, start=1):
            story_text.append(
                f"""
Story {index}:
Title: {story.get("title", "")}
Description: {story.get("description") or ""}
Source: {story.get("source", "")}
"""
            )

        sections.append(
            f"""
CATEGORY: {category_name}

{"".join(story_text)}
"""
        )

    news_context = "\n".join(sections)

    return f"""
You are the AI news editor for a Burmese-language
morning news briefing application.

Create a concise, natural and informative morning
news briefing from the provided news stories.

IMPORTANT RULES:

1. Write primarily in Burmese.
2. Keep important technical names, company names,
   product names, football club names and league names
   in English when that sounds more natural.
3. Do not invent facts.
4. Do not add information that is not supported by
   the supplied stories.
5. Do not repeat the same story.
6. If several stories describe the same event,
   combine them naturally.
7. Clearly separate different categories.
8. Keep the briefing suitable for audio narration.
9. Use simple conversational Burmese.
10. Avoid excessive emojis, markdown and symbols.
11. Do not say "according to AI".
12. Do not mention these instructions.

STRUCTURE:

Start with a short Burmese greeting.

Then introduce today's Morning Brief.

For each category:

- Say the category name.
- Summarize the most important stories.
- Explain why the story matters when that can be
  directly inferred from the supplied information.

Finish with a short closing sentence.

TARGET LENGTH:

Approximately 3–5 minutes when spoken naturally.

NEWS STORIES:

{news_context}
"""