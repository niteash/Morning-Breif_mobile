from pathlib import Path

from app.lib.supabase import admin_supabase


BUCKET_NAME = "briefings"


def upload_briefing_audio(
    file_path: str,
    storage_path: str,
) -> str:

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
            f"Signed URL was not returned: {response}"
        )

    return signed_url