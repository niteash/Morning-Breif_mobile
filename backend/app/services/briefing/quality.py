"""Offline narration-depth and source-sufficiency assessment.

These estimates are intentionally conservative. They prevent a duration target
from becoming permission to repeat or invent facts; the encoded MP3 remains the
only authoritative duration measurement.
"""
from __future__ import annotations

import math
import re


# Calibrated from the 2026-11-25 staging artifact: 2,750 characters produced
# 198.36 seconds with the configured my-MM voice and prosody (13.86 chars/sec).
BURMESE_TTS_CHARACTERS_PER_SECOND = 13.86
MINIMUM_TARGET_RATIO = 0.85
OPENING_AND_TRANSITIONS_SECONDS = 18
MAX_SUPPORTED_SECONDS_PER_STORY = 45


def estimate_narration_seconds(script: str) -> int:
    """Estimate speech length without calling a TTS provider."""
    if not isinstance(script, str) or not script.strip():
        return 0
    return max(1, round(len(script.strip()) / BURMESE_TTS_CHARACTERS_PER_SECOND))


def target_character_range(target_minutes: int) -> tuple[int, int]:
    if not 1 <= target_minutes <= 30:
        raise ValueError('Target minutes must be between 1 and 30')
    target = target_minutes * 60 * BURMESE_TTS_CHARACTERS_PER_SECOND
    return math.ceil(target * MINIMUM_TARGET_RATIO), math.ceil(target * 1.08)


def _usable_excerpt(value: object) -> str:
    if not isinstance(value, str):
        return ''
    cleaned = re.sub(r'\s+', ' ', value).strip()
    return '' if cleaned.casefold() in {'comments', 'comment', 'read more'} else cleaned


def assess_source_material(categories: list[dict], target_minutes: int) -> dict:
    """Estimate how much narration the supplied excerpts can safely support."""
    stories = [story for group in categories for story in group.get('stories', [])
               if _usable_excerpt(story.get('title'))]
    evidence_characters = 0
    headline_only = 0
    short_sources = 0
    supported_seconds = OPENING_AND_TRANSITIONS_SECONDS if stories else 0

    for story in stories:
        excerpts = [_usable_excerpt(story.get('description'))]
        excerpts.extend(_usable_excerpt(item.get('description'))
                        for item in story.get('supporting_sources', []))
        evidence = ' '.join(item for item in excerpts if item)
        evidence_characters += len(evidence)
        if not evidence:
            headline_only += 1
        elif len(evidence) < 120:
            short_sources += 1
        # A headline gets only a few seconds. Rich excerpts may support up to
        # roughly 45 seconds, but never an unlimited expansion.
        supported_seconds += min(
            MAX_SUPPORTED_SECONDS_PER_STORY,
            6 + round(len(evidence) / 8),
        )

    target_seconds = target_minutes * 60
    minimum_seconds = math.ceil(target_seconds * MINIMUM_TARGET_RATIO)
    estimated_supported_seconds = min(target_seconds, supported_seconds)
    return {
        'target_seconds': target_seconds,
        'minimum_acceptable_seconds': minimum_seconds,
        'story_count': len(stories),
        'evidence_characters': evidence_characters,
        'headline_only_story_count': headline_only,
        'short_source_story_count': short_sources,
        'estimated_supported_seconds': estimated_supported_seconds,
        'sufficient_for_target': estimated_supported_seconds >= minimum_seconds,
    }


def evaluate_narration(script: str, categories: list[dict], target_minutes: int) -> dict:
    source = assess_source_material(categories, target_minutes)
    estimate = estimate_narration_seconds(script)
    if estimate >= source['minimum_acceptable_seconds']:
        status = 'target_estimate_met'
    elif not source['sufficient_for_target']:
        status = 'source_material_insufficient'
    else:
        status = 'narration_below_supported_target'
    return {
        **source,
        'estimated_narration_seconds': estimate,
        'status': status,
        'authoritative_duration': 'measure_encoded_audio',
    }
