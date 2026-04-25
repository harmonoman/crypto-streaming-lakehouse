"""
tests/unit/test_sync_metabase.py

Unit tests for sync_metabase_schema() in dags/metabase_sync.py.
All HTTP calls are mocked — no live Metabase required.
"""

from unittest.mock import MagicMock, patch

from metabase_sync import sync_metabase_schema


def _make_mocks(token="test-token-123"):
    mock_session = MagicMock()
    mock_session.json.return_value = {"id": token}
    mock_session.raise_for_status = MagicMock()
    mock_sync = MagicMock()
    mock_sync.raise_for_status = MagicMock()
    return mock_session, mock_sync


_ENV = {
    "METABASE_URL":            "http://metabase:3000",
    "METABASE_ADMIN_EMAIL":    "admin@test.com",
    "METABASE_ADMIN_PASSWORD": "testpass",
    "METABASE_DATABASE_ID":    "2",
}


# ── Test 1 — Auth call made ───────────────────────────────────────────────────

def test_sync_makes_auth_request():
    mock_session, mock_sync = _make_mocks()
    with patch("requests.post", side_effect=[mock_session, mock_sync]) as mock_post, \
         patch.dict("os.environ", _ENV):
        sync_metabase_schema()
    first_call = mock_post.call_args_list[0]
    assert "/api/session" in first_call[0][0]
    assert first_call[1]["json"]["username"] == "admin@test.com"
    assert first_call[1]["json"]["password"] == "testpass"


# ── Test 2 — Schema sync call made ───────────────────────────────────────────

def test_sync_makes_schema_sync_request():
    mock_session, mock_sync = _make_mocks()
    with patch("requests.post", side_effect=[mock_session, mock_sync]) as mock_post, \
         patch.dict("os.environ", _ENV):
        sync_metabase_schema()
    second_call = mock_post.call_args_list[1]
    assert "sync_schema" in second_call[0][0]
    assert "2" in second_call[0][0]


# ── Test 3 — Uses environment variables ──────────────────────────────────────

def test_sync_uses_env_vars():
    mock_session, mock_sync = _make_mocks()
    env = {**_ENV, "METABASE_URL": "http://custom:9000", "METABASE_DATABASE_ID": "5"}
    with patch("requests.post", side_effect=[mock_session, mock_sync]) as mock_post, \
         patch.dict("os.environ", env):
        sync_metabase_schema()
    assert "custom:9000" in mock_post.call_args_list[0][0][0]
    assert "5" in mock_post.call_args_list[1][0][0]


# ── Test 4 — Handles auth failure gracefully ─────────────────────────────────

def test_sync_handles_auth_failure():
    mock_session = MagicMock()
    mock_session.json.return_value = {}  # no token
    mock_session.raise_for_status = MagicMock()
    with patch("requests.post", return_value=mock_session), \
         patch.dict("os.environ", _ENV):
        sync_metabase_schema()  # must not raise


# ── Test 5 — Correct session header used ─────────────────────────────────────

def test_sync_uses_session_header():
    mock_session, mock_sync = _make_mocks(token="my-session-token")
    with patch("requests.post", side_effect=[mock_session, mock_sync]) as mock_post, \
         patch.dict("os.environ", _ENV):
        sync_metabase_schema()
    headers = mock_post.call_args_list[1][1].get("headers", {})
    assert "X-Metabase-Session" in headers
    assert headers["X-Metabase-Session"] == "my-session-token"
