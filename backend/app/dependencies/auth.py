import asyncio
import base64
import json
import hashlib
import logging
import random
import re
import time
import uuid
import weakref
import httpx
from fastapi import Depends, Header, HTTPException, Request
from supabase_auth.errors import AuthApiError, AuthError, AuthInvalidJwtError, AuthRetryableError
from app.services.account_deletion import account_is_active

from app.lib.supabase import admin_supabase

logger = logging.getLogger(__name__)
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,80}$")
_verification_tasks = weakref.WeakKeyDictionary()
_verification_cache = weakref.WeakKeyDictionary()
_active_account_tasks = weakref.WeakKeyDictionary()
_active_account_cache = weakref.WeakKeyDictionary()
MAX_INFLIGHT_VERIFICATIONS = 32
MAX_CACHED_VERIFICATIONS = 256
MAX_CACHED_ACCOUNT_CHECKS = 1024
VERIFICATION_CACHE_TTL_SECONDS = 30
ACCOUNT_ACTIVE_CACHE_TTL_SECONDS = 5


def _transport_category(error: Exception | None) -> str:
    if isinstance(error, httpx.PoolTimeout):
        return "connection_pool_timeout"
    if isinstance(error, (httpx.TimeoutException, TimeoutError)):
        return "network_timeout"
    if isinstance(error, httpx.ReadError):
        return "network_read_failure"
    if isinstance(error, httpx.ConnectError):
        return "network_connect_failure"
    if isinstance(error, httpx.RemoteProtocolError):
        return "remote_protocol_failure"
    return "other"


async def _verify_remote(token: str, request_id: str, route: str, expiry: str):
    for attempt in range(2):
        try:
            # supabase-auth returns a TypedDict from get_claims. Modern JWTs are
            # verified locally after its signing key is fetched and cached.
            return await asyncio.to_thread(admin_supabase.auth.get_claims, token)
        except (httpx.NetworkError, httpx.RemoteProtocolError,
                httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout) as error:
            if attempt:
                raise
            # JWKS retrieval is read-only. Never retry credential rejection,
            # rate limits, pool exhaustion or arbitrary provider failures here.
            logger.warning(
                "Authentication retry request_id=%s route=%s token_expiry=%s "
                "transport_category=%s error_type=%s attempt=2",
                request_id, route, expiry, _transport_category(error), type(error).__name__,
            )
            await asyncio.sleep(random.uniform(0.05, 0.15))


async def _verify_shared(token: str, request_id: str, route: str, expiry: str):
    loop = asyncio.get_running_loop()
    pending = _verification_tasks.setdefault(loop, {})
    verified = _verification_cache.setdefault(loop, {})
    key = hashlib.sha256(token.encode()).digest()
    cached = verified.get(key)
    now = loop.time()
    if cached and cached[0] > now:
        return cached[1]
    if cached:
        verified.pop(key, None)

    task = pending.get(key)
    if task is None or task.done():
        if task is None and len(pending) >= MAX_INFLIGHT_VERIFICATIONS:
            raise httpx.PoolTimeout("Authentication verification capacity reached")
        task = loop.create_task(_verify_remote(token, request_id, route, expiry))
        pending[key] = task

        def finished(completed):
            if pending.get(key) is completed:
                pending.pop(key, None)
            # A disconnected waiter must not leave an unobserved exception.
            if completed.cancelled():
                return
            error = completed.exception()
            if error is None:
                # Publish success before newly arriving requests can start an
                # unnecessary second verification task.
                verified[key] = (
                    loop.time() + VERIFICATION_CACHE_TTL_SECONDS,
                    completed.result(),
                )

        task.add_done_callback(finished)
    # Cancellation of one HTTP request must not cancel other callers' check.
    response = await asyncio.shield(task)
    verified[key] = (loop.time() + VERIFICATION_CACHE_TTL_SECONDS, response)
    if len(verified) > MAX_CACHED_VERIFICATIONS:
        expired = [cache_key for cache_key, (deadline, _) in verified.items() if deadline <= loop.time()]
        for cache_key in expired:
            verified.pop(cache_key, None)
        while len(verified) > MAX_CACHED_VERIFICATIONS:
            verified.pop(next(iter(verified)))
    return response


def _auth_context(request: Request) -> tuple[str, str]:
    request_id = request.headers.get("x-request-id", "")
    if not REQUEST_ID_RE.fullmatch(request_id):
        request_id = uuid.uuid4().hex
    route = getattr(request.scope.get("route"), "path", request.url.path)
    return request_id, route


def _token_expiry_state(token: str | None) -> str:
    if not token:
        return "not_available"
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
        expires_at = float(claims["exp"])
    except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return "unparseable"
    remaining = expires_at - time.time()
    if remaining <= 0:
        return "expired"
    if remaining <= 60:
        return "expiring"
    return "valid"


def _log_auth_failure(request_id: str, route: str, category: str, expiry: str, error: Exception | None = None):
    logger.warning(
        "Authentication failure request_id=%s route=%s category=%s token_expiry=%s error_type=%s transport_category=%s",
        request_id, route, category, expiry, type(error).__name__ if error else "none", _transport_category(error),
    )


