import logging

from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from scholarag.app.config import Settings
from scholarag.app.dependencies import get_settings
from scholarag.app.main import app


def test_settings_endpoint(app_client):
    custom_settings = Settings(
        db={
            "db_type": "opensearch",
            "index_paragraphs": "foo",
            "index_journals": "bar",
            "host": "host.com",
            "port": 7777,
        }
    )
    app.dependency_overrides[get_settings] = lambda: custom_settings

    response = app_client.get("/settings")
    assert response.json() == custom_settings.model_dump(mode="json")


def test_startup(caplog, monkeypatch):
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("SCHOLARAG__DB__DB_TYPE", "opensearch")
    monkeypatch.setenv("SCHOLARAG__DB__INDEX_PARAGRAPHS", "amazing")
    monkeypatch.setenv("SCHOLARAG__DB__INDEX_JOURNALS", "amazing_journals")
    monkeypatch.setenv("SCHOLARAG__DB__HOST", "http://www.example.com")
    monkeypatch.setenv("SCHOLARAG__DB__PORT", "1234")
    monkeypatch.setenv("SCHOLARAG__REDIS__HOST", "greathost.ch")
    monkeypatch.setenv("SCHOLARAG__REDIS__PORT", "6789")
    monkeypatch.setenv("SCHOLARAG__LOGGING__LEVEL", "debug")
    monkeypatch.setenv("SCHOLARAG__LOGGING__EXTERNAL_PACKAGES", "critical")
    monkeypatch.setenv(
        "SCHOLARAG__MISC__CORS_ORIGINS", "http://greatcors.com, https://badcors.org"
    )

    # The with statement triggers the startup.
    with TestClient(app) as test_client:
        test_client.get("/healthz")
    assert caplog.record_tuples[0][::2] == (
        "scholarag.app.dependencies",
        "Reading the environment and instantiating settings",
    )
    assert caplog.record_tuples[1][::2] == (
        "scholarag.app.middleware",
        "The caching service is disabled.",
    )

    assert (
        logging.getLevelName(logging.getLogger("scholarag").getEffectiveLevel())
        == "DEBUG"
    )
    assert logging.getLevelName(logging.getLogger("app").getEffectiveLevel()) == "DEBUG"
    assert (
        logging.getLevelName(logging.getLogger("httpx").getEffectiveLevel())
        == "CRITICAL"
    )
    assert (
        logging.getLevelName(logging.getLogger("fastapi").getEffectiveLevel())
        == "CRITICAL"
    )
    assert (
        logging.getLevelName(logging.getLogger("elasticsearch").getEffectiveLevel())
        == "CRITICAL"
    )
    assert filter(
        lambda x: x.__dict__["cls"] == CORSMiddleware, app.user_middleware
    ).__next__().kwargs["allow_origins"] == [
        "http://greatcors.com",
        "https://badcors.org",
    ]
