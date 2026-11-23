import html
import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv
from app.lib.supabase import admin_supabase

load_dotenv()


AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")
AZURE_SPEECH_VOICE = os.getenv(
    "AZURE_SPEECH_VOICE",
    "my-MM-NilarNeural",
) or "my-MM-NilarNeural"
SUPPORTED_BURMESE_VOICES = {'my-MM-NilarNeural'}

ENGLISH_PRONUNCIATIONS = {
    'OpenAI': 'အိုးပင်း အေ အိုင်',
    'ChatGPT': 'ချက် ဂျီ ပီ တီ',
    'Microsoft': 'မိုက်ခရိုဆော့ဖ်',
    'Google': 'ဂူဂယ်',
    'YouTube': 'ယူကျု',
    'Facebook': 'ဖေ့စ်ဘွတ်ခ်',
    'Instagram': 'အင်စတာဂရမ်',
    'WhatsApp': 'ဝေါ့စ်အက်ပ်',
    'Apple': 'အက်ပဲလ်',
    'iPhone': 'အိုင်ဖုန်း',
    'Android': 'အန်းဒရွိုက်',
    'NVIDIA': 'အင်ဗီဒီယာ',
    'Tesla': 'တက်စလာ',
    'Amazon': 'အမေဇွန်',
    'Netflix': 'နက်ဖလစ်',
    'AI': 'အေ အိုင်',
}
LETTER_PRONUNCIATIONS = {
    'A': 'အေ', 'B': 'ဘီ', 'C': 'စီ', 'D': 'ဒီ', 'E': 'အီး', 'F': 'အက်ဖ်',
    'G': 'ဂျီ', 'H': 'အိတ်ချ်', 'I': 'အိုင်', 'J': 'ဂျေ', 'K': 'ကေ',
    'L': 'အယ်လ်', 'M': 'အမ်', 'N': 'အန်', 'O': 'အို', 'P': 'ပီ',
    'Q': 'ကျူ', 'R': 'အာ', 'S': 'အက်စ်', 'T': 'တီ', 'U': 'ယူ',
    'V': 'ဗီ', 'W': 'ဒဗလျူ', 'X': 'အိတ်စ်', 'Y': 'ဝိုင်', 'Z': 'ဇက်',
}
PRONUNCIATIONS_BY_CASEFOLD = {
    term.casefold(): pronunciation for term, pronunciation in ENGLISH_PRONUNCIATIONS.items()
}
ENGLISH_TERM = re.compile(
    r'(?<![A-Za-z])(?:'
    + '|'.join(re.escape(term) for term in sorted(ENGLISH_PRONUNCIATIONS, key=len, reverse=True))
    + r')(?![A-Za-z])',
    re.IGNORECASE,
)
LATIN_ACRONYM = re.compile(r'(?<![A-Za-z])[A-Z]{2,6}(?![A-Za-z])')


def _speech_pronunciation(value: str) -> str:
    """Normalize common Latin terms for Nilar without switching speakers."""
    try:
        rows = (admin_supabase.table('pronunciation_lexicon').select('term,spoken_form')
                .eq('active', True).eq('locale', 'my-MM').limit(200).execute().data or [])
        for row in sorted(rows, key=lambda item: len(item.get('term') or ''), reverse=True):
            term, spoken = (row.get('term') or '').strip(), (row.get('spoken_form') or '').strip()
            if term and spoken:
                value = re.sub(rf'(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])', spoken, value, flags=re.IGNORECASE)
    except Exception:
        # A missing/new lexicon must never block speech generation.
        pass
    value = ENGLISH_TERM.sub(
        lambda match: PRONUNCIATIONS_BY_CASEFOLD[match.group(0).casefold()],
        value,
    )
    return LATIN_ACRONYM.sub(
        lambda match: ' '.join(LETTER_PRONUNCIATIONS[letter] for letter in match.group(0)),
        value,
    )


def _escaped_paragraphs(value: str) -> list[str]:
    return [html.escape(part.strip()) for part in re.split(r'\n\s*\n+', value) if part.strip()]


def build_ssml(text: str) -> str:
    """Use one Burmese female voice for the entire bilingual narration."""
    paragraphs = _escaped_paragraphs(_speech_pronunciation(text))
    narration = '<break time="420ms"/>'.join(paragraphs)
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="my-MM">
    <voice name="{AZURE_SPEECH_VOICE}"><prosody rate="-2%" pitch="+1%">{narration}</prosody></voice>
</speak>'''


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

    if not re.fullmatch(r'[a-z0-9-]+', AZURE_SPEECH_REGION):
        raise RuntimeError('Invalid Azure region')
    if AZURE_SPEECH_VOICE not in SUPPORTED_BURMESE_VOICES:
        raise RuntimeError('A supported Burmese voice is required')

    endpoint = (
        f"https://{AZURE_SPEECH_REGION}"
        ".tts.speech.microsoft.com"
        "/cognitiveservices/v1"
    )

    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": (
            "audio-24khz-48kbitrate-mono-mp3"
        ),
        "User-Agent": "MorningBrief",
    }

    ssml = build_ssml(text)

    try:
        response = requests.post(
            endpoint, headers=headers, data=ssml.encode("utf-8"),
            timeout=60, allow_redirects=False,
        )
    except requests.RequestException:
        raise RuntimeError('Azure Speech transport failure; no automatic retry') from None

    if response.status_code != 200:
        raise RuntimeError(
            "Azure Speech request failed: "
            f"HTTP {response.status_code}"
        )

    output = Path(output_path)
    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_bytes(response.content)

    return str(output)
