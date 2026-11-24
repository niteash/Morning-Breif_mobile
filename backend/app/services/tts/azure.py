import html
import os
import re
from pathlib import Path
import unicodedata

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



def _burmese_integer_under_100000(number: int) -> str:
    """Convert 0–99,999 to Burmese spoken-number text."""
    if not 0 <= number <= 99999:
        raise ValueError("Number outside supported range")

    if number < 10000:
        return _burmese_integer_under_10000(number)

    ten_thousands, remainder = divmod(number, 10000)

    spoken = BURMESE_DIGITS[ten_thousands] + 'သောင်း'
    if remainder:
        spoken += _burmese_integer_under_10000(remainder)

    return spoken



MMK_AMOUNT = re.compile(
    r'(?<![\w\d])'
    r'([0-9၀-၉]+(?:,[0-9၀-၉]{3})*)'
    r'\s*(ကျပ်|MMK)'
    r'(?![A-Za-z0-9၀-၉\u1000-\u109F])',
    re.IGNORECASE,
)



def _normalize_mmk_amounts(text: str) -> str:
    """Normalize well-formed, whole-kyat amounts for Burmese TTS."""

    def replace(match: re.Match) -> str:
        original = match.group(0)
        digits = match.group(1)
        groups = digits.split(',')

        # Reject malformed digit grouping.
        if len(groups) > 1 and (
            not 1 <= len(groups[0]) <= 3
            or any(len(group) != 3 for group in groups[1:])
        ):
            return original

        try:
            amount = int(''.join(
                str(unicodedata.digit(char))
                for char in digits
                if char != ','
            ))
        except (TypeError, ValueError):
            return original

        if not 0 <= amount <= 99999:
            return original

        spoken = _burmese_integer_under_100000(amount)
        return spoken + ' ကျပ်'

    return MMK_AMOUNT.sub(replace, text)


PERCENTAGE_AMOUNT = re.compile(
    r'(?<![\w,.$])'
    r'([0-9၀-၉]+)'
    r'(?:\.([0-9၀-၉]{1,2}))?'
    r'%'
    r'(?![\w.,%])'
)


def _spoken_percentage_integer(number: int) -> str:
    """Natural Burmese pronunciation for supported integers."""
    if 11 <= number <= 19:
        return 'တစ်ဆယ့်' + BURMESE_DIGITS[number - 10]

    return _burmese_integer_under_10000(number)


def _normalize_percentages(text: str) -> str:
    """Convert supported percentages to Burmese speech text."""

    def replace(match: re.Match) -> str:
        original = match.group(0)

        try:
            whole = int(''.join(
                str(unicodedata.digit(char))
                for char in match.group(1)
            ))

            if whole > 9999:
                return original

            spoken = _spoken_percentage_integer(whole)

            fraction = match.group(2)

            if fraction is not None:
                decimal_digits = [
                    BURMESE_DIGITS[unicodedata.digit(char)]
                    if unicodedata.digit(char) != 0
                    else 'သုည'
                    for char in fraction
                ]

                spoken += ' ဒသမ ' + ' '.join(decimal_digits)

            return spoken + ' ရာခိုင်နှုန်း'

        except (TypeError, ValueError):
            return original

    return PERCENTAGE_AMOUNT.sub(replace, text)



def _speech_pronunciation(value: str) -> str:
    """Normalize currency and Latin terms for Burmese speech."""

    # Currency must be processed before acronym conversion.
    value = _normalize_mmk_amounts(value)
    value = _normalize_usd_amounts(value)
    value = _normalize_percentages(value)
    try:
        rows = (
            admin_supabase.table('pronunciation_lexicon')
            .select('term,spoken_form')
            .eq('active', True)
            .eq('locale', 'my-MM')
            .limit(200)
            .execute()
            .data or []
        )

        for row in sorted(
            rows,
            key=lambda item: len(item.get('term') or ''),
            reverse=True,
        ):
            term = (row.get('term') or '').strip()
            spoken = (row.get('spoken_form') or '').strip()

            if term and spoken:
                value = re.sub(
                    rf'(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])',
                    spoken,
                    value,
                    flags=re.IGNORECASE,
                )

    except Exception:
        # Missing lexicon must not block speech generation.
        pass

    value = ENGLISH_TERM.sub(
        lambda match: PRONUNCIATIONS_BY_CASEFOLD[
            match.group(0).casefold()
        ],
        value,
    )

    value = LATIN_ACRONYM.sub(
        lambda match: ' '.join(
            LETTER_PRONUNCIATIONS[letter]
            for letter in match.group(0)
        ),
        value,
    )

    return value

BURMESE_DIGITS = (
    '', 'တစ်', 'နှစ်', 'သုံး', 'လေး',
    'ငါး', 'ခြောက်', 'ခုနစ်', 'ရှစ်', 'ကိုး',
)


def _burmese_integer_under_10000(number: int) -> str:
    """Convert an integer from 0 to 9999 to spoken Burmese."""
    if not 0 <= number <= 9999:
        raise ValueError("Number outside supported range")

    if number == 0:
        return 'သုည'

    parts = []

    for place, label in (
        (1000, 'ထောင်'),
        (100, 'ရာ'),
        (10, 'ဆယ်'),
    ):
        digit, number = divmod(number, place)

        if digit:
            if place == 10 and digit == 1:
                parts.append('ဆယ်')
            else:
                parts.append(BURMESE_DIGITS[digit] + label)

    if number:
        parts.append(BURMESE_DIGITS[number])

    return ''.join(parts)


USD_AMOUNT = re.compile(
    r'(?<![\w$])\$\s*'
    r'([1-9]\d{0,3}|[1-9]\d{0,2},\d{3}|0)'
    r'(?![\d.,])'
)



def _normalize_usd_amounts(text: str) -> str:
    """Convert supported whole-dollar amounts without altering others."""

    def replace(match: re.Match) -> str:
        original = match.group(0)
        amount = int(match.group(1).replace(',', ''))

        # Unsupported values must not crash audio generation.
        if not 0 <= amount <= 9999:
            return original

        spoken = _burmese_integer_under_10000(amount)

        return 'အမေရိကန်ဒေါ်လာ ' + spoken

    return USD_AMOUNT.sub(replace, text)

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
