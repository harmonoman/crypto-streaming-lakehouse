"""
tests/integration/test_dashboard_export.py

Validates the Metabase dashboard export file.
"""
import json
from pathlib import Path

EXPORT_PATH = Path("metabase/dashboard_export.json")
DOCS_PATH   = Path("docs/metabase_setup.md")


def test_export_file_exists():
    assert EXPORT_PATH.exists(), f"Expected export at {EXPORT_PATH}"


def test_export_is_valid_json():
    data = json.loads(EXPORT_PATH.read_text())
    assert isinstance(data, dict)


def test_export_has_dashboard_structure():
    data = json.loads(EXPORT_PATH.read_text())
    assert "name" in data
    assert "dashcards" in data
    assert len(data["dashcards"]) >= 4


def test_export_has_no_credentials():
    raw = EXPORT_PATH.read_text().lower()
    for pattern in ["password", "secret", "api_key", "postgresql://", "amqp://"]:
        assert pattern not in raw, f"Found sensitive pattern '{pattern}' in export"


def test_docs_mention_export_file():
    content = DOCS_PATH.read_text()
    assert "dashboard_export.json" in content
