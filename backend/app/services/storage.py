from pathlib import Path
from uuid import UUID
from app.services.account_deletion import account_is_active

from app.lib.supabase import admin_supabase


BUCKET_NAME = "briefings"


def upload_briefing_audio(
    file_path: str,
    storage_path: str,
) -> str:

    user_id = str(UUID(storage_path.split('/')[0]))
    if not account_is_active(user_id):
        raise RuntimeError("Account is unavailable")
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Audio file not found: {file_path}"
        )

    with path.open("rb") as audio_file:
        file_bytes = audio_file.read()

    admin_supabase.storage.from_(
        BUCKET_NAME
    ).upload(
        storage_path,
        file_bytes,
        {
            "content-type": "audio/mpeg",
            "upsert": "true",
        },
    )

    try:
        if not account_is_active(user_id):
            raise RuntimeError("Account became unavailable during upload")
    except Exception:
        # Remove the newly uploaded object if deletion started or verification failed.
        admin_supabase.storage.from_(BUCKET_NAME).remove([storage_path])
        raise
    return storage_path


def create_briefing_signed_url(
    storage_path: str,
    expires_in: int = 3600,
) -> str:

    response = (
        admin_supabase
        .storage
        .from_(BUCKET_NAME)
        .create_signed_url(
            storage_path,
            expires_in,
        )
    )

    if not response:
        raise RuntimeError(
            "Failed to create signed audio URL"
        )

    signed_url = response.get("signedURL")

    if not signed_url:
        raise RuntimeError(
            "Signed URL was not returned"
        )

    return signed_url
