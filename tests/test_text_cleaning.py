"""Tests for text_cleaning — HTML conversion and conservative cleanup."""

from text_cleaning import clean_description, html_to_text


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
