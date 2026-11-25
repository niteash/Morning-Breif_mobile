"""Fill missing staging news images from reviewed RSS metadata by exact article URL."""
import argparse
import os
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
PROJECT = 'wwtntxknfjagdjdgiaxu'
STAGING_URL = f'https://{PROJECT}.supabase.co'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--confirm-staging-project', default='')
    args = parser.parse_args()
    if args.write and args.confirm_staging_project != PROJECT:
        parser.error('Write mode requires the exact staging project confirmation')

    values = dotenv_values(ROOT / 'backend/.env.staging', interpolate=False)
    if values.get('SUPABASE_URL') != STAGING_URL or not values.get('SUPABASE_SERVICE_ROLE_KEY'):
        raise SystemExit('Staging configuration unavailable')
    os.environ['PYTHON_DOTENV_DISABLED'] = '1'
    for key in ('SUPABASE_URL', 'SUPABASE_PUBLISHABLE_KEY', 'SUPABASE_SERVICE_ROLE_KEY'):
        os.environ[key] = values.get(key) or ''

    import sys
    sys.path.insert(0, str(ROOT / 'backend'))
    from app.lib.supabase import admin_supabase
    from app.services.news.rss_processing import canonical_article_url
    from app.services.news.rss_registry import SOURCES
    from app.services.news.safe_rss import FeedFailure, fetch_feed, parse_feed

    existing = (admin_supabase.table('news_items').select('id,url,image_url')
                .is_('image_url', 'null').limit(1000).execute().data or [])
    by_url = {canonical_article_url(row.get('url') or ''): row for row in existing}
    by_url.pop(None, None)
    matches = {}
    failed_sources = 0
    for source in SOURCES:
        if not source.enabled:
            continue
        try:
            entries = parse_feed(fetch_feed(source).body, source)
        except FeedFailure:
            failed_sources += 1
            continue
        for entry in entries:
            article_url = canonical_article_url(entry.get('url') or '')
            image_url = canonical_article_url(entry.get('image_url') or '')
            if article_url in by_url and image_url:
                matches[by_url[article_url]['id']] = image_url

    updated = 0
    if args.write:
        for identity, image_url in matches.items():
            response = (admin_supabase.table('news_items').update({'image_url': image_url})
                        .eq('id', identity).is_('image_url', 'null').execute())
            if response.data:
                updated += 1
    print({
        'mode': 'write' if args.write else 'dry-run',
        'missing_rows': len(existing),
        'matched_rows': len(matches),
        'updated_rows': updated,
        'failed_sources': failed_sources,
    })
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