def _cache_account_status(cache: dict, loop, user_id: str, active: bool) -> None:
    cache[user_id] = (loop.time() + ACCOUNT_ACTIVE_CACHE_TTL_SECONDS, active)
    if len(cache) <= MAX_CACHED_ACCOUNT_CHECKS:
        return
    now = loop.time()
    for cached_user, (deadline, _) in list(cache.items()):
        if deadline <= now:
            cache.pop(cached_user, None)
    while len(cache) > MAX_CACHED_ACCOUNT_CHECKS:
        cache.pop(next(iter(cache)))


async def get_verified_user(
    request: Request,
    authorization: str | None = Header(default=None),
):
    request_id, route = _auth_context(request)
    if not authorization:
        _log_auth_failure(request_id, route, "missing_authorization", "not_available")
        raise HTTPException(
            status_code=401,
            detail="Authorization header is missing",
        )

    scheme, separator, token = authorization.partition(" ")

    if not separator or scheme.lower() != "bearer" or not token.strip():
        _log_auth_failure(request_id, route, "malformed_authorization", "not_available")
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header",
        )

    token = token.strip()
    if any(character.isspace() for character in token):
        _log_auth_failure(request_id, route, "malformed_authorization", "unparseable")
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    expiry = _token_expiry_state(token)

    try:
        # Ask Supabase Auth to validate the access token and return its claims.
        response = await _verify_shared(token, request_id, route, expiry)
        claims = response.get("claims") if isinstance(response, dict) else None
        user_id = claims.get("sub") if isinstance(claims, dict) else None

        if (not isinstance(user_id, str) or not user_id
                or claims.get("is_anonymous") is True):
            _log_auth_failure(request_id, route, "token_rejected", expiry)
            raise HTTPException(
                status_code=401,
                detail="Invalid access token",
            )

        try:
            user_id = str(uuid.UUID(user_id))
        except ValueError:
            _log_auth_failure(request_id, route, "token_rejected", expiry)
            raise HTTPException(status_code=401, detail="Invalid access token") from None

        return {
            "user_id": user_id,
            "access_token": token,
        }

    except HTTPException:
        raise

    except AuthInvalidJwtError as error:
        _log_auth_failure(request_id, route, "token_rejected", expiry, error)
        raise HTTPException(status_code=401, detail="Invalid or expired access token") from None
    except AuthApiError as error:
        status = error.status
        category = "token_rejected" if status in {401, 403} else "auth_provider_unavailable"
        _log_auth_failure(request_id, route, category, expiry, error)
        if status == 401:
            raise HTTPException(status_code=401, detail="Invalid or expired access token") from None
        if status == 403:
            raise HTTPException(status_code=403, detail="Access token is not authorized") from None
        # Provider rate limits and server/client failures are not invalid credentials.
        raise HTTPException(status_code=503, detail="Authentication service is temporarily unavailable") from None
    except (AuthRetryableError, httpx.TransportError, TimeoutError) as error:
        _log_auth_failure(request_id, route, "auth_provider_unavailable", expiry, error)
        raise HTTPException(status_code=503, detail="Authentication service is temporarily unavailable") from None
    except AuthError as error:
        _log_auth_failure(request_id, route, "auth_provider_error", expiry, error)
        raise HTTPException(status_code=503, detail="Authentication service is temporarily unavailable") from None
    except Exception as error:
        # Do not expose exception text, request headers, tokens, or provider payloads.
        _log_auth_failure(request_id, route, "auth_provider_unexpected_error", expiry, error)
        raise HTTPException(status_code=503, detail="Authentication service is temporarily unavailable") from None


async def get_current_user(user: dict = Depends(get_verified_user)):
    loop = asyncio.get_running_loop()
    pending = _active_account_tasks.setdefault(loop, {})
    cached = _active_account_cache.setdefault(loop, {})
    user_id = user['user_id']
    cached_result = cached.get(user_id)
    now = loop.time()
    if cached_result and cached_result[0] > now:
        active = cached_result[1]
    else:
        cached.pop(user_id, None)
        task = pending.get(user_id)
        if task is None or task.done():
            async def check_account():
                for attempt in range(2):
                    try:
                        return await asyncio.to_thread(account_is_active, user_id)
                    except (httpx.TransportError, TimeoutError):
                        if attempt:
                            raise
                        await asyncio.sleep(random.uniform(0.05, 0.15))

            task = loop.create_task(check_account())
            pending[user_id] = task

            def finished(completed):
                if pending.get(user_id) is completed:
                    pending.pop(user_id, None)
                if completed.cancelled():
                    return
                error = completed.exception()
                if error is None:
                    _cache_account_status(cached, loop, user_id, completed.result())

            task.add_done_callback(finished)
        try:
            active = await asyncio.shield(task)
        except Exception as error:
            logger.warning(
                "Account verification failure error_type=%s transport_category=%s",
                type(error).__name__, _transport_category(error),
            )
            raise HTTPException(status_code=503, detail="Account verification is temporarily unavailable") from None
        _cache_account_status(cached, loop, user_id, active)

    if not active:
        raise HTTPException(status_code=403, detail="Account deletion has been requested")
    return user
