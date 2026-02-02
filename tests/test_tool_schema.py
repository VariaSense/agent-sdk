"""Tests for tool schema generation."""

import pytest
from pydantic import BaseModel, Field
from agent_sdk.core.tool_schema import (
    ToolSchema,
    SchemaGenerator,
    ToolSchemaRegistry,
    ToolSchemaValidator,
    register_function_schema,
    get_schema_registry,
)


class InputModel(BaseModel):
    """Test input model."""
    name: str = Field(..., description="Name of the item")
    value: int = Field(default=10, description="Value")


class OutputModel(BaseModel):
    """Test output model."""
    success: bool
    result: str


def test_tool_schema_creation():
    """Test creating a ToolSchema."""
    schema = ToolSchema(
        name="test_tool",
        description="A test tool",
        parameters={"arg1": {"type": "string"}},
        required_parameters=["arg1"],
    )
    
    assert schema.name == "test_tool"
    assert schema.description == "A test tool"
    assert "arg1" in schema.parameters


def test_schema_to_openai_format():
    """Test converting to OpenAI format."""
    schema = ToolSchema(
        name="add",
        description="Add two numbers",
        parameters={
            "a": {"type": "integer"},
            "b": {"type": "integer"},
        },
        required_parameters=["a", "b"],
    )
    
    openai_fmt = schema.to_openai_format()
    
    assert openai_fmt["type"] == "function"
    assert openai_fmt["function"]["name"] == "add"
    assert "a" in openai_fmt["function"]["parameters"]["properties"]


def test_schema_to_anthropic_format():
    """Test converting to Anthropic format."""
    schema = ToolSchema(
        name="multiply",
        description="Multiply two numbers",
        parameters={
            "x": {"type": "number"},
            "y": {"type": "number"},
        },
        required_parameters=["x", "y"],
    )
    
    anthropic_fmt = schema.to_anthropic_format()
    
    assert anthropic_fmt["name"] == "multiply"
    assert "input_schema" in anthropic_fmt
    assert "x" in anthropic_fmt["input_schema"]["properties"]


def test_python_type_to_json_schema():
    """Test converting Python types to JSON schema."""
    # String
    schema = SchemaGenerator.python_type_to_json_schema(str)
    assert schema["type"] == "string"
    
    # Integer
    schema = SchemaGenerator.python_type_to_json_schema(int)
    assert schema["type"] == "integer"
    
    # Float
    schema = SchemaGenerator.python_type_to_json_schema(float)
    assert schema["type"] == "number"
    
    # Boolean
    schema = SchemaGenerator.python_type_to_json_schema(bool)
    assert schema["type"] == "boolean"
    
    # List
    schema = SchemaGenerator.python_type_to_json_schema(list)
    assert schema["type"] == "array"


def test_schema_generator_from_pydantic():
    """Test generating schema from Pydantic model."""
    schema = SchemaGenerator.from_pydantic_model(
        InputModel,
        name="input_tool",
        description="Takes input data"
    )
    
    assert schema.name == "input_tool"
    assert "name" in schema.parameters
    assert "value" in schema.parameters
    assert "name" in schema.required_parameters


def test_schema_generator_from_function():
    """Test generating schema from Python function."""
    def calculate(a: int, b: int, operation: str = "add") -> int:
        """Calculate operation on two numbers."""
        if operation == "add":
            return a + b
        return a * b
    
    schema = SchemaGenerator.from_function(calculate, name="math_op")
    
    assert schema.name == "math_op"
    assert "a" in schema.parameters
    assert "b" in schema.parameters
    assert "operation" in schema.parameters
    assert "a" in schema.required_parameters
    assert "b" in schema.required_parameters
    assert "operation" not in schema.required_parameters  # Has default


def test_schema_registry():
    """Test schema registry."""
    registry = ToolSchemaRegistry()
    
    schema = ToolSchema(
        name="test_tool",
        description="Test",
        parameters={},
        required_parameters=[],
    )
    
    registry.register(schema)
    
    assert registry.get("test_tool") == schema
    assert len(registry.list_schemas()) == 1


def test_schema_registry_export():
    """Test exporting schemas in different formats."""
    registry = ToolSchemaRegistry()
    
    schema = ToolSchema(
        name="add",
        description="Add numbers",
        parameters={"a": {"type": "integer"}},
        required_parameters=["a"],
    )
    
    registry.register(schema)
    
    # OpenAI format
    openai_schemas = registry.to_openai_format()
    assert len(openai_schemas) == 1
    assert openai_schemas[0]["type"] == "function"
    
    # Anthropic format
    anthropic_schemas = registry.to_anthropic_format()
    assert len(anthropic_schemas) == 1
    assert "input_schema" in anthropic_schemas[0]
    
    # JSON schema
    json_schemas = registry.to_json_schemas()
    assert len(json_schemas) == 1
    assert json_schemas[0]["type"] == "object"


def test_schema_validator():
    """Test schema validation."""
    schema = ToolSchema(
        name="test",
        description="Test",
        parameters={
            "name": {"type": "string"},
            "age": {"type": "integer"},
        },
        required_parameters=["name", "age"],
    )
    
    # Valid input
    valid_input = {"name": "John", "age": 30}
    assert ToolSchemaValidator.validate(schema, valid_input) is True
    
    # Missing required field
    invalid_input = {"name": "John"}
    assert ToolSchemaValidator.validate(schema, invalid_input) is False
    
    # Wrong type
    wrong_type = {"name": "John", "age": "thirty"}
    assert ToolSchemaValidator.validate(schema, wrong_type) is False


def test_register_function_globally():
    """Test registering function schema globally."""
    def my_tool(x: int, y: str = "default") -> str:
        """My test tool."""
        return f"{y}: {x}"
    
    schema = register_function_schema(my_tool, name="my_test", description="Test tool")
    
    registry = get_schema_registry()
    retrieved = registry.get("my_test")
    
    assert retrieved is not None
    assert retrieved.name == "my_test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
