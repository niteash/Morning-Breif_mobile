import os
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = os.getenv(
    "SUPABASE_PUBLISHABLE_KEY"
)
SUPABASE_SERVICE_ROLE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY"
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing")

if urlparse(SUPABASE_URL).hostname in {"your-project.supabase.co", "example.supabase.co"}:
    raise RuntimeError(
        "SUPABASE_URL is still a placeholder. Configure a real environment or "
        "start local staging with backend/scripts/run_staging.py."
    )

if not SUPABASE_PUBLISHABLE_KEY:
    raise RuntimeError(
        "SUPABASE_PUBLISHABLE_KEY is missing"
    )

if not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError(
        "SUPABASE_SERVICE_ROLE_KEY is missing"
    )

# Generation validates its provider credential lazily. Preferences, Auth, news and
# saved audio remain available when AI generation has not yet been configured.
