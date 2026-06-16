"""Tests for text_cleaning — HTML conversion and conservative cleanup."""

from text_cleaning import clean_description, html_to_text, sanitize_html


def test_html_to_text_handles_none_and_tags():
    assert html_to_text(None) == ""
    assert html_to_text("") == ""
    assert html_to_text("<p>Hello <b>world</b></p>") == "Hello world"


def test_clean_description_strips_reply_history():
    raw = "My printer is broken.\n\nOn Mon, someone wrote:\n> old reply text"
    cleaned = clean_description(raw)
    assert "printer is broken" in cleaned
    assert "old reply text" not in cleaned


def test_clean_description_strips_confidentiality_footer():
    raw = "Please reset my password.\n\nThis email is confidential and privileged."
    cleaned = clean_description(raw)
    assert "reset my password" in cleaned
    assert "confidential" not in cleaned.lower()


def test_clean_description_is_idempotent_on_plain_text():
    raw = "Outlook will not sync new mail."
    assert clean_description(raw) == raw


def test_sanitize_html_strips_script_and_event_handlers():
    dirty = '<p onclick="x()">Hi</p><script>alert(1)</script><a href="javascript:evil()">go</a>'
    clean = sanitize_html(dirty)
    assert "<script" not in clean
    assert "alert(1)" not in clean
    assert "onclick" not in clean
    assert "javascript:" not in clean


def test_sanitize_html_keeps_safe_markup():
    ok = '<p>Hello <b>world</b> <a href="https://example.com">link</a></p>'
    clean = sanitize_html(ok)
    assert "<b>world</b>" in clean
    assert 'href="https://example.com"' in clean


def test_sanitize_html_handles_none():
    assert sanitize_html(None) == ""
