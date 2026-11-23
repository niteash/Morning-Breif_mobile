from pathlib import Path
from unittest.mock import Mock

import pytest

from app.services.briefing import pipeline
from app.services.tts.duration import audio_duration_seconds
from app.services.ai import gemini


def mp3_bytes():
    # Valid MPEG-1 Layer III headers, 128 kbps, 44.1 kHz; silent payload fixture.
    return (bytes.fromhex("fffb9064") + bytes(413)) * 100


def test_mp3_duration_from_encoded_frames(tmp_path):
    path = tmp_path / "fixture.mp3"
    path.write_bytes(mp3_bytes())
    assert audio_duration_seconds(str(path)) == 3


@pytest.mark.parametrize("upload_fails", [False, True])
def test_combined_audio_and_cleanup(monkeypatch, upload_fails):
    categories = [
        {"category": {"slug": "tech"}, "stories": [{"title": "Technology story"}]},
        {"category": {"slug": "world"}, "stories": [{"title": "World story"}]},
    ]
    generate = Mock(return_value=" မြန်မာသတင်း ")
    monkeypatch.setattr(pipeline, "generate_briefing_script", generate)
    paths = []
    def speech(script, path):
        assert script == "မြန်မာသတင်း"
        paths.append(path)
        Path(path).write_bytes(mp3_bytes())
    monkeypatch.setattr(pipeline, "generate_speech", speech)
    upload = Mock(side_effect=RuntimeError("upload unavailable") if upload_fails else None)
    monkeypatch.setattr(pipeline, "upload_briefing_audio", upload)
    if upload_fails:
        with pytest.raises(pipeline.PipelineStageError) as raised:
            pipeline.generate_combined_audio("e726b864-c879-4b8f-9ac1-c5cb73ae8a58", "2026-11-08", categories)
        assert raised.value.stage == "storage_upload"
        assert raised.value.error_type == "RuntimeError"
    else:
        result = pipeline.generate_combined_audio("e726b864-c879-4b8f-9ac1-c5cb73ae8a58", "2026-11-08", categories)
        assert result["duration_seconds"] == 3
        assert result["audio_url"].startswith("e726b864-c879-4b8f-9ac1-c5cb73ae8a58/2026-11-08/")
        assert result["script"] == "မြန်မာသတင်း"
    generate.assert_called_once_with(categories, regeneration_id=None)
    upload.assert_called_once()
    assert len(paths) == 1
    assert not Path(paths[0]).exists()


def test_no_news_never_generates(monkeypatch):
    generate = Mock()
    monkeypatch.setattr(pipeline, "generate_briefing_script", generate)
    with pytest.raises(ValueError):
        pipeline.generate_combined_audio("e726b864-c879-4b8f-9ac1-c5cb73ae8a58", "2026-11-08", [])
    generate.assert_not_called()


def test_prompt_bounds_large_articles_without_dropping_selected_stories():
    categories = [{
        "category": {"name_en": "World"},
        "stories": [
            {
                "title": f"Selected story {index}",
                "description": "x" * 10_000,
                "supporting_sources": [{"title": "Supporting", "description": "y" * 10_000}],
            }
            for index in range(12)
        ],
    }]

    news_text = gemini.build_news_text(categories)
    prompt = gemini.build_prompt(categories)

    assert len(news_text) <= gemini.MAX_NEWS_TEXT_CHARACTERS
    assert len(prompt) <= 24_000
    for index in range(12):
        assert f"Selected story {index}" in news_text


@pytest.mark.parametrize('failure', ['empty_script', 'tts', 'invalid_audio'])
def test_failed_provider_output_never_reaches_storage(monkeypatch, failure):
    monkeypatch.setattr(pipeline, 'generate_briefing_script', Mock(
        return_value=' ' if failure == 'empty_script' else 'မြန်မာသတင်း'))
    paths = []
    def speech(script, path):
        paths.append(path)
        if failure == 'tts':
            raise RuntimeError('provider unavailable')
        Path(path).write_bytes(b'not an MP3')
    voice = Mock(side_effect=speech)
    upload = Mock()
    monkeypatch.setattr(pipeline, 'generate_speech', voice)
    monkeypatch.setattr(pipeline, 'upload_briefing_audio', upload)
    with pytest.raises(Exception):
        pipeline.generate_combined_audio('e726b864-c879-4b8f-9ac1-c5cb73ae8a58', '2026-11-15', [
            {'stories': [{'title': 'A real story'}]}])
    upload.assert_not_called()
    if failure == 'empty_script':
        voice.assert_not_called()
    assert all(not Path(path).exists() for path in paths)


@pytest.mark.parametrize("stage", [
    "ai_generation", "script_validation", "speech_synthesis",
    "audio_validation", "storage_upload",
])
def test_pipeline_reports_safe_failure_stage(monkeypatch, stage):
    categories = [{"stories": [{"title": "A real story"}]}]
    monkeypatch.setattr(pipeline, "generate_briefing_script", Mock(return_value="မြန်မာသတင်း"))

    def speech(_script, path):
        Path(path).write_bytes(mp3_bytes())

    monkeypatch.setattr(pipeline, "generate_speech", speech)
    monkeypatch.setattr(pipeline, "upload_briefing_audio", Mock())

    targets = {
        "ai_generation": "generate_briefing_script",
        "script_validation": "validate_script",
        "speech_synthesis": "generate_speech",
        "audio_validation": "audio_duration_seconds",
        "storage_upload": "upload_briefing_audio",
    }
    monkeypatch.setattr(pipeline, targets[stage], Mock(side_effect=OSError("secret detail")))

    with pytest.raises(pipeline.PipelineStageError) as raised:
        pipeline.generate_combined_audio(
            "e726b864-c879-4b8f-9ac1-c5cb73ae8a58",
            "2026-11-15",
            categories,
        )

    assert raised.value.stage == stage
    assert raised.value.error_type == "OSError"
    assert "secret detail" not in str(raised.value)
