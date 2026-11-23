"""Operator-only ingestion. Never grant privileges from user-editable metadata."""
import os

from fastapi import Depends, HTTPException

from app.dependencies.auth import get_current_user


def require_operator(current_user: dict = Depends(get_current_user)) -> dict:
    allowed = {
        value.strip()
        for value in os.getenv("INGESTION_OPERATOR_IDS", "").split(",")
        if value.strip()
    }
    if current_user["user_id"] not in allowed:
        raise HTTPException(status_code=403, detail="Operator access required")
    return current_user
