import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from itertools import permutations
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from postgrest import SyncPostgrestClient

from app.services import scheduler
from app.services.briefing.rehearsal import batch_digest
from app.services.news.clustering import cluster_stories
from app.services.news.ranker import rank_candidates
from app.services.news import selector
from app.services.news.selector import (
    select_publisher_balanced,
    stable_categories,
    stable_category_rows,
    story_feedback_scores,
)


NOW = datetime(2026, 11, 25, 6, tzinfo=timezone.utc)


def _story(
    identifier: str,
    title: str,
    description: str = 'Source detail',
    source: str = 'Fixture Publisher',
) -> dict:
    return {
        'id': identifier,
        'category_id': 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
        'title': title,
        'description': description,
        'source': source,
        'url': f'https://example.com/{identifier}',
        'published_at': NOW.isoformat(),
    }


def test_equal_score_ranking_is_stable_when_database_row_order_changes():
    stories = [
        _story('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'Second distinct report'),
        _story('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'First distinct report'),
    ]

    forward = rank_candidates(stories, category_slug=None, now=NOW)
    reverse = rank_candidates(list(reversed(stories)), category_slug=None, now=NOW)

    assert [story['id'] for story in forward] == [story['id'] for story in reverse]


def test_selected_categories_have_a_canonical_order():
    rows = [
        {'category_id': '2', 'categories': {'slug': 'myanmar'}},
        {'category_id': '1', 'categories': {'slug': 'crypto'}},
    ]

    assert [row['category_id'] for row in stable_category_rows(rows)] == ['1', '2']


def test_plain_scheduled_categories_have_the_same_canonical_order():
    categories = [
        {'id': '2', 'slug': 'myanmar'},
        {'id': '1', 'slug': 'crypto'},
    ]

    assert [row['id'] for row in stable_categories(categories)] == ['1', '2']


def test_opposing_story_feedback_is_order_independent():
    rows = [
        {'story_id': 'story-a', 'action': 'more_like_this'},
        {'story_id': 'story-a', 'action': 'less_like_this'},
        {'story_id': 'story-b', 'action': 'more_like_this'},
    ]

    assert story_feedback_scores(rows) == story_feedback_scores(list(reversed(rows)))
    assert story_feedback_scores(rows) == {'story-a': 0, 'story-b': 18}


def _selected_pipeline(stories: list[dict], limit: int = 5) -> list[dict]:
    ranked = rank_candidates(stories, category_slug=None, now=NOW, limit=20)
    clusters = cluster_stories(ranked, similarity_threshold=0.45)
    return select_publisher_balanced(clusters, limit)


def test_repeated_pipeline_selection_and_digest_ignore_shuffled_database_rows():
    stories = [
        _story('10000000-0000-4000-8000-000000000001', 'Alpha market outlook', source='Publisher A'),
        _story('10000000-0000-4000-8000-000000000002', 'Beta market outlook', source='Publisher A'),
        _story('10000000-0000-4000-8000-000000000003', 'Gamma market outlook', source='Publisher A'),
        _story('10000000-0000-4000-8000-000000000004', 'Delta market outlook', source='Publisher B'),
        _story('10000000-0000-4000-8000-000000000005', 'Epsilon market outlook', source='Publisher C'),
    ]
    category = {
        'id': 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
        'slug': 'business',
    }
    expected = _selected_pipeline(stories)
    expected_ids = [story['id'] for story in expected]
    expected_digest = batch_digest([{'category': category, 'stories': expected}])

    for shuffled in list(permutations(stories))[:40]:
        selected = _selected_pipeline(list(shuffled))
        assert [story['id'] for story in selected] == expected_ids
        assert batch_digest([{'category': category, 'stories': selected}]) == expected_digest


def test_complete_selector_is_stable_when_database_results_are_shuffled(monkeypatch):
    category_id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
    stories = [
        {
            **_story(
                f'10000000-0000-4000-8000-00000000000{index}',
                title,
                source=source,
            ),
            'category_id': category_id,
            'author': None,
            'image_url': None,
            'created_at': NOW.isoformat(),
        }
        for index, (title, source) in enumerate([
            ('Alpha company reports business update', 'Publisher A'),
            ('Beta company reports business update', 'Publisher A'),
            ('Gamma company reports business update', 'Publisher A'),
            ('Delta company reports business update', 'Publisher B'),
            ('Epsilon company reports business update', 'Publisher C'),
        ], start=1)
    ]
    news_calls = 0
    news_requests = []

    def handle(request):
        nonlocal news_calls
        table = request.url.path.rsplit('/', 1)[-1]
        if table == 'story_feedback':
            return httpx.Response(200, json=[])
        if table == 'profiles':
            return httpx.Response(200, json=[{}])
        if table == 'user_categories':
            return httpx.Response(200, json=[{
                'category_id': category_id,
                'categories': {
                    'id': category_id,
                    'slug': 'business',
                    'name_en': 'Business',
                    'name_my': 'စီးပွားရေး',
                },
            }])
        if table == 'news_items':
            news_requests.append(request)
            news_calls += 1
            rows = stories if news_calls % 2 else list(reversed(stories))
            return httpx.Response(200, json=rows)
        raise AssertionError(f'Unexpected table: {table}')

    client = httpx.Client(transport=httpx.MockTransport(handle))
    postgrest = SyncPostgrestClient(
        'https://offline.invalid/rest/v1',
        http_client=client,
    )
    monkeypatch.setattr(
        selector,
        'create_supabase_client',
        lambda _token: SimpleNamespace(table=postgrest.from_),
    )
    try:
        first = asyncio.run(selector.select_recent_stories(
            user_id='fixture-user',
            access_token='offline-token',
            stories_per_category=5,
            now=NOW,
        ))
        second = asyncio.run(selector.select_recent_stories(
            user_id='fixture-user',
            access_token='offline-token',
            stories_per_category=5,
            now=NOW,
        ))
    finally:
        client.close()

    first_ids = [story['id'] for story in first[0]['stories']]
    second_ids = [story['id'] for story in second[0]['stories']]
    assert first_ids == second_ids
    assert batch_digest(first) == batch_digest(second)
    assert all(
        request.url.params['order'] == 'published_at.desc,id.asc'
        for request in news_requests
    )


def test_publisher_balancing_keeps_rank_order_and_diversity_cap():
    leaders = [
        _story('10000000-0000-4000-8000-000000000001', 'First', source='Publisher A'),
        _story('10000000-0000-4000-8000-000000000002', 'Second', source='Publisher A'),
        _story('10000000-0000-4000-8000-000000000003', 'Third', source='Publisher A'),
        _story('10000000-0000-4000-8000-000000000004', 'Fourth', source='Publisher B'),
        _story('10000000-0000-4000-8000-000000000005', 'Fifth', source='Publisher C'),
    ]

    selected = select_publisher_balanced([[story] for story in leaders], limit=4)

    assert [story['id'] for story in selected] == [
        leaders[0]['id'], leaders[1]['id'], leaders[3]['id'], leaders[4]['id'],
    ]
    assert [story['source'] for story in selected] == [
        'Publisher A', 'Publisher A', 'Publisher B', 'Publisher C',
    ]


def test_scheduled_query_has_fixed_window_and_total_database_order(monkeypatch):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json=[])

    client = httpx.Client(transport=httpx.MockTransport(handle))
    postgrest = SyncPostgrestClient(
        'https://offline.invalid/rest/v1',
        http_client=client,
    )
    monkeypatch.setattr(
        scheduler,
        'admin_supabase',
        SimpleNamespace(table=postgrest.from_),
    )
    try:
        assert scheduler.select_recent_news(
            {'id': 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'slug': 'business'},
            now=NOW,
        ) == []
    finally:
        client.close()

    params = requests[0].url.params
    assert params['order'] == 'published_at.desc,id.asc'
    assert params.get_list('published_at') == [
        'gte.2026-11-24T06:00:00+00:00',
        'lte.2026-11-25T06:00:00+00:00',
    ]


def test_scheduled_categories_share_one_evaluation_timestamp(monkeypatch):
    categories = [
        {'id': '2', 'slug': 'myanmar'},
        {'id': '1', 'slug': 'crypto'},
    ]
    monkeypatch.setattr(scheduler, 'select_user_categories', lambda _user: categories)
    database = Mock()
    database.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
        SimpleNamespace(data=[])
    )
    database.table.return_value.select.return_value.eq.return_value.execute.return_value = (
        SimpleNamespace(data=[])
    )
    monkeypatch.setattr(scheduler, 'admin_supabase', database)
    seen = []

    def select(category, preferences, now):
        seen.append((category['slug'], now))
        return [_story(
            f'10000000-0000-4000-8000-00000000000{len(seen)}',
            f"{category['slug']} report",
        )]

    monkeypatch.setattr(scheduler, 'select_recent_news', select)

    result = scheduler.collect_user_news('fixture-user', now=NOW)

    assert [group['category']['slug'] for group in result] == [
        'myanmar', 'crypto',
    ]
    assert seen == [('myanmar', NOW), ('crypto', NOW)]


def test_naive_evaluation_timestamps_fail_before_story_ranking():
    naive = datetime(2026, 11, 25, 6)

    with pytest.raises(ValueError, match='include a timezone'):
        scheduler.select_recent_news(
            {'id': 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'slug': 'business'},
            now=naive,
        )


def test_selection_digest_is_stable_across_category_story_and_support_order():
    first = {
        'category': {'id': 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'slug': 'crypto'},
        'stories': [
            {**_story('11111111-1111-4111-8111-111111111111', 'Bitcoin report'),
             'supporting_sources': [
                 _story('33333333-3333-4333-8333-333333333333', 'Supporting B'),
                 _story('22222222-2222-4222-8222-222222222222', 'Supporting A'),
             ]},
            _story('44444444-4444-4444-8444-444444444444', 'Ethereum report'),
        ],
    }
    second = {
        'category': {'id': 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'slug': 'myanmar'},
        'stories': [_story('55555555-5555-4555-8555-555555555555', 'Myanmar report')],
    }
    reordered = [deepcopy(second), deepcopy(first)]
    reordered[1]['stories'].reverse()
    reordered[1]['stories'][1]['supporting_sources'].reverse()

    assert batch_digest([first, second]) == batch_digest(reordered)


def test_selection_digest_changes_when_grounding_evidence_changes():
    categories = [{
        'category': {'id': 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'slug': 'crypto'},
        'stories': [_story('11111111-1111-4111-8111-111111111111', 'Bitcoin report')],
    }]
    changed = deepcopy(categories)
    changed[0]['stories'][0]['description'] = 'Different supported facts'

    assert batch_digest(categories) != batch_digest(changed)
