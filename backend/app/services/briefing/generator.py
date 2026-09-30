from google import genai

from app.config import GEMINI_API_KEY

client = genai.Client(
    api_key=GEMINI_API_KEY
)


MODEL_NAME = "gemini-2.5-flash"


def generate_briefing_script(
    prompt: str,
) -> str:

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
    )

    if not response.text:
        raise RuntimeError(
            "Gemini returned an empty response"
        )

    return response.text.strip()