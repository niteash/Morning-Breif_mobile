from supabase import Client, create_client

from app.config import (
    SUPABASE_URL,
    SUPABASE_PUBLISHABLE_KEY,
    SUPABASE_SERVICE_ROLE_KEY,
)


def create_supabase_client(
    access_token: str | None = None,
) -> Client:
    client = create_client(
        SUPABASE_URL,
        SUPABASE_PUBLISHABLE_KEY,
    )

    if access_token:
        client.postgrest.auth(access_token)

    return client


def create_admin_supabase_client() -> Client:
    return create_client(
        SUPABASE_URL,
        SUPABASE_SERVICE_ROLE_KEY,
    )


supabase: Client = create_supabase_client()

admin_supabase: Client = create_admin_supabase_client()