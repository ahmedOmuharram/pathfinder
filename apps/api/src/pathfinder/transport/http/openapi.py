"""Declare the RFC 7807 problem+json error contract in the OpenAPI schema."""

from typing import Any

from fastapi import FastAPI

from pathfinder.platform.errors import ProblemDetail

_HTTP_METHODS = ("get", "post", "put", "patch", "delete", "options", "head", "trace")
_PROBLEM_JSON = "application/problem+json"
_PROBLEM_SCHEMA_REF = "#/components/schemas/ProblemDetail"


def _problem_components() -> dict[str, Any]:
    """ProblemDetail's JSON schema plus the enums it references (e.g. ErrorCode)."""
    schema = ProblemDetail.model_json_schema(
        ref_template="#/components/schemas/{model}"
    )
    nested = schema.pop("$defs", {})
    for prop in schema["properties"].values():
        prop.pop("default", None)
    return {"ProblemDetail": schema, **nested}


def _problem_content() -> dict[str, Any]:
    return {_PROBLEM_JSON: {"schema": {"$ref": _PROBLEM_SCHEMA_REF}}}


def _inject_problem_responses(schema: dict[str, Any]) -> None:
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    for name, model_schema in _problem_components().items():
        components.setdefault(name, model_schema)

    for path, path_item in schema["paths"].items():
        has_path_param = "{" in path
        for method in _HTTP_METHODS:
            operation = path_item.get(method)
            if operation is None:
                continue
            responses = operation["responses"]
            if "422" in responses:
                responses["422"].setdefault("content", {}).update(_problem_content())
            if has_path_param:
                responses.setdefault(
                    "404", {"description": "Not Found", "content": _problem_content()}
                )


def install_problem_responses(app: FastAPI) -> None:
    # app.openapi() builds and caches the schema; mutate the cached object.
    _inject_problem_responses(app.openapi())
