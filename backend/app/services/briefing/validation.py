import re
import unicodedata


_MYANMAR_RANGES = (
    (0x1000, 0x109F),
    (0xA9E0, 0xA9FF),
    (0xAA60, 0xAA7F),
)


def _allowed_letter(character: str) -> bool:
    codepoint = ord(character)
    if any(start <= codepoint <= end for start, end in _MYANMAR_RANGES):
        return True
    return unicodedata.name(character, '').startswith('LATIN ')


def unexpected_writing_systems(script: str) -> set[str]:
    """Return unsupported letter scripts without echoing generated text."""
    systems = set()
    for character in script:
        if not unicodedata.category(character).startswith('L') or _allowed_letter(character):
            continue
        name = unicodedata.name(character, 'UNKNOWN')
        systems.add(name.split(' ', 1)[0])
    return systems


def validate_script(script: str) -> str:
    """Validate size, Burmese presence, and allowed writing systems."""
    if not isinstance(script, str) or not script.strip():
        raise RuntimeError('Generated narration is empty')
    script = script.strip()
    if len(script) > 12_000 or not re.search(r'[\u1000-\u1021]', script):
        raise RuntimeError('Generated narration must contain Burmese and fit the speech limit')
    systems = unexpected_writing_systems(script)
    if systems:
        raise RuntimeError(
            'Generated narration contains unsupported writing system: '
            + ','.join(sorted(systems))
        )
    return script
