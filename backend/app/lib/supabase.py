from collections.abc import Iterator
from contextlib import contextmanager

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


@contextmanager
def isolated_admin_supabase_client() -> Iterator[Client]:
    """Provide a short-lived admin client for a background worker thread."""
    client = create_admin_supabase_client()
    try:
        yield client
    finally:
        # Avoid creating unused connection pools while cleaning up.
        postgrest = getattr(client, "_postgrest", None)
        if postgrest is not None:
            postgrest.aclose()
        client.auth.close()


supabase: Client = create_supabase_client()

admin_supabase: Client = create_admin_supabase_client()
