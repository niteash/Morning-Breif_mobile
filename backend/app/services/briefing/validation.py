import re

def validate_script(script: str) -> str:
    """Basic language/size validation, not factual or pronunciation verification."""
    if not isinstance(script, str) or not script.strip():
        raise RuntimeError('Generated narration is empty')
    script = script.strip()
    if len(script) > 12_000 or not re.search(r'[\u1000-\u1021]', script):
        raise RuntimeError('Generated narration must contain Burmese and fit the speech limit')
    return script
