"""Offline tests must never inherit local service credentials or make network calls."""
import os
import socket

import pytest

os.environ.update({
    "SUPABASE_URL": "https://offline-test.supabase.co",
    "SUPABASE_PUBLISHABLE_KEY": "offline-publishable-key",
    "SUPABASE_SERVICE_ROLE_KEY": "offline-service-role-key",
    "GEMINI_API_KEY": "offline-gemini-key",
    "SCHEDULER_ENABLED": "false",
    "ACCOUNT_DELETION_ENABLED": "false",
    "ACCOUNT_DELETION_WORKER_ENABLED": "false",
    "PUSH_DELIVERY_ENABLED": "false",
    "NEWS_INGESTION_ENABLED": "false",
    "PYTHON_DOTENV_DISABLED": "1",
    "INGESTION_OPERATOR_IDS": "",
    "RSS_IMPORT_ACCESS_TOKEN": "fixture-authenticated-operator-jwt",
    "RSS_IMPORT_RLS_POLICY_VERIFIED": "false",
})


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Network access is forbidden in offline tests")
    monkeypatch.setattr(socket.socket, "connect", blocked)
