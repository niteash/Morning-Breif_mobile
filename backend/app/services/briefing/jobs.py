"""Durable generation coordination. Missing migrations fail closed before paid work."""
import logging
import os
from datetime import datetime, timezone
import math

from app.lib.supabase import admin_supabase
from app.services.briefing.pipeline import generate_combined_audio
from app.services.entitlements import require_generation_access

logger = logging.getLogger(__name__)


class GenerationUnavailable(Exception):
    pass


class GenerationBusy(Exception):
    def __init__(self, detail=None):
        self.detail = detail or {'code': 'generation_busy', 'status': 'unknown',
                                'message': 'Generation is busy. Refresh the briefing status.'}


class GenerationDisabled(Exception):
    pass


def generation_disabled():
    return (os.getenv('BRIEFING_GENERATION_ENABLED', 'true') != 'true'
            or any(not (os.getenv(key) or '').strip() for key in
                   ('GEMINI_API_KEY', 'AZURE_SPEECH_KEY', 'AZURE_SPEECH_REGION')))


def busy_detail(user_id, day):
    """Read only the caller's job; never expose tokens or request IDs."""
    detail = {'code': 'generation_busy', 'status': 'unknown',
              'message': 'Generation is busy. Refresh the briefing status.'}
    try:
        rows = (admin_supabase.table('briefing_generation_jobs')
                .select('state,lease_until').eq('user_id', user_id)
                .eq('briefing_date', day).limit(1).execute().data)
        if not rows:
            return detail
        row = rows[0]
        if row['state'] == 'failed':
            detail.update(code='generation_cooldown', status='cooldown',
                          message='The previous attempt failed. Wait for the cooldown before retrying.')
        elif row['state'] == 'generating':
            detail.update(code='generation_in_progress', status='generating',
                          message='Your briefing is being prepared. Refresh its status; do not submit again.')
        until = datetime.fromisoformat(row['lease_until'].replace('Z', '+00:00'))
        detail['retry_after_seconds'] = max(0, math.ceil((until - datetime.now(timezone.utc)).total_seconds()))
        detail['retry_at'] = until.isoformat()
    except Exception:
        logger.warning('generation_status_lookup_failed')
    return detail


class GenerationLimited(Exception):
    pass


class LostGenerationLease(Exception):
    pass


