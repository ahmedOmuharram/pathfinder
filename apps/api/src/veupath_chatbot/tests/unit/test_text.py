"""Tests for veupath_chatbot.platform.text — pure text utilities."""

from veupath_chatbot.platform.text import strip_html_tags


class TestStripHtmlTags:
    """site-search highlights matches with <em> tags; strip them."""

    def test_strips_em_tags(self) -> None:
        assert strip_html_tags("the <em>kinase</em> gene") == "the kinase gene"

    def test_strips_multiple_tags(self) -> None:
        assert strip_html_tags("<b>bold</b> and <i>italic</i>") == "bold and italic"

    def test_strips_self_closing_tags(self) -> None:
        assert strip_html_tags("line<br/>break") == "linebreak"

    def test_handles_empty_string(self) -> None:
        assert strip_html_tags("") == ""

    def test_handles_no_tags(self) -> None:
        assert strip_html_tags("plain text") == "plain text"

    def test_strips_and_trims_whitespace(self) -> None:
        assert strip_html_tags("  <em>test</em>  ") == "test"

    def test_handles_none_gracefully(self) -> None:
        assert strip_html_tags(None) == ""
