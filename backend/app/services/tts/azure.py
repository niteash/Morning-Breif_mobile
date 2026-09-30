import html
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()


AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")
AZURE_SPEECH_VOICE = os.getenv(
    "AZURE_SPEECH_VOICE",
    "my-MM-NilarNeural",
)


def generate_speech(
    text: str,
    output_path: str,
) -> str:

    if not AZURE_SPEECH_KEY:
        raise RuntimeError(
            "AZURE_SPEECH_KEY is not configured"
        )

    if not AZURE_SPEECH_REGION:
        raise RuntimeError(
            "AZURE_SPEECH_REGION is not configured"
        )

    if not AZURE_SPEECH_VOICE:
        raise RuntimeError(
            "AZURE_SPEECH_VOICE is not configured"
        )

    endpoint = (
        f"https://{AZURE_SPEECH_REGION}"
        ".tts.speech.microsoft.com"
        "/cognitiveservices/v1"
    )

    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": (
            "audio-24khz-96kbitrate-mono-mp3"
        ),
        "User-Agent": "MorningBrief",
    }

    safe_text = html.escape(text)

    ssml = f"""<?xml version="1.0" encoding="UTF-8"?>
<speak
    version="1.0"
    xmlns="http://www.w3.org/2001/10/synthesis"
    xml:lang="my-MM"
>
    <voice name="{AZURE_SPEECH_VOICE}">
        {safe_text}
    </voice>
</speak>
"""

    response = requests.post(
        endpoint,
        headers=headers,
        data=ssml.encode("utf-8"),
        timeout=60,
    )

    if response.status_code != 200:
        raise RuntimeError(
            "Azure Speech request failed: "
            f"{response.status_code} "
            f"{response.text}"
        )

    output = Path(output_path)
    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_bytes(response.content)

    return str(output)