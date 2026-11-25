"""User-owned saved articles; deployment requires the reviewed bookmark schema."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from app.dependencies.auth import get_current_user
from app.lib.supabase import create_supabase_client

router = APIRouter(prefix='/api/v1/bookmarks', tags=['Bookmarks'])


@router.get('')
def list_bookmarks(offset: int = Query(0, ge=0, le=10000), limit: int = Query(20, ge=1, le=50),
                   current_user: dict = Depends(get_current_user)):
    try:
        rows = (create_supabase_client(current_user['access_token']).table('article_bookmarks')
                .select('article_id,created_at,article:news_items(id,category_id,source,title,description,url,image_url,author,published_at,created_at)')
                .eq('user_id', current_user['user_id']).order('created_at', desc=True)
                .order('article_id', desc=True).range(offset, offset + limit).execute().data or [])
        return {'bookmarks': rows[:limit], 'next_offset': offset + limit if len(rows) > limit and offset + limit <= 10000 else None}
    except Exception:
        raise HTTPException(503, 'Saved articles are temporarily unavailable') from None


@router.get('/{article_id}')
def bookmark_state(article_id: UUID, current_user: dict = Depends(get_current_user)):
    try:
        rows = (create_supabase_client(current_user['access_token']).table('article_bookmarks')
                .select('article_id').eq('user_id', current_user['user_id'])
                .eq('article_id', str(article_id)).limit(1).execute().data or [])
        return {'saved': bool(rows)}
    except Exception:
        raise HTTPException(503, 'Saved articles are temporarily unavailable') from None


@router.put('/{article_id}')
def save_bookmark(article_id: UUID, current_user: dict = Depends(get_current_user)):
    try:
        create_supabase_client(current_user['access_token']).table('article_bookmarks').upsert(
            {'user_id': current_user['user_id'], 'article_id': str(article_id)},
            on_conflict='user_id,article_id', ignore_duplicates=True).execute()
        return {'saved': True}
    except Exception:
        raise HTTPException(503, 'Could not save this article') from None


@router.delete('/{article_id}')
def remove_bookmark(article_id: UUID, current_user: dict = Depends(get_current_user)):
    try:
        (create_supabase_client(current_user['access_token']).table('article_bookmarks').delete()
         .eq('user_id', current_user['user_id']).eq('article_id', str(article_id)).execute())
        return {'saved': False}
    except Exception:
        raise HTTPException(503, 'Could not remove this saved article') from None
