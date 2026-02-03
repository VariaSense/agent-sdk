"""
Tests for Tool Schema Generation.
"""

import pytest
from pydantic import BaseModel, Field
from agent_sdk.core.tool_schema_generator import (
    ToolSchemaGenerator,
    generate_schema,
    register_tool,
    get_registry,
)


class SearchParams(BaseModel):
    """Parameters for search tool."""
    query: str = Field(..., description="Search query")
    limit: int = Field(10, description="Max results")
    filters: dict = Field(default_factory=dict, description="Search filters")


class CalculatorParams(BaseModel):
    """Parameters for calculator tool."""
    operation: str = Field(..., description="Math operation: +, -, *, /")
    a: float = Field(..., description="First operand")
    b: float = Field(..., description="Second operand")


class TestToolSchemaGenerator:
    """Test ToolSchemaGenerator class."""

    def test_create_generator(self):
        """Test generator creation."""
        generator = ToolSchemaGenerator()
        assert generator is not None
        assert len(generator._schema_cache) == 0
        assert len(generator._tool_registry) == 0

    def test_generate_tool_schema(self):
        """Test generating a tool schema."""
        generator = ToolSchemaGenerator()
        schema = generator.generate_tool_schema(
            "search",
            SearchParams,
            "Search for information",
        )

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "search"
        assert schema["function"]["description"] == "Search for information"
        assert "properties" in schema["function"]["parameters"]
        assert "required" in schema["function"]["parameters"]

    def test_schema_caching(self):
        """Test that schemas are cached."""
        generator = ToolSchemaGenerator()
        schema1 = generator.generate_tool_schema("search", SearchParams)
        schema2 = generator.generate_tool_schema("search", SearchParams)

        assert schema1 is schema2  # Same object reference

    def test_register_tool_schema(self):
        """Test registering a tool."""
        generator = ToolSchemaGenerator()

        def search_handler(query: str, limit: int = 10):
            return {"query": query, "limit": limit}

        generator.register_tool_schema(
            "search",
            SearchParams,
            "Search tool",
            search_handler,
        )

        assert "search" in generator._tool_registry
        assert generator._tool_registry["search"]["handler"] == search_handler

    def test_get_tool_schema(self):
        """Test retrieving registered schema."""
        generator = ToolSchemaGenerator()
        generator.register_tool_schema("search", SearchParams, "Search")

        schema = generator.get_tool_schema("search")
        assert schema is not None
        assert schema["function"]["name"] == "search"

    def test_get_all_tool_schemas(self):
        """Test getting all registered schemas."""
        generator = ToolSchemaGenerator()
        generator.register_tool_schema("search", SearchParams, "Search")
        generator.register_tool_schema("calc", CalculatorParams, "Calculator")

        schemas = generator.get_all_tool_schemas()
        assert len(schemas) == 2
        assert "search" in schemas
        assert "calc" in schemas

    def test_validate_tool_input_valid(self):
        """Test validating valid input."""
        generator = ToolSchemaGenerator()
        generator.register_tool_schema("search", SearchParams)

        is_valid, model, error = generator.validate_tool_input(
            "search",
            {"query": "python", "limit": 5},
        )

        assert is_valid is True
        assert model is not None
        assert model.query == "python"
        assert model.limit == 5
        assert error is None

    def test_validate_tool_input_invalid_model(self):
        """Test validating with unknown tool."""
        generator = ToolSchemaGenerator()

        is_valid, model, error = generator.validate_tool_input(
            "unknown",
            {"query": "test"},
        )

        assert is_valid is False
        assert model is None
        assert "not registered" in error

    def test_validate_tool_input_invalid_data(self):
        """Test validating with invalid data."""
        generator = ToolSchemaGenerator()
        generator.register_tool_schema("calc", CalculatorParams)

        is_valid, model, error = generator.validate_tool_input(
            "calc",
            {"operation": "+"},  # Missing required fields a and b
        )

        assert is_valid is False
        assert model is None
        assert error is not None

    def test_get_tool_handler(self):
        """Test retrieving tool handler."""
        def my_handler():
            pass

        generator = ToolSchemaGenerator()
        generator.register_tool_schema(
            "test",
            SearchParams,
            handler=my_handler,
        )

        handler = generator.get_tool_handler("test")
        assert handler is my_handler

    def test_parse_pydantic_schema(self):
        """Test parsing Pydantic schema."""
        generator = ToolSchemaGenerator()
        parsed = generator.parse_pydantic_schema(SearchParams)

        assert "properties" in parsed
        assert "required" in parsed
        assert "query" in parsed["properties"]
        assert "query" in parsed["required"]

    def test_generate_openai_schema(self):
        """Test OpenAI schema format."""
        generator = ToolSchemaGenerator()
        schema = generator.generate_openai_schema(
            "search",
            SearchParams,
            "Search",
        )

        assert "name" in schema
        assert "description" in schema
        assert "parameters" in schema
        assert schema["name"] == "search"

    def test_generate_anthropic_schema(self):
        """Test Anthropic schema format."""
        generator = ToolSchemaGenerator()
        schema = generator.generate_anthropic_schema(
            "calc",
            CalculatorParams,
            "Calculator",
        )

        assert "name" in schema
        assert "description" in schema
        assert "parameters" in schema

    def test_to_json_schema(self):
        """Test converting schema to JSON."""
        generator = ToolSchemaGenerator()
        schema = generator.generate_tool_schema("search", SearchParams)
        json_str = generator.to_json_schema(schema)

        assert isinstance(json_str, str)
        assert "search" in json_str
        assert "function" in json_str

    def test_from_json_schema(self):
        """Test parsing JSON schema."""
        generator = ToolSchemaGenerator()
        schema = generator.generate_tool_schema("search", SearchParams)
        json_str = generator.to_json_schema(schema)
        parsed = generator.from_json_schema(json_str)

        assert parsed["function"]["name"] == "search"

    def test_merge_schemas(self):
        """Test merging multiple schemas."""
        generator = ToolSchemaGenerator()
        schema1 = generator.generate_tool_schema("search", SearchParams)
        schema2 = generator.generate_tool_schema("calc", CalculatorParams)

        merged = generator.merge_schemas(schema1, schema2)
        assert len(merged["tools"]) == 2
        assert merged["total_tools"] == 2


class TestModuleLevelFunctions:
    """Test module-level convenience functions."""

    def test_generate_schema_function(self):
        """Test generate_schema function."""
        schema = generate_schema("search", SearchParams, "Search")

        assert schema["function"]["name"] == "search"
        assert schema["type"] == "function"

    def test_register_tool_function(self):
        """Test register_tool function."""
        def handler():
            pass

        register_tool("test", SearchParams, "Test", handler)

        registry = get_registry()
        assert registry.get_tool_schema("test") is not None

    def test_get_registry_function(self):
        """Test get_registry function."""
        registry = get_registry()
        assert isinstance(registry, ToolSchemaGenerator)


class TestFieldDescriptions:
    """Test field description handling."""

    def test_field_descriptions_added(self):
        """Test that field descriptions are added to schema."""
        generator = ToolSchemaGenerator()
        schema = generator.generate_tool_schema("search", SearchParams)

        properties = schema["function"]["parameters"]["properties"]
        assert "description" in properties["query"]
        assert properties["query"]["description"] == "Search query"

    def test_default_values_added(self):
        """Test that defaults are added to schema."""
        generator = ToolSchemaGenerator()
        schema = generator.generate_tool_schema("search", SearchParams)

        properties = schema["function"]["parameters"]["properties"]
        assert properties["limit"]["default"] == 10
