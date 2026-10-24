import time

from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY


client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options=types.HttpOptions(
        timeout=90_000,
    ),
)

PRIMARY_MODEL = "gemini-2.5-flash"
FALLBACK_MODEL = "gemini-2.5-flash-lite"


def build_news_text(categories: list[dict]) -> str:
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

        news_sections.append(f"\nCATEGORY: {category_name}")

        for index, story in enumerate(stories, start=1):
            title = (story.get("title") or "").strip()
            description = (story.get("description") or "").strip()
            source = (story.get("source") or "").strip()
            published_at = story.get("published_at") or ""
            url = story.get("url") or ""

            if not title:
                continue

            news_sections.append(
                f"""
STORY {index}
Title: {title}
Description: {description}
Source: {source}
Published: {published_at}
URL: {url}
"""
            )

    return "\n".join(news_sections)


def build_prompt(
    categories: list[dict],
    regeneration_id: str | None = None,
) -> str:
    news_text = build_news_text(categories)

    regeneration_instruction = ""

    if regeneration_id:
        regeneration_instruction = f"""
REGENERATION REQUEST
ID: {regeneration_id}

Create a fresh narration using only the supplied stories.
Do not invent additional facts or stories.
"""

    return f"""
You are the editorial AI for a Burmese-language
morning news briefing application.

Create a concise, natural Burmese audio-news script.

{regeneration_instruction}

STRICT EDITORIAL RULES

1. Use only the supplied news articles.
2. Never invent news, events, statistics, quotations, or results.
3. Never imply that a general introduction is a real news report.
4. Do not add categories that have no supplied stories.
5. Do not repeat stories.
6. Keep factual claims consistent with the supplied articles.
7. Mention the source when appropriate.
8. Write naturally in Burmese.
9. English technical terms may remain in English.
10. Do not read URLs aloud.

Start with:
မင်္ဂလာနံနက်ခင်းပါရှင်။

Summarize the actual supplied news, grouped by category.
End with a short Burmese closing.

SUPPLIED NEWS ARTICLES:

{news_text}
"""


def _generate_with_model(
    model_name: str,
    prompt: str,
) -> str:
    started = time.perf_counter()

    print(f"[Gemini] Starting model: {model_name}")
    print(f"[Gemini] Prompt length: {len(prompt)} characters")

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True,
            ),
        ),
    )

    elapsed = time.perf_counter() - started
    text = response.text

    print(f"[Gemini] Model completed in {elapsed:.2f}s")

    if not text or not text.strip():
        raise RuntimeError(
            f"{model_name} returned an empty response"
        )

    print(f"[Gemini] Generated {len(text)} characters")

    return text.strip()


def generate_briefing_script(
    categories: list[dict],
    regeneration_id: str | None = None,
) -> str:
    news_text = build_news_text(categories)

    if not news_text.strip():
        raise ValueError(
            "Cannot generate a news briefing: "
            "no usable news stories were found."
        )

    prompt = build_prompt(
        categories=categories,
        regeneration_id=regeneration_id,
    )

    try:
        return _generate_with_model(
            model_name=PRIMARY_MODEL,
            prompt=prompt,
        )

    except Exception as primary_error:
        print(
            f"[Gemini] Primary model failed: "
            f"{type(primary_error).__name__}: {primary_error}"
        )

    print("[Gemini] Trying fallback model")

    try:
        return _generate_with_model(
            model_name=FALLBACK_MODEL,
            prompt=prompt,
        )

    except Exception as fallback_error:
        print(
            f"[Gemini] Fallback model failed: "
            f"{type(fallback_error).__name__}: {fallback_error}"
        )

        raise RuntimeError(
            "Gemini briefing generation failed after "
            "primary and fallback attempts"
        ) from fallback_error