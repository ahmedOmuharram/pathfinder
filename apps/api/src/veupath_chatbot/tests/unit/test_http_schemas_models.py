from datetime import UTC, datetime
from uuid import uuid4

from veupath_chatbot.transport.http import schemas


def test_http_schemas_import_and_basic_model_parsing() -> None:
    # Importing the monolithic schemas module should be safe and side-effect free.
    now = datetime.now(UTC)

    health = schemas.HealthResponse(status="healthy", version="1", timestamp=now)
    assert health.status == "healthy"

    # Alias population should work (populate_by_name=True).
    site = schemas.SiteResponse(
        id="plasmodb",
        name="PlasmoDB",
        displayName="PlasmoDB",
        baseUrl="https://plasmodb.org",
        projectId="PlasmoDB",
        isPortal=False,
    )
    assert site.display_name == "PlasmoDB"
    assert site.base_url.startswith("https://")

    chat = schemas.ChatRequest(siteId="plasmodb", message="hello", strategyId=None)
    assert chat.site_id == "plasmodb"

    msg = schemas.MessageResponse(
        role="assistant",
        content="hi",
        timestamp=now,
        toolCalls=[schemas.ToolCallResponse(id="t1", name="tool", arguments={"a": 1})],
    )
    assert msg.tool_calls and msg.tool_calls[0].name == "tool"

    # A few strategy DTOs (ensures aliases & defaults are valid).
    step = schemas.StepResponse(
        id="s1",
        kind="search",
        displayName="Step",
        recordType="gene",
        resultCount=5,
    )
    assert step.display_name == "Step"
    assert step.result_count == 5

    # A model with UUID fields
    _ = schemas.OpenStrategyRequest(siteId="plasmodb", strategyId=uuid4())
