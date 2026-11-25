"""Shared provider pipeline: one script, one measured MP3, always cleaned up."""
import tempfile
from pathlib import Path
from uuid import uuid4
from uuid import UUID
from datetime import date as calendar_date
import os
import logging

from app.services.ai.gemini import generate_briefing_script
from app.services.storage import upload_briefing_audio
from app.services.tts.azure import generate_speech
from app.services.tts.duration import audio_duration_seconds


from app.services.briefing.validation import validate_script
from app.services.briefing.quality import evaluate_narration


logger = logging.getLogger(__name__)


class PipelineStageError(RuntimeError):
    """Safe, non-secret diagnostic for a failed generation stage."""

    def __init__(self, stage: str, cause: Exception):
        super().__init__(f"Briefing generation failed during {stage}")
        self.stage = stage
        self.error_type = type(cause).__name__


def _run_stage(stage: str, operation):
    try:
        return operation()
    except PipelineStageError:
        raise
    except Exception as error:
        raise PipelineStageError(stage, error) from None


def generate_combined_audio(user_id: str, date: str, categories: list[dict],
                            regeneration_id: str | None = None,
                            target_minutes: int = 7, progress=None) -> dict:
    # Reject unscoped paths before any paid call, including in operator tools.
    if str(UUID(user_id)) != user_id or calendar_date.fromisoformat(date).isoformat() != date:
        raise ValueError('Invalid audio owner or briefing date')
    if not any((story.get("title") or "").strip()
               for group in categories for story in group.get("stories", [])):
        raise ValueError("No usable news stories are available")
    metadata = None
    if os.getenv('BRIEFING_SOURCES_ENABLED', 'true') == 'true':
        from app.services.ai.gemini import generate_grounded_briefing
        if progress:
            progress('writing', 45, 'Writing your briefing')
        metadata = _run_stage(
            "ai_generation",
            lambda: (generate_grounded_briefing(categories, date)
                     if target_minutes == 7 else
                     generate_grounded_briefing(categories, date, target_minutes)),
        )
        script = metadata['script']
    else:
        script = _run_stage(
            "ai_generation",
            lambda: (generate_briefing_script(categories, regeneration_id=regeneration_id)
                     if target_minutes == 7 else
                     generate_briefing_script(categories, regeneration_id=regeneration_id,
                                               target_minutes=target_minutes)),
        )
    script = _run_stage("script_validation", lambda: validate_script(script))
    quality = _run_stage(
        "narration_quality",
        lambda: evaluate_narration(script, categories, target_minutes),
    )
    if quality['status'] == 'narration_below_supported_target':
        raise PipelineStageError(
            'narration_quality',
            RuntimeError('Narration is shorter than the supplied reporting supports'),
        )
    if quality['status'] == 'source_material_insufficient':
        logger.warning(
            'Briefing source material is insufficient for requested duration: '
            'target_seconds=%s supported_seconds=%s',
            quality['target_seconds'], quality['estimated_supported_seconds'],
        )
    if metadata is not None:
        metadata['narration_quality'] = quality
    # Unique storage objects prevent overlapping attempts from overwriting audio
    # referenced by an already-saved briefing. DB generation fencing is still needed.
    storage_path = f"{user_id}/{date}/{uuid4()}.mp3"
    with tempfile.TemporaryDirectory(prefix="morning-brief-") as directory:
        path = str(Path(directory) / "briefing.mp3")
        if progress:
            progress('synthesizing', 70, 'Generating Burmese audio')
        _run_stage("speech_synthesis", lambda: generate_speech(script.strip(), path))
        duration = _run_stage("audio_validation", lambda: audio_duration_seconds(path))
        if progress:
            progress('finalizing', 90, 'Finalizing your briefing')
        _run_stage(
            "storage_upload",
            lambda: upload_briefing_audio(
                file_path=path,
                storage_path=storage_path,
            ),
        )
    return {"script": script.strip(), "audio_url": storage_path,
            "duration_seconds": duration, "source_metadata": metadata}
