"""Validate model source IDs and snapshot publisher metadata from trusted selection."""
from urllib.parse import urlsplit
from app.services.briefing.validation import validate_script


def _safe_image_url(value):
    if not value:
        return None
    try:
        parsed = urlsplit(value)
    except (TypeError, ValueError):
        return None
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        return None
    return value


def validate_grounded_result(result, categories):
    selected = {}
    for group in categories:
        for story in group['stories']:
            selected[story['id']] = (group['category'], story)
    if not isinstance(result, dict) or not isinstance(result.get('title'), str) or not result['title'].strip():
        raise ValueError('Missing briefing title')
    sections = result.get('sections')
    if not isinstance(sections, list) or not sections:
        raise ValueError('Missing grounded sections')
    if len(result['title']) > 240 or len(sections) > 50:
        raise ValueError('Grounded result exceeds limits')
    normalized = []
    referenced_ids = []
    for section in sections:
        if not isinstance(section, dict):
            raise ValueError('Invalid grounded section')
        ids = section.get('source_ids')
        if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or i not in selected for i in ids):
            raise ValueError('Unknown source reference')
        ids = list(dict.fromkeys(ids))
        referenced_ids.extend(ids)
        sources = []
        for identity in ids:
            category, story = selected[identity]
            if section.get('category_id') != category['id']:
                raise ValueError('Source category mismatch')
            if any(not isinstance(story.get(key), str) or not story[key].strip() for key in ('title', 'source')):
                raise ValueError('Missing source attribution')
            url = urlsplit(story.get('url') or '')
            if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
                raise ValueError('Missing or unsafe publisher URL')
            sources.append({
                **{key: story.get(key) for key in ('id','title','source','url','description','published_at')},
                'image_url': _safe_image_url(story.get('image_url')),
            })
            # Retain alternate reports of this event from the selected cluster.
            # They are selection snapshots, never URLs supplied by the model.
            for related in story.get('supporting_sources', []):
                parsed = urlsplit(related.get('url') or '')
                if (related.get('category_id') != category['id'] or not related.get('id')
                    or not related.get('title') or not related.get('source')
                    or parsed.scheme not in ('http', 'https') or not parsed.hostname
                    or parsed.username or parsed.password):
                    raise ValueError('Invalid supporting source')
                if related['id'] not in {item['id'] for item in sources}:
                    sources.append({
                        **{key: related.get(key) for key in ('id','title','source','url','description','published_at')},
                        'image_url': _safe_image_url(related.get('image_url')),
                    })
        narration = section.get('narration')
        if not isinstance(narration, str) or not narration.strip() or len(narration) > 12_000:
            raise ValueError('Invalid grounded section')
        story_narrations = section.get('story_narrations')
        normalized_story_narrations = []
        if story_narrations is not None:
            if (not isinstance(story_narrations, list)
                    or len(story_narrations) != len(ids)):
                raise ValueError('Invalid story narration coverage')
            for expected_id, item in zip(ids, story_narrations):
                if (not isinstance(item, dict) or item.get('source_id') != expected_id
                        or not isinstance(item.get('narration'), str)
                        or not item['narration'].strip()
                        or item['narration'].strip() not in narration):
                    raise ValueError('Invalid story narration coverage')
                normalized_story_narrations.append({
                    'source_id': expected_id,
                    'narration': item['narration'].strip(),
                })
        normalized.append({'category_id': section['category_id'], 'category_name': category.get('name_my') or category.get('name_en'),
                           'narration': narration.strip(), 'source_ids': ids, 'sources': sources,
                           **({'story_narrations': normalized_story_narrations}
                              if story_narrations is not None else {})})
    expected = {g['category']['id'] for g in categories if g['stories']}
    if {section['category_id'] for section in normalized} != expected:
        raise ValueError('Missing selected category coverage')
    expected_story_ids = {
        story['id'] for group in categories for story in group.get('stories', [])
    }
    if set(referenced_ids) != expected_story_ids or len(referenced_ids) != len(expected_story_ids):
        raise ValueError('Missing selected story coverage')
    # Narration is assembled ONLY from validated sections; no separate ungrounded script.
    return {'title': result['title'].strip(), 'sections': normalized,
            'script': validate_script('\n\n'.join(section['narration'] for section in normalized))}
