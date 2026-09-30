import os

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

if not SUPABASE_PUBLISHABLE_KEY:
    raise RuntimeError(
        "SUPABASE_PUBLISHABLE_KEY is missing"
    )

if not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError(
        "SUPABASE_SERVICE_ROLE_KEY is missing"
    )

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing"
    )