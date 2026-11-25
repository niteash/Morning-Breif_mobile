import pytest
from app.services.briefing.grounding import validate_grounded_result


def data():
    return [{'category': {'id':'category','name_my':'မြန်မာ'},'stories':[{'id':'article','title':'Title','source':'Publisher','url':'https://example.org/original','image_url':'https://cdn.example.org/feed-image.jpg'}]}]


def result():
    return {'title':'နေ့သစ်','sections':[{'category_id':'category','source_ids':['article'],'narration':'မြန်မာသတင်း'}]}


def test_snapshot_uses_original_metadata_and_consistent_narration():
    saved = validate_grounded_result(result(), data())
    assert saved['script'] == saved['sections'][0]['narration']
    assert saved['sections'][0]['sources'][0]['url']=='https://example.org/original'
    assert saved['sections'][0]['sources'][0]['image_url']=='https://cdn.example.org/feed-image.jpg'


def test_unsafe_feed_image_is_omitted_without_rejecting_the_source():
    batch = data(); batch[0]['stories'][0]['image_url'] = 'file:///private/image.jpg'
    assert validate_grounded_result(result(), batch)['sections'][0]['sources'][0]['image_url'] is None


@pytest.mark.parametrize('field,value',[('source_ids',['invented']),('source_ids',[]),('category_id','unselected')])
def test_fabricated_or_unrelated_sources_rejected(field,value):
    value_result=result();value_result['sections'][0][field]=value
    with pytest.raises(ValueError):validate_grounded_result(value_result,data())


def test_missing_original_url_rejected():
    batch=data();batch[0]['stories'][0]['url']=''
    with pytest.raises(ValueError):validate_grounded_result(result(),batch)


@pytest.mark.parametrize('section', [None, [], 'not a section'])
def test_malformed_sections_rejected(section):
    value = result(); value['sections'] = [section]
    with pytest.raises(ValueError): validate_grounded_result(value, data())


@pytest.mark.parametrize('url', ['javascript:alert(1)', 'https://user:secret@example.org/news', 'file:///news'])
def test_unsafe_publisher_urls_rejected(url):
    batch = data(); batch[0]['stories'][0]['url'] = url
    with pytest.raises(ValueError): validate_grounded_result(result(), batch)


def test_snapshot_survives_live_feed_changes():
    batch = data()
    saved = validate_grounded_result(result(), batch)
    batch[0]['stories'][0]['title'] = 'Changed'
    batch[0]['stories'].clear()
    assert saved['sections'][0]['sources'][0]['title'] == 'Title'


def test_duplicate_citations_preserve_one_source_snapshot():
    value = result(); value['sections'][0]['source_ids'] *= 2
    assert len(validate_grounded_result(value, data())['sections'][0]['sources']) == 1


@pytest.mark.parametrize('configured', ['0', '11', 'invalid'])
def test_configured_selection_limit_fails_closed(monkeypatch, configured):
    from app.services.news.selector import configured_story_limit
    monkeypatch.setenv('BRIEFING_STORIES_PER_CATEGORY', configured)
    with pytest.raises(ValueError): configured_story_limit()


def test_configured_selection_limit_is_bounded(monkeypatch):
    from app.services.news.selector import configured_story_limit
    monkeypatch.setenv('BRIEFING_STORIES_PER_CATEGORY', '7')
    assert configured_story_limit() == 7


def test_overlapping_sources_remain_attached_to_the_narrated_event():
    batch = data()
    batch[0]['stories'][0]['supporting_sources'] = [{
        'id': 'alternate', 'category_id': 'category', 'source': 'Second publisher',
        'title': 'Same event', 'url': 'https://example.net/event',
    }]
    saved = validate_grounded_result(result(), batch)
    assert [s['id'] for s in saved['sections'][0]['sources']] == ['article', 'alternate']


def test_nonempty_selected_categories_cannot_be_silently_omitted():
    batch = data()
    batch.append({'category': {'id': 'second', 'name_my': 'နည်းပညာ'}, 'stories': [
        {'id': 'second-article', 'title': 'Other news', 'source': 'Publisher', 'url': 'https://example.org/other'}]})
    with pytest.raises(ValueError, match='coverage'):
        validate_grounded_result(result(), batch)


def test_selected_story_cannot_be_silently_omitted_from_category():
    batch = data()
    batch[0]['stories'].append({
        'id': 'second-article', 'title': 'Second report', 'source': 'Publisher',
        'url': 'https://example.org/second',
    })
    with pytest.raises(ValueError, match='story coverage'):
        validate_grounded_result(result(), batch)


def test_story_narrations_must_match_trusted_source_order_and_assembled_text():
    value = result()
    value['sections'][0]['story_narrations'] = [{
        'source_id': 'article', 'narration': 'မြန်မာသတင်း',
    }]
    saved = validate_grounded_result(value, data())
    assert saved['sections'][0]['story_narrations'][0]['source_id'] == 'article'
    value['sections'][0]['story_narrations'][0]['source_id'] = 'invented'
    with pytest.raises(ValueError, match='story narration coverage'):
        validate_grounded_result(value, data())


def test_empty_selected_category_needs_no_invented_story():
    batch = data(); batch.append({'category': {'id': 'empty'}, 'stories': []})
    assert len(validate_grounded_result(result(), batch)['sections']) == 1


def test_english_heavy_section_is_allowed_when_complete_script_is_burmese():
    batch = data()
    batch.append({'category': {'id': 'second', 'name_my': 'နည်းပညာ'}, 'stories': [
        {'id': 'second-article', 'title': 'AI update', 'source': 'Publisher',
         'url': 'https://example.org/ai'}]})
    value = result()
    value['sections'].append({'category_id': 'second', 'source_ids': ['second-article'],
                              'narration': 'OpenAI technology update.'})
    saved = validate_grounded_result(value, batch)
    assert saved['sections'][1]['narration'] == 'OpenAI technology update.'


def test_world_recognizes_cross_border_event_without_accepting_generic_scams():
    from app.services.news.relevance import is_relevant
    assert is_relevant('world', 'Ongoing demolition of scam hubs in Shwe Kokko Phase II crackdown',
                       'Working with neighbouring and regional countries to crack down on online scams.')
    assert not is_relevant('world', 'Five tips to avoid online scams', 'Stay safe when browsing.')


def test_myanmar_relevance_accepts_burmese_headline():
    from app.services.news.relevance import is_relevant

    assert is_relevant(
        "myanmar",
        "မန္တလေးမြို့တွင် မိုးသည်းထန်စွာ ရွာသွန်း",
        "မန္တလေးမြို့တွင် မိုးသည်းထန်စွာ ရွာသွန်းခဲ့သည်။",
    )


def test_myanmar_relevance_rejects_unrelated_burmese_headline():
    from app.services.news.relevance import is_relevant

    assert not is_relevant(
        "myanmar",
        "ဂျပန်နိုင်ငံတွင် နည်းပညာအသစ် မိတ်ဆက်",
        "ဂျပန်ကုမ္ပဏီတစ်ခုက နည်းပညာအသစ်ကို မိတ်ဆက်ခဲ့သည်။",
    )



def test_myanmar_relevance_rejects_unrelated_story_with_location():
    from app.services.news.relevance import is_relevant

    assert not is_relevant(
        "myanmar",
        "ဂျပန်နိုင်ငံတွင် နည်းပညာအသစ် မိတ်ဆက်",
        "ဂျပန်ကုမ္ပဏီတစ်ခုက နည်းပညာအသစ်ကို "
        "မိတ်ဆက်ခဲ့ပြီး ရန်ကုန်မြို့ကိုလည်း ဖော်ပြခဲ့သည်။",
    )



def test_myanmar_relevance_rejects_unrelated_headline_with_location():
    from app.services.news.relevance import is_relevant

    assert not is_relevant(
        "myanmar",
        "ဂျပန်ကုမ္ပဏီက ရန်ကုန်အမည်ကို အသုံးပြုပြီး "
        "တိုကျိုတွင် နည်းပညာအသစ် မိတ်ဆက်",
        "ဂျပန်နိုင်ငံ တိုကျိုမြို့တွင် "
        "နည်းပညာအသစ်တစ်ခု မိတ်ဆက်ခဲ့သည်။",
    )


def test_myanmar_relevance_rejects_foreign_event_with_myanmar_location():
    from app.services.news.relevance import is_relevant

    assert not is_relevant(
        "myanmar",
        "ဂျပန်ကုမ္ပဏီက ရန်ကုန်အမည်ပါသော "
        "ထုတ်ကုန်သစ်ကို တိုကျိုတွင် ကြေညာ",
        "ဂျပန်နိုင်ငံတွင် ထုတ်ကုန်သစ်တစ်ခု "
        "မိတ်ဆက်ခဲ့ခြင်းဖြစ်သည်။",
    )
