from pathlib import Path

from app.lib.supabase import admin_supabase


BUCKET_NAME = "briefing-audio"


def upload_audio(
    file_path: str,
    storage_path: str,
) -> str:

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Audio file not found: {file_path}"
        )

    audio_bytes = path.read_bytes()

    admin_supabase.storage.from_(
        BUCKET_NAME
    ).upload(
        storage_path,
        audio_bytes,
        {
            "content-type": "audio/mpeg",
            "upsert": "true",
        },
    )

    return storage_path


def create_signed_audio_url(
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

    return response["signedURL"]