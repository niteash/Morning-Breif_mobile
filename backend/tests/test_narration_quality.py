import json
from unittest.mock import Mock

import pytest

from app.services.ai import gemini
from app.services.briefing import pipeline
from app.services.briefing.quality import (
    assess_source_material,
    estimate_narration_seconds,
    evaluate_narration,
    target_character_range,
)
from app.services.briefing.validation import validate_script
from app.services.tts import azure


def categories(description='A detailed source excerpt. ' * 20, story_count=9):
    return [{
        'category': {'id': 'category', 'name_my': 'စီးပွားရေး', 'name_en': 'Business'},
        'stories': [{
            'id': f'story-{index}',
            'title': f'Company report {index}',
            'description': description,
            'source': 'Approved Publisher',
            'url': f'https://example.org/{index}',
        } for index in range(story_count)],
    }]


def test_november_25_length_calibration_estimates_observed_duration():
    assert estimate_narration_seconds('မ' * 2750) == 198
    minimum, maximum = target_character_range(7)
    assert minimum > 4900
    assert maximum > minimum


def test_november_25_source_snapshot_reports_seven_minute_shortfall():
    descriptions = [
        'South Korea draft bill favors bank-led stablecoin issuance but allows fintech and technology companies to become the largest individual shareholders.',
        'The Bitcoin miner sold 2,102 BTC while it produced just 1,708 BTC in the September quarter.',
        'The Ethereum Foundation doubled its protocol security team and prioritized a cryptographic overhaul as advances in AI threaten security assumptions.',
        'Bitcoin slipped below $60,000 as realized losses increased. The sell-off resembles past market bottoms, but another drop to $53,200 could occur.',
        'The asset manager warned that the downturn could persist amid weak demand and forecast an uneven recovery.',
        'A Myanmar delegation attended the International Municipal Forum 2026 in Russia.',
        'Myanmar was selected as Official Guest Country for Coffee Expo Seoul 2027.',
        'More than 120 people were arrested in Mayangone and Yankin townships.',
        'Nationalists and lawmakers are stirring anti-Muslim fears and reviving language that preceded violence.',
    ]
    data = categories(story_count=0)
    data[0]['stories'] = [{
        'id': f'november-25-{index}', 'title': f'Saved story {index}',
        'description': description, 'source': 'Saved publisher',
        'url': f'https://example.org/saved/{index}',
    } for index, description in enumerate(descriptions)]
    assessment = assess_source_material(data, 7)
    assert assessment['story_count'] == 9
    assert assessment['estimated_supported_seconds'] < 357
    assert assessment['sufficient_for_target'] is False


def test_short_source_material_is_reported_instead_of_padded():
    data = categories(description='Short excerpt.', story_count=9)
    source = assess_source_material(data, 7)
    assert source['sufficient_for_target'] is False
    quality = evaluate_narration('မြန်မာသတင်း။' * 30, data, 7)
    assert quality['status'] == 'source_material_insufficient'
    prompt = gemini.build_prompt(data, target_minutes=7)
    assert 'SOURCE-LENGTH LIMIT' in prompt
    assert 'Do not pad, repeat, infer' in prompt


def test_rich_sources_require_a_supported_length_before_tts(monkeypatch):
    data = categories()
    assert assess_source_material(data, 7)['sufficient_for_target'] is True
    monkeypatch.setenv('BRIEFING_SOURCES_ENABLED', 'false')
    monkeypatch.setattr(pipeline, 'generate_briefing_script', Mock(return_value='မြန်မာသတင်း။'))
    speech = Mock()
    monkeypatch.setattr(pipeline, 'generate_speech', speech)
    with pytest.raises(pipeline.PipelineStageError) as raised:
        pipeline.generate_combined_audio(
            'e726b864-c879-4b8f-9ac1-c5cb73ae8a58', '2026-11-25', data,
        )
    assert raised.value.stage == 'narration_quality'
    speech.assert_not_called()


def test_language_validation_rejects_arabic_but_allows_burmese_and_source_names():
    assert validate_script('မြန်မာသတင်းတွင် Bitcoin နှင့် CleanSpark ပါဝင်သည်။')
    with pytest.raises(RuntimeError, match='ARABIC'):
        validate_script('မြန်မာသတင်းတွင် انفرادي စာလုံး ပါဝင်သည်။')


def test_structured_grounding_keeps_one_narration_per_story(monkeypatch):
    data = categories(description='Supported excerpt.', story_count=2)
    response = {
        'title': 'နေ့သစ်',
        'opening': 'မင်္ဂလာနံနက်ခင်းပါရှင်။',
        'category_introductions': ['စီးပွားရေးသတင်းများကို ဆက်လက်တင်ပြပါမယ်။'],
        'story_narrations': ['ပထမ မြန်မာသတင်း။', 'ဒုတိယ မြန်မာသတင်း။'],
        'closing': 'နားဆင်ပေးလို့ ကျေးဇူးတင်ပါတယ်ရှင်။',
    }
    monkeypatch.setattr(gemini, '_generate_with_model', Mock(return_value=json.dumps(response)))
    result = gemini.generate_grounded_briefing(data, '2026-11-25')
    section = result['sections'][0]
    assert [item['source_id'] for item in section['story_narrations']] == [
        'story-0', 'story-1',
    ]
    assert all(item['narration'] in section['narration']
               for item in section['story_narrations'])


@pytest.mark.parametrize(('text', 'expected'), [
    ('ဒေါ်လာ ၆၀,၀၀၀', 'အမေရိကန်ဒေါ်လာ ခြောက်သောင်း'),
    ('$53,200', 'အမေရိကန်ဒေါ်လာ ငါးသောင်းသုံးထောင်နှစ်ရာ'),
    ('၂၀၂၆ ခုနှစ်', 'နှစ်ထောင်နှစ်ဆယ်ခြောက် ခုနှစ်'),
    ('12.5%', 'ဆယ့်နှစ် ဒသမ ငါး ရာခိုင်နှုန်း'),
    ('Bitcoin BTC CleanSpark FTX', 'ဘစ်ကွိုင် ဘီ တီ စီ ကလင်း စပါ့ခ် အက်ဖ် တီ အိတ်စ်'),
])
def test_burmese_tts_normalization_for_stage6_terms(text, expected, monkeypatch):
    monkeypatch.setattr(azure.admin_supabase, 'table', Mock(side_effect=RuntimeError('offline')))
    assert expected in azure.build_ssml(text)
