from fastapi import Header, HTTPException
import jwt


async def get_current_user(
    authorization: str | None = Header(default=None),
):
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header is missing",
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header",
        )

    token = authorization.replace("Bearer ", "", 1)

    try:
        payload = jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_exp": True,
            },
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Access token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid access token",
        )

    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="User ID not found in token",
        )

    return {
        "user_id": user_id,
        "access_token": token,
    }