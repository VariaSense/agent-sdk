"""Regression tests for tool schemas."""

from agent_sdk.core.tool_schema import ToolSchema, ToolSchemaValidator
from agent_sdk.tool_packs.builtin import TOOL_DEFINITIONS, SCHEMA_VERSION


def test_tool_schema_validation_required_fields():
    schema = ToolSchema(
        name="add",
        description="Add two numbers",
        parameters={"a": {"type": "number"}, "b": {"type": "number"}},
        required_parameters=["a", "b"],
    )

    assert ToolSchemaValidator.validate(schema, {"a": 1, "b": 2}) is True
    assert ToolSchemaValidator.validate(schema, {"a": 1}) is False
    assert ToolSchemaValidator.validate(schema, {"a": 1, "b": "nope"}) is False


def test_builtin_tool_schemas_have_versions():
    for definition in TOOL_DEFINITIONS.values():
        assert definition.schema.get("version") == SCHEMA_VERSION
