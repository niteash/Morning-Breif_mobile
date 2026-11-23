"""Resolve configured feed categories in the current database environment."""
from uuid import UUID

from app.lib.supabase import admin_supabase
from app.services.news.sources import NEWS_SOURCES


def resolve_category_ids() -> dict[str, UUID]:
    slugs = sorted({feed['category'] for feed in NEWS_SOURCES})
    response = (admin_supabase.table('categories').select('id,slug')
                .in_('slug', slugs).eq('active', True).execute())
    resolved = {row['slug']: UUID(row['id']) for row in response.data or []}
    if set(resolved) != set(slugs):
        raise RuntimeError('Configured categories are missing or inactive')
    return resolved
