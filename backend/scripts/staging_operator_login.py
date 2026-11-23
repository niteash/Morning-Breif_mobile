
#!/usr/bin/env python3
"""
Nay Thit — Staging RSS Operator Login

Authenticates an existing staging Supabase user and securely
saves RSS_IMPORT_ACCESS_TOKEN to backend/.env.staging.

Security:
- Staging project only
- Password input is hidden
- Access tokens are never printed
- Passwords and refresh tokens are never saved
- HTTPS certificate verification uses certifi
- Verifies the expected Supabase user ID
- Protects the environment file with owner-only permissions
"""

import getpass
import json
import os
import ssl
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi


# ============================================================
# STAGING CONFIGURATION
# ============================================================

STAGING_PROJECT_ID = "wwtntxknfjagdjdgiaxu"

STAGING_SUPABASE_URL = (
    f"https://{STAGING_PROJECT_ID}.supabase.co"
)

OPERATOR_EMAIL = "test@gmail.com"

EXPECTED_USER_ID = (
    "e726b864-c879-4b8f-9ac1-c5cb73ae8a58"
)

BACKEND_DIR = Path(__file__).resolve().parents[1]

ENV_FILE = BACKEND_DIR / ".env.staging"

TOKEN_VARIABLE = "RSS_IMPORT_ACCESS_TOKEN"

REQUEST_TIMEOUT = 20


# ============================================================
# SSL CONFIGURATION
# ============================================================

def create_ssl_context():
    """Create a certificate-verifying HTTPS context."""
    return ssl.create_default_context(
        cafile=certifi.where()
    )


# ============================================================
# SUPABASE AUTHENTICATION
# ============================================================

def login_to_supabase(api_key, password):
    """Authenticate the staging operator via Supabase Auth."""

    endpoint = (
        f"{STAGING_SUPABASE_URL}"
        "/auth/v1/token?grant_type=password"
    )

    payload = {
        "email": OPERATOR_EMAIL,
        "password": password,
    }

    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "apikey": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    ssl_context = create_ssl_context()

    try:
        with urlopen(
            request,
            context=ssl_context,
            timeout=REQUEST_TIMEOUT,
        ) as response:
            return json.load(response)

    except HTTPError as error:
        print(
            f"Authentication request failed "
            f"(HTTP {error.code})."
        )
        raise SystemExit(1)

    except URLError as error:
        print(
            "HTTPS connection failed:",
            type(error.reason).__name__,
        )
        raise SystemExit(1)

    except (TimeoutError, OSError):
        print("Network connection timed out or failed.")
        raise SystemExit(1)


# ============================================================
# VERIFY OPERATOR IDENTITY
# ============================================================

def verify_operator(session):
    """Ensure the session belongs to the approved staging user."""

    user = session.get("user") or {}

    user_id = user.get("id")
    user_email = user.get("email", "").lower()

    token = session.get("access_token")

    if user_id != EXPECTED_USER_ID:
        raise SystemExit(
            "ERROR: Unexpected Supabase user ID."
        )

    if user_email != OPERATOR_EMAIL.lower():
        raise SystemExit(
            "ERROR: Unexpected operator email."
        )

    if not isinstance(token, str) or not token:
        raise SystemExit(
            "ERROR: Missing access token."
        )

    return token


# ============================================================
# SAVE ACCESS TOKEN
# ============================================================

def save_access_token(token):
    """
    Update the staging environment file.

    Preserves other environment variables and replaces any
    existing RSS_IMPORT_ACCESS_TOKEN entry.

    Writes through a protected temporary file and atomically
    replaces the destination.
    """

    if not ENV_FILE.is_file():
        raise SystemExit(
            "ERROR: backend/.env.staging does not exist."
        )

    if ENV_FILE.is_symlink():
        raise SystemExit(
            "ERROR: Refusing to write to a symlink."
        )

    existing_lines = ENV_FILE.read_text(
        encoding="utf-8"
    ).splitlines()

    updated_lines = [
        line
        for line in existing_lines
        if not line.strip().startswith(
            TOKEN_VARIABLE + "="
        )
    ]

    updated_lines.append(
        f"{TOKEN_VARIABLE}={token}"
    )

    updated_content = (
        "\n".join(updated_lines) + "\n"
    )

    temporary_path = None

    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".env.staging.",
            dir=str(ENV_FILE.parent),
            text=True,
        )

        temporary_path = Path(temporary_name)

        os.fchmod(descriptor, 0o600)

        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
        ) as file:
            file.write(updated_content)
            file.flush()
            os.fsync(file.fileno())

        os.replace(
            temporary_path,
            ENV_FILE,
        )

        ENV_FILE.chmod(0o600)

    finally:
        if (
            temporary_path is not None
            and temporary_path.exists()
        ):
            temporary_path.unlink()


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 52)
    print("NAY THIT — STAGING RSS OPERATOR LOGIN")
    print("=" * 52)

    print()
    print("Project:", STAGING_PROJECT_ID)
    print("Account:", OPERATOR_EMAIL)
    print("Environment:", "STAGING ONLY")

    print()

    if not ENV_FILE.is_file():
        print(
            "ERROR: Staging environment file missing."
        )
        print("Expected:", ENV_FILE)
        return 1

    print("Enter your staging Supabase credentials.")
    print("Input will not be displayed.")
    print()

    api_key = getpass.getpass(
        "Supabase staging publishable key: "
    ).strip()

    if not api_key:
        print("ERROR: Publishable key is required.")
        return 1

    if not (
        api_key.startswith("sb_publishable_")
        or (
            api_key.count(".") == 2
            and api_key.startswith("eyJ")
        )
    ):
        print(
            "ERROR: Use a Supabase publishable "
            "or legacy anon key, not a secret key."
        )
        return 1

    password = getpass.getpass(
        f"Password for {OPERATOR_EMAIL}: "
    )

    if not password:
        print("ERROR: Password is required.")
        return 1

    print()
    print("Authenticating with staging Supabase...")

    session = login_to_supabase(
        api_key,
        password,
    )

    token = verify_operator(session)

    save_access_token(token)

    print()
    print("=" * 52)
    print("SUCCESS")
    print("=" * 52)

    print()
    print("Staging operator authenticated.")
    print("Expected user ID verified.")
    print("RSS_IMPORT_ACCESS_TOKEN saved securely.")
    print("Environment file permissions: 600")

    expires_in = session.get("expires_in")

    if isinstance(expires_in, (int, float)):
        print(
            "Token lifetime:",
            int(expires_in),
            "seconds",
        )

    print()
    print("No access token or password was printed.")
    print()
    print(
        "NOTE: Authentication does not grant "
        "database INSERT permission by itself."
    )
    print(
        "Verify the operator-specific RLS policy "
        "before importing news."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