def generate_and_save(user_id: str, date: str, categories: list[dict],
                      regeneration_id: str | None = None, target_minutes: int = 7,
                      progress=None) -> tuple[dict, bool]:
    # Shared manual/scheduled gate, before job claims or paid provider work.
    require_generation_access(user_id)
    if not any((story.get("title") or "").strip()
               for group in categories for story in group.get("stories", [])):
        raise ValueError("No usable stories")
    if generation_disabled():
        # Reuse a ready result without a claim/write/provider call, including a
        # replay of the same persisted regeneration intent.
        rows = (admin_supabase.table('briefings').select('*').eq('user_id', user_id)
                .eq('briefing_date', date).eq('status', 'ready').limit(1).execute().data)
        if rows and isinstance(rows, list):
            if not regeneration_id:
                return rows[0], False
            previous = (admin_supabase.table('briefing_generation_jobs').select('request_id,state')
                        .eq('user_id', user_id).eq('briefing_date', date).limit(1).execute().data)
            if previous and previous[0].get('state') == 'ready' and previous[0].get('request_id') == regeneration_id:
                return rows[0], False
        raise GenerationDisabled()
    previous_audio = None
    if regeneration_id:
        try:
            rows = (admin_supabase.table('briefings').select('audio_url')
                    .eq('user_id', user_id).eq('briefing_date', date).limit(1).execute().data or [])
            previous_audio = rows[0].get('audio_url') if isinstance(rows, list) and rows else None
        except Exception:
            # Cleanup is best effort and must not block a new briefing.
            previous_audio = None
    grounded = os.getenv('BRIEFING_SOURCES_ENABLED', 'true') == 'true'
    if grounded:
        try:
            if admin_supabase.rpc('briefing_sources_ready', {}).execute().data is not True:
                raise GenerationUnavailable('Source schema unavailable')
        except Exception:
            raise GenerationUnavailable('Source schema unavailable') from None
    params = {"p_user_id": user_id, "p_date": date}
    try:
        claim = admin_supabase.rpc("claim_briefing_v2", {
            **params, "p_force": bool(regeneration_id), "p_request_id": regeneration_id,
        }).execute().data
    except Exception as error:
        raise GenerationUnavailable("Generation coordination unavailable") from error
    if not isinstance(claim, dict):
        raise GenerationUnavailable("Invalid claim response")
    outcome = claim.get("outcome")
    if outcome == "ready":
        if not isinstance(claim.get("briefing"), dict):
            raise GenerationUnavailable("Invalid saved briefing")
        return claim["briefing"], False
    if outcome == "busy":
        raise GenerationBusy(busy_detail(user_id, date))
    if outcome == "limited":
        raise GenerationLimited()
    if outcome != "claimed" or not claim.get("token"):
        raise GenerationUnavailable("Invalid claim response")
    owned = {**params, "p_token": claim["token"]}
    try:
        artifact = (generate_combined_audio(user_id, date, categories, regeneration_id)
                    if target_minutes == 7 and progress is None else
                    generate_combined_audio(user_id, date, categories, regeneration_id,
                                            target_minutes, progress))
        source_params = {'p_metadata': artifact['source_metadata']} if grounded else {}
        saved = admin_supabase.rpc('finish_briefing_with_sources' if grounded else 'finish_briefing_v2', {
            **owned, **source_params, "p_script": artifact["script"], "p_audio_path": artifact["audio_url"],
            "p_duration": artifact["duration_seconds"],
        }).execute().data
        if not isinstance(saved, dict) or not saved.get("id"):
            raise LostGenerationLease()
        chapters = build_chapters(artifact.get('source_metadata'), artifact['duration_seconds'])
        if chapters or target_minutes != 7:
            updated = (admin_supabase.table('briefings').update({
                'chapters': chapters, 'target_minutes': target_minutes,
            }).eq('id', saved['id']).eq('user_id', user_id).execute().data or [])
            if isinstance(updated, list) and updated:
                saved = updated[0]
        if (previous_audio and previous_audio != artifact['audio_url']
                and previous_audio.startswith(f'{user_id}/')):
            try:
                admin_supabase.storage.from_('briefings').remove([previous_audio])
            except Exception as error:
                logger.warning('Superseded audio cleanup deferred: error_type=%s', type(error).__name__)
        return saved, True
    except Exception:
        try:
            admin_supabase.rpc("fail_briefing_v2", owned).execute()
        except Exception:
            # No raw provider/DB exceptions in logs. An abandoned claim expires.
            logger.warning("Could not mark generation failed; lease will expire")
        raise


def build_chapters(metadata: dict | None, duration_seconds: int) -> list[dict]:
    """Create deterministic category/story markers without asking the model for timestamps."""
    if not metadata or not isinstance(metadata.get('sections'), list) or duration_seconds <= 0:
        return []
    sections = [section for section in metadata['sections'] if section.get('sources')]
    if not sections:
        return []
    weights = [max(1, len(section.get('narration') or '')) for section in sections]
    total = sum(weights)
    cursor = 0.0
    chapters = []
    for section, weight in zip(sections, weights):
        start = cursor
        cursor += duration_seconds * weight / total
        sources = section.get('sources') or []
        chapters.append({
            'id': f"category:{section.get('category_id')}", 'type': 'category',
            'title': section.get('category_name') or 'သတင်း',
            'category_name': section.get('category_name'),
            'start_seconds': round(start), 'end_seconds': round(cursor),
        })
        span = max(1, cursor - start)
        for index, source in enumerate(sources):
            marker = start + span * index / max(1, len(sources))
            chapters.append({
                'id': f"story:{source.get('id')}", 'type': 'story',
                'story_id': source.get('id'), 'title': source.get('title'),
                'category_name': section.get('category_name'),
                'publisher': source.get('source'), 'url': source.get('url'),
                'image_url': source.get('image_url'),
                'published_at': source.get('published_at'),
                'start_seconds': round(marker),
                'end_seconds': round(start + span * (index + 1) / max(1, len(sources))),
            })
    return chapters
