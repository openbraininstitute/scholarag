import pytest
from pydantic import ValidationError
from scholarag.app.config import Settings


def test_required(monkeypatch):
    # We get an error when no custom variables provided
    with pytest.raises(ValidationError):
        Settings()

    monkeypatch.setenv("SCHOLARAG__DB__DB_TYPE", "opensearch")
    monkeypatch.setenv("SCHOLARAG__DB__INDEX_PARAGRAPHS", "amazing")
    monkeypatch.setenv("SCHOLARAG__DB__INDEX_JOURNALS", "amazing_journals")
    monkeypatch.setenv("SCHOLARAG__DB__HOST", "http://www.example.com")
    monkeypatch.setenv("SCHOLARAG__DB__PORT", "1234")

    settings = Settings()

    assert settings.db.index_paragraphs == "amazing"
    assert settings.db.index_journals == "amazing_journals"
    assert settings.db.db_type == "opensearch"
    assert settings.db.host == "http://www.example.com"
    assert settings.db.port == 1234

    # make sure not case sensitive
    monkeypatch.delenv("SCHOLARAG__DB__PORT")
    monkeypatch.setenv("SCHOLARAG__DB__PORT", "9876")

    settings = Settings()
    assert settings.db.port == 9876


def test_generative_validation(monkeypatch):
    # provide required
    monkeypatch.setenv("SCHOLARAG__DB__DB_TYPE", "opensearch")
    monkeypatch.setenv("SCHOLARAG__DB__INDEX_PARAGRAPHS", "amazing")
    monkeypatch.setenv("SCHOLARAG__DB__INDEX_JOURNALS", "amazing_journals")
    monkeypatch.setenv("SCHOLARAG__DB__HOST", "http://www.example.com")
    monkeypatch.setenv("SCHOLARAG__DB__PORT", "1234")

    monkeypatch.setenv("SCHOLARAG__GENERATIVE__OPENAI__TOKEN", "abcd")
    settings = Settings()

    assert settings.generative.openai.token.get_secret_value() == "abcd"
