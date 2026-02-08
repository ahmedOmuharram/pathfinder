import respx

from veupath_chatbot.services.research import WebSearchService


@respx.mock
async def test_web_search_parses_results_when_result_body_has_multiple_classes() -> (
    None
):
    html = """
<!doctype html>
<html>
  <body>
    <div class="results">
      <div class="result results_links web-result">
        <div class="links_main links_deep result__body">
          <h2 class="result__title">
            <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Froos">David S. Roos | Example</a>
          </h2>
          <a class="result__snippet">Professor at University of Pennsylvania</a>
        </div>
      </div>
    </div>
  </body>
</html>
"""
    respx.get("https://html.duckduckgo.com/html/").respond(200, text=html)
    respx.get("https://example.com/roos").respond(
        200,
        text='<html><head><meta name="description" content="David S. Roos is a professor who helped found key parasite genomics resources."></head><body><p>Extra.</p></body></html>',
    )

    service = WebSearchService(timeout_seconds=5.0)
    out = await service.search("David S. Roos", limit=5, include_summary=True)

    results_value = out.get("results")
    assert isinstance(results_value, list) and len(results_value) > 0
    first_result = results_value[0]
    assert isinstance(first_result, dict)
    title_value = first_result.get("title")
    assert isinstance(title_value, str)
    assert title_value.lower().startswith("david s. roos")
    url_value = first_result.get("url")
    assert isinstance(url_value, str)
    assert url_value == "https://example.com/roos"
    assert isinstance(first_result.get("summary"), (str, type(None)))
    citations_value = out.get("citations")
    assert isinstance(citations_value, list) and len(citations_value) > 0
    first_citation = citations_value[0]
    assert isinstance(first_citation, dict)
    tag_value = first_citation.get("tag")
    assert isinstance(tag_value, str)


@respx.mock
async def test_web_search_summary_uses_paragraph_when_meta_missing_and_avoids_nav_text() -> (
    None
):
    html = """
<!doctype html>
<html>
  <body>
    <div class="results">
      <div class="result results_links web-result">
        <div class="links_main links_deep result__body">
          <h2 class="result__title">
            <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpage">Example</a>
          </h2>
          <a class="result__snippet">Short</a>
        </div>
      </div>
    </div>
  </body>
</html>
"""
    respx.get("https://html.duckduckgo.com/html/").respond(200, text=html)
    respx.get("https://example.com/page").respond(
        200,
        text="""
<html><body>
<p>Toggle navigation Main navigation People About</p>
<p>This is a longer paragraph describing the page content. It has multiple sentences. It should be selected.</p>
</body></html>
""",
    )

    service = WebSearchService(timeout_seconds=5.0)
    out = await service.search(
        "Example", limit=1, include_summary=True, summary_max_chars=600
    )
    results_value = out.get("results")
    assert isinstance(results_value, list) and len(results_value) > 0
    first_result = results_value[0]
    assert isinstance(first_result, dict)
    summary_value = first_result.get("summary")
    assert summary_value is not None
    assert isinstance(summary_value, str)
    assert "toggle navigation" not in summary_value.lower()


@respx.mock
async def test_web_search_retries_with_simplified_query_when_ddg_returns_challenge() -> (
    None
):
    # DDG sometimes returns a 202 "challenge" page for specific long queries.
    challenge_html = "<html><body>challenge loading</body></html>"
    ok_html = """
<!doctype html>
<html><body>
  <div class="links_main links_deep result__body">
    <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fok">OK</a>
    <a class="result__snippet">Useful snippet</a>
  </div>
</body></html>
"""
    # Original query -> 202 challenge.
    respx.get(
        "https://html.duckduckgo.com/html/",
        params={"q": "A B parasitologist biography"},
    ).respond(202, text=challenge_html)
    # Intermediate truncation candidate -> still challenged.
    respx.get(
        "https://html.duckduckgo.com/html/",
        params={"q": "A B parasitologist"},
    ).respond(202, text=challenge_html)
    # Simplified query (drops low-value terms) -> 200 with results.
    respx.get(
        "https://html.duckduckgo.com/html/",
        params={"q": "A B"},
    ).respond(200, text=ok_html)
    respx.get("https://example.com/ok").respond(
        200, text="<html><p>Summary.</p></html>"
    )

    service = WebSearchService(timeout_seconds=5.0)
    out = await service.search(
        "A B parasitologist biography", limit=3, include_summary=True
    )
    assert out["results"]
    assert out.get("effectiveQuery") == "A B"
    assert out.get("searchAdjusted") is True
