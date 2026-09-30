from app.services.briefing.generator import (
    generate_briefing_script,
)


def main():

    prompt = """
You are a Burmese morning news assistant.

Write a very short Burmese morning briefing
about artificial intelligence.

Mention:
- AI
- Google Gemini
- software developers

Keep it under 150 words.

Do not invent specific news events.
"""

    result = generate_briefing_script(prompt)

    print("\n==============================")
    print("GEMINI TEST RESULT")
    print("==============================\n")

    print(result)


if __name__ == "__main__":
    main()