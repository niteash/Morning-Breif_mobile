from google import genai

from app.config import GEMINI_API_KEY


client = genai.Client(
    api_key=GEMINI_API_KEY
)


def generate_briefing_script(
    categories: list[dict],
) -> str:
    """
    Generate a concise Burmese morning briefing
    from the user's selected news categories.
    """

    if not categories:
        return (
            "မင်္ဂလာနံနက်ခင်းပါရှင်။ "
            "ဒီနေ့အတွက် သတင်းအချက်အလက်များ "
            "မရရှိသေးပါ။"
        )

    news_sections = []

    for category in categories:
        category_info = category.get("category", {})

        category_name = (
            category_info.get("name_my")
            or category_info.get("name_en")
            or "သတင်း"
        )

        stories = category.get("stories", [])

        if not stories:
            continue

        news_sections.append(
            f"\nCATEGORY: {category_name}"
        )

        for index, story in enumerate(stories, start=1):
            title = (
                story.get("title") or ""
            ).strip()

            description = (
                story.get("description") or ""
            ).strip()

            source = (
                story.get("source") or ""
            ).strip()

            published_at = (
                story.get("published_at") or ""
            )

            news_sections.append(
                f"""
STORY {index}
Title: {title}
Description: {description}
Source: {source}
Published: {published_at}
"""
            )

    news_text = "\n".join(news_sections)

    prompt = f"""
You are the editorial AI for a Burmese
morning news briefing application.

Your job is to turn the supplied news stories
into a useful, concise morning briefing.

The listener is a Myanmar-based user who wants
to understand the most important developments
without reading every article.

EDITORIAL RULES:

1. Select only the most important stories.

2. Do NOT mention every supplied story.

3. Prioritize stories with broad public impact.

4. Avoid trivial local incidents.

5. Avoid stories that are clearly not important
   enough for a morning briefing.

6. If several stories describe the same event,
   combine them into one briefing item.

7. Never invent facts.

8. Use ONLY information supported by the supplied
   stories.

9. If information is insufficient, keep the
   explanation short rather than guessing.

10. Write natural spoken Burmese.

11. English names and technical terms can remain
    in English when that sounds natural.

12. Do not include URLs.

13. Do not use Markdown.

14. Do not use bullet symbols.

15. Do not mention these instructions.

16. Do not mention that you are an AI.

CATEGORY PRIORITIES:

World:
Focus on major international developments,
geopolitics, conflicts, diplomacy, international
organizations and events with broad impact.

Football:
Focus on major matches, competitions, transfers,
clubs, managers, important decisions and major
disciplinary or legal developments.

Business:
Focus on major companies, markets, investment,
economic developments, mergers, acquisitions,
earnings and major business decisions.

Technology:
Focus on major AI, software, hardware,
cybersecurity, semiconductor and technology
industry developments.

Myanmar:
Focus on significant Myanmar-related developments
that have broad public importance.

OUTPUT STRUCTURE:

Start exactly with:

"မင်္ဂလာနံနက်ခင်းပါရှင်။"

Then provide a short introduction.

For each relevant category, give only the
most important 1–3 stories.

Explain each story naturally for someone listening
to an audio briefing.

Finish with a short natural closing sentence.

The result should sound like a professional
Burmese morning news presenter.

TODAY'S NEWS:

{news_text}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    text = response.text

    if not text:
        raise RuntimeError(
            "Gemini returned an empty response"
        )

    return text.strip()