"""Offline rehearsal of the real coordinator/pipeline with no external side effects."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID
from datetime import datetime, timedelta, timezone
import hashlib
import json


def validate_selection(categories, now=None):
    now = now or datetime.now(timezone.utc)
    counts = {}
    ids = set()
    for group in categories:
        category = group['category']
        UUID(category['id'])
        counts[category['slug']] = len(group['stories'])
        reviewed = [article for leader in group['stories'] for article in [leader, *leader.get('supporting_sources', [])]]
        for story in reviewed:
            UUID(story['id'])
            if story['id'] in ids or story['category_id'] != category['id']:
                raise ValueError('Duplicate or mismatched story')
            ids.add(story['id'])
            if not story.get('title', '').strip() or not story.get('source', '').strip():
                raise ValueError('Missing title or attribution')
            from urllib.parse import urlsplit
            url = urlsplit(story['url'])
            if url.scheme not in {'http', 'https'} or not url.hostname or url.username or url.password:
                raise ValueError('Invalid publisher URL')
            published = datetime.fromisoformat(story['published_at'].replace('Z', '+00:00'))
            if published.tzinfo is None or not now - timedelta(hours=24) <= published <= now:
                raise ValueError('Story outside the approved freshness window')
    if not ids:
        raise ValueError('No eligible selected news; do not generate filler')
    return counts


def batch_digest(categories):
    """Hash a canonical provider selection, ignoring volatile rank scores."""
    story_fields = (
        'id', 'category_id', 'title', 'description', 'source', 'url',
        'image_url', 'published_at',
    )

    def story_identity(story):
        return (
            str(story.get('id') or ''),
            str(story.get('url') or ''),
            str(story.get('title') or ''),
        )

    reviewed = []
    for group in categories:
        category = dict(group.get('category') or {})
        stories = []
        for source_story in sorted(group.get('stories') or [], key=story_identity):
            story = {key: source_story.get(key) for key in story_fields}
            story['supporting_sources'] = [
                {key: supporting.get(key) for key in story_fields}
                for supporting in sorted(
                    source_story.get('supporting_sources') or [],
                    key=story_identity,
                )
            ]
            stories.append(story)
        reviewed.append({'category': category, 'stories': stories})
    reviewed.sort(key=lambda group: (
        str(group['category'].get('slug') or ''),
        str(group['category'].get('id') or ''),
    ))
    canonical = json.dumps(
        reviewed,
        sort_keys=True,
        ensure_ascii=False,
        separators=(',', ':'),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def mock_rehearsal(user_id, day, categories):
    from app.services.briefing import jobs, pipeline
    from app.services.ai.gemini import build_prompt
    prompt = build_prompt(categories)
    if len(prompt) > 24_000:
        raise ValueError('Prompt exceeds the reviewed limit')
    # Synthetic encoded MP3 frames exercise parsing, not voice quality.
    audio = (bytes.fromhex('fffb9064') + bytes(413)) * 100
    db = Mock()
    saved = {'id': 'mock-briefing', 'user_id': user_id, 'briefing_date': day, 'status': 'ready'}
    def rpc(name, params):
        if name == 'briefing_sources_ready':
            result = True
        elif name == 'claim_briefing_v2':
            result = {'outcome': 'claimed', 'token': 'mock-lease'}
        elif name in ('finish_briefing_v2', 'finish_briefing_with_sources'):
            assert params['p_token'] == 'mock-lease'
            saved.update(script=params['p_script'], audio_url=params['p_audio_path'], duration_seconds=params['p_duration'])
            if 'p_metadata' in params:
                saved['source_metadata'] = params['p_metadata']
            result = saved
        else:
            raise AssertionError('Unexpected coordinator call')
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=result))
    db.rpc.side_effect = rpc
    def speech(text, path):
        Path(path).write_bytes(audio)
    def upload(*, file_path, storage_path):
        assert Path(file_path).read_bytes() == audio
        assert storage_path.startswith(f'{user_id}/{day}/')
    from app.services.briefing.grounding import validate_grounded_result
    def grounded(groups, local_day):
        return validate_grounded_result({'title': 'နေ့သစ်', 'sections': [
            {'category_id': g['category']['id'], 'source_ids': [s['id'] for s in g['stories']],
             'narration': 'မင်္ဂလာပါ။ ဤအသံသည် စမ်းသပ်မှုအတွက်သာ ဖြစ်ပါသည်။'}
            for g in groups if g['stories']]}, groups)
    with patch('app.services.ai.gemini.generate_grounded_briefing', side_effect=grounded), \
         patch.object(jobs, 'generation_disabled', return_value=False), patch.object(jobs, 'admin_supabase', db), patch.object(jobs, 'require_generation_access'), \
         patch.object(pipeline, 'generate_briefing_script', return_value='မင်္ဂလာပါ။ ဤအသံသည် စမ်းသပ်မှုအတွက်သာ ဖြစ်ပါသည်။'), \
         patch.object(pipeline, 'generate_speech', side_effect=speech) as tts, \
         patch.object(pipeline, 'upload_briefing_audio', side_effect=upload) as storage:
        result, created = jobs.generate_and_save(user_id, day, categories)
    assert created and result['status'] == 'ready' and result['duration_seconds'] > 0
    assert tts.call_count == storage.call_count == 1
    return {'mode': 'mocked_entitlement_providers_storage_and_database', 'status': result['status'],
            'duration_seconds': result['duration_seconds'], 'prompt_characters': len(prompt),
            'owner_path_valid': True, 'external_writes': 0, 'paid_calls': 0}
