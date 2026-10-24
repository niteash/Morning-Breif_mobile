from fastapi import Header, HTTPException

from app.lib.supabase import admin_supabase


async def get_current_user(
    authorization: str | None = Header(default=None),
):
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header is missing",
        )

    scheme, separator, token = authorization.partition(" ")

    if not separator or scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header",
        )

    token = token.strip()

    try:
        # Ask Supabase Auth to validate the access token.
        response = admin_supabase.auth.get_user(token)
        user = response.user

        if not user or not user.id:
            raise HTTPException(
                status_code=401,
                detail="Invalid access token",
            )

        return {
            "user_id": str(user.id),
            "access_token": token,
        }

    except HTTPException:
        raise

    except Exception:
        # Do not expose authentication internals or token contents.
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token",
        )