"""Tests for the AI summarizer — fully mocked, no live OpenAI calls."""

import ai_summarizer
from ai_summarizer import (
    create_ticket_summary,
    create_comprehensive_ticket_embedding_text,
)


class _Msg:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Msg(content)


class _Resp:
    def __init__(self, content):
        self.choices = [_Choice(content)]


class _Completions:
    def create(self, **kwargs):
        return _Resp("Revit desktop connector fails to open, blocking the user's work.")


class _Chat:
    def __init__(self):
        self.completions = _Completions()


class _FakeClient:
    def __init__(self):
        self.chat = _Chat()


def _use_fake_client(monkeypatch):
    monkeypatch.setattr(ai_summarizer, "openai_client", lambda: _FakeClient())
    ai_summarizer._cached_ticket_summary.cache_clear()


def test_create_ticket_summary_prefixes_ticket_id(monkeypatch):
    _use_fake_client(monkeypatch)
    summary = create_ticket_summary("Revit issue", "cannot open connector", ticket_id=6511)
    assert summary.startswith("[Ticket 6511]")
    assert "Revit" in summary


def test_comprehensive_embedding_includes_original_text(monkeypatch):
    _use_fake_client(monkeypatch)
    text = create_comprehensive_ticket_embedding_text(
        "Revit issue", "cannot open connector", ticket_id=6511
    )
    assert "Original:" in text
    assert "cannot open connector" in text


def test_summary_falls_back_to_raw_on_error(monkeypatch):
    def _boom():
        raise RuntimeError("API down")

    monkeypatch.setattr(ai_summarizer, "openai_client", _boom)
    ai_summarizer._cached_ticket_summary.cache_clear()
    # On failure the summarizer degrades gracefully to "subject\n\ndescription".
    summary = create_ticket_summary("Subj", "Desc", ticket_id=1)
    assert "Subj" in summary and "Desc" in summary
