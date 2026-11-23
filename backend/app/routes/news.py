from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

from app.dependencies.auth import get_current_user
from app.lib.supabase import create_supabase_client


router = APIRouter(
    prefix="/api/v1/news",
    tags=["News"],
)


class StoryFeedbackRequest(BaseModel):
    action: Literal['more_like_this','less_like_this','hide_topic','hide_publisher','report_incorrect']
    reason: str | None = Field(default=None, max_length=500)


@router.put('/{article_id}/feedback')
def set_story_feedback(article_id: UUID, payload: StoryFeedbackRequest,
                       current_user: dict = Depends(get_current_user)):
    try:
        row = {'user_id': current_user['user_id'], 'story_id': str(article_id),
               'action': payload.action, 'reason': payload.reason}
        saved = (create_supabase_client(current_user['access_token'])
                 .table('story_feedback').upsert(row, on_conflict='user_id,story_id,action')
                 .execute().data or [])
        if not saved:
            raise RuntimeError('Feedback was not saved')
        return {'saved': True}
    except Exception:
        raise HTTPException(503, 'Feedback is temporarily unavailable') from None


@router.get("")
async def get_news(
    category_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    access_token = current_user["access_token"]

    supabase = create_supabase_client(access_token)
    try:
        feedback = (supabase.table('story_feedback')
                    .select('story_id,action,news_items(category_id,source)')
                    .eq('user_id', user_id).execute().data or [])
    except Exception:
        feedback = []
    hidden_topics = {str((row.get('news_items') or {}).get('category_id')) for row in feedback
                     if row.get('action') == 'hide_topic'}
    hidden_publishers = {(row.get('news_items') or {}).get('source', '').casefold().strip()
                         for row in feedback if row.get('action') == 'hide_publisher'}
    preferred = {str(row.get('story_id')) for row in feedback if row.get('action') == 'more_like_this'}

    def personalized(rows):
        visible = [row for row in rows if str(row.get('category_id')) not in hidden_topics
                   and (row.get('source') or '').casefold().strip() not in hidden_publishers]
        visible.sort(key=lambda row: str(row.get('id')) not in preferred)
        return visible[:limit]

    # If a specific category is requested,
    # return only that category.
    if category_id:
        response = (
            supabase
            .table("news_items")
            .select(
                """
                id,
                category_id,
                source,
                title,
                description,
                url,
                image_url,
                author,
                published_at,
                created_at
                """
            )
            .eq("category_id", str(category_id))
            .order("published_at", desc=True, nullsfirst=False)
            .order("id", desc=True)
            .limit(min(100, limit * 4))
            .execute()
        )

        return {
            "news": personalized(response.data or []),
        }

    # Get the categories selected by this user.
    user_categories_response = (
        supabase
        .table("user_categories")
        .select("category_id")
        .eq("user_id", user_id)
        .execute()
    )

    selected_category_ids = [
        row["category_id"]
        for row in user_categories_response.data
    ]

    if not selected_category_ids:
        return {
            "news": [],
        }

    # Get news belonging to selected categories.
    response = (
        supabase
        .table("news_items")
        .select(
            """
            id,
            category_id,
            source,
            title,
            description,
            url,
            image_url,
            author,
            published_at,
            created_at
            """
        )
        .in_("category_id", selected_category_ids)
        .order("published_at", desc=True, nullsfirst=False)
        .order("id", desc=True)
        .limit(min(100, limit * 4))
        .execute()
    )

    return {
        "news": personalized(response.data or []),
    }


# Discovery is explicit: the existing /news route remains personalized.
@router.get('/discover')
def discover_news(q: str = Query(default='', max_length=120),
                  category_id: UUID | None = None,
                  selected_only: bool = False,
                  offset: int = Query(default=0, ge=0, le=10000),
                  limit: int = Query(default=20, ge=1, le=50),
                  current_user: dict = Depends(get_current_user)):
    from fastapi import HTTPException
    term = q.strip()
    if any(ord(char) < 32 for char in term):
        raise HTTPException(422, 'Invalid search text')
    try:
        db = create_supabase_client(current_user['access_token'])
        query = db.table('news_items').select('id,category_id,source,title,description,url,image_url,author,published_at,created_at')
        if selected_only:
            selected_rows = (db.table('user_categories').select('category_id')
                             .eq('user_id', current_user['user_id']).execute().data or [])
            selected_ids = [str(row['category_id']) for row in selected_rows if row.get('category_id')]
            if not selected_ids or (category_id and str(category_id) not in selected_ids):
                return {'news': [], 'next_offset': None}
            query = query.in_('category_id', selected_ids)
        if category_id:
            query = query.eq('category_id', str(category_id))
        if term:
            # A bound single-column filter, never raw OR/SQL from the client.
            literal = term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            query = query.ilike('title', '%' + literal + '%')
        rows = query.order('published_at', desc=True, nullsfirst=False).order('id', desc=True).range(offset, offset + limit).execute().data or []
        return {'news': rows[:limit], 'next_offset': offset + limit if len(rows) > limit and offset + limit <= 10000 else None}
    except Exception:
        raise HTTPException(503, 'News search is temporarily unavailable') from None


@router.get('/{article_id}')
def get_article(article_id: UUID, current_user: dict = Depends(get_current_user)):
    from fastapi import HTTPException
    try:
        rows = create_supabase_client(current_user['access_token']).table('news_items').select(
            'id,category_id,source,title,description,url,image_url,author,published_at,created_at'
        ).eq('id', str(article_id)).limit(1).execute().data or []
    except Exception:
        raise HTTPException(503, 'Article is temporarily unavailable') from None
    if not rows:
        raise HTTPException(404, 'Article is no longer available')
    return {'article': rows[0]}
