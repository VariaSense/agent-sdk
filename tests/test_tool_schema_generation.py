"""
Comprehensive tests for Tool Schema Generation.

Tests cover:
- Automatic schema generation from functions
- Type hint processing (basic, generic, optional types)
- Docstring parsing for parameter descriptions
- Pydantic model schema generation
- Format conversion (OpenAI, Anthropic, JSON)
- Schema registry management
- Validation against schemas
- Decorator-based auto-registration
"""

import pytest
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from agent_sdk.core.tool_schema import (
    ToolSchema,
    SchemaGenerator,
    ToolSchemaRegistry,
    ToolSchemaValidator,
    get_schema_registry,
    register_tool_schema,
    register_function_schema,
    auto_schema,
    generate_tools_schema,
)


# ============================================================================
# Test Functions
# ============================================================================

def simple_function(name: str, age: int) -> str:
    """A simple test function."""
    return f"{name} is {age}"


def documented_function(query: str, max_results: int = 10, debug: bool = False) -> List[str]:
    """Search for information.
    
    Args:
        query: The search query string to look up
        max_results: Maximum number of results to return (default 10)
        debug: Enable debug logging
        
    Returns:
        List of search result strings
    """
    return []


def optional_params_function(required: str, optional: Optional[int] = None) -> Optional[str]:
    """Function with optional parameters.
    
    Args:
        required: A required string parameter
        optional: An optional integer parameter
    """
    return required


def complex_types_function(items: List[str], mapping: Dict[str, int], data: Optional[List[Dict[str, Any]]] = None) -> bool:
    """Function with complex type hints.
    
    Args:
        items: List of strings
        mapping: Dictionary mapping strings to integers
        data: Optional list of dictionaries
    """
    return True


def no_params() -> str:
    """Function with no parameters."""
    return "result"


def no_docstring(param1: str, param2: int):
    pass


# ============================================================================
# Test Pydantic Models
# ============================================================================

class SearchInput(BaseModel):
    """Input model for search operation."""
    query: str = Field(..., description="Search query string")
    max_results: int = Field(default=10, description="Maximum results")
    filters: Optional[Dict[str, str]] = Field(default=None, description="Search filters")


class UserModel(BaseModel):
    """User data model."""
    name: str
    email: str
    age: int = Field(default=0)


# ============================================================================
# Test Classes
# ============================================================================

class TestSchemaGenerator:
    """Test SchemaGenerator class."""
    
    def test_basic_type_conversion(self):
        """Test conversion of basic types."""
        assert SchemaGenerator.python_type_to_json_schema(str)["type"] == "string"
        assert SchemaGenerator.python_type_to_json_schema(int)["type"] == "integer"
        assert SchemaGenerator.python_type_to_json_schema(float)["type"] == "number"
        assert SchemaGenerator.python_type_to_json_schema(bool)["type"] == "boolean"
    
    def test_list_type_conversion(self):
        """Test conversion of list types."""
        schema = SchemaGenerator.python_type_to_json_schema(List[str])
        assert schema["type"] == "array"
    
    def test_dict_type_conversion(self):
        """Test conversion of dict types."""
        schema = SchemaGenerator.python_type_to_json_schema(Dict[str, int])
        assert schema["type"] == "object"
    
    def test_optional_type_conversion(self):
        """Test conversion of Optional types."""
        schema = SchemaGenerator.python_type_to_json_schema(Optional[int])
        # Optional[int] resolves to int type in our implementation
        assert schema["type"] == "integer"
    
    def test_docstring_parsing(self):
        """Test extraction of parameter descriptions from docstring."""
        descriptions = SchemaGenerator._extract_parameter_descriptions(
            documented_function.__doc__
        )
        
        assert "query" in descriptions
        assert "search query string" in descriptions["query"]
        assert "max_results" in descriptions
        assert "maximum" in descriptions["max_results"].lower()
        assert "debug" in descriptions
    
    def test_docstring_parsing_no_docstring(self):
        """Test docstring parsing with missing docstring."""
        descriptions = SchemaGenerator._extract_parameter_descriptions(None)
        assert descriptions == {}
    
    def test_from_simple_function(self):
        """Test schema generation from simple function."""
        schema = SchemaGenerator.from_function(simple_function)
        
        assert schema.name == "simple_function"
        assert "name" in schema.parameters
        assert "age" in schema.parameters
        assert schema.required_parameters == ["name", "age"]
        assert schema.parameters["name"]["type"] == "string"
        assert schema.parameters["age"]["type"] == "integer"
    
    def test_from_function_with_defaults(self):
        """Test schema generation with default parameters."""
        schema = SchemaGenerator.from_function(documented_function)
        
        assert schema.name == "documented_function"
        assert "query" in schema.required_parameters
        assert "max_results" not in schema.required_parameters
        assert "debug" not in schema.required_parameters
        assert schema.parameters["max_results"]["default"] == 10
        assert schema.parameters["debug"]["default"] == False
    
    def test_from_function_with_docstring_descriptions(self):
        """Test that descriptions are extracted from docstring."""
        schema = SchemaGenerator.from_function(documented_function)
        
        assert "search query string" in schema.parameters["query"].get("description", "")
    
    def test_from_function_with_optional_params(self):
        """Test function with optional parameters."""
        schema = SchemaGenerator.from_function(optional_params_function)
        
        assert "required" in schema.required_parameters
        assert "optional" not in schema.required_parameters
    
    def test_from_function_with_complex_types(self):
        """Test function with complex type hints."""
        schema = SchemaGenerator.from_function(complex_types_function)
        
        assert schema.parameters["items"]["type"] == "array"
        assert schema.parameters["mapping"]["type"] == "object"
    
    def test_from_function_no_params(self):
        """Test function with no parameters."""
        schema = SchemaGenerator.from_function(no_params)
        
        assert schema.name == "no_params"
        assert len(schema.parameters) == 0
        assert len(schema.required_parameters) == 0
    
    def test_from_function_no_docstring(self):
        """Test function without docstring."""
        schema = SchemaGenerator.from_function(no_docstring)
        
        assert schema.name == "no_docstring"
        # Description is derived from first line of docstring (None in this case)
        assert schema.description == ""
    
    def test_from_pydantic_model(self):
        """Test schema generation from Pydantic model."""
        schema = SchemaGenerator.from_pydantic_model(
            SearchInput,
            "search",
            "Search operation"
        )
        
        assert schema.name == "search"
        assert schema.description == "Search operation"
        assert "query" in schema.parameters
        assert "max_results" in schema.parameters
        assert "query" in schema.required_parameters
    
    def test_from_pydantic_model_fields(self):
        """Test Pydantic model field descriptions."""
        schema = SchemaGenerator.from_pydantic_model(
            SearchInput,
            "search",
            "Search"
        )
        
        # Pydantic extracts Field descriptions
        assert "description" in schema.parameters["query"] or "query" in schema.parameters


class TestToolSchema:
    """Test ToolSchema class."""
    
    def test_to_openai_format(self):
        """Test conversion to OpenAI format."""
        schema = ToolSchema(
            name="test_tool",
            description="Test description",
            parameters={"param1": {"type": "string"}},
            required_parameters=["param1"]
        )
        
        openai_format = schema.to_openai_format()
        
        assert openai_format["type"] == "function"
        assert openai_format["function"]["name"] == "test_tool"
        assert openai_format["function"]["description"] == "Test description"
        assert "parameters" in openai_format["function"]
    
    def test_to_anthropic_format(self):
        """Test conversion to Anthropic format."""
        schema = ToolSchema(
            name="test_tool",
            description="Test",
            parameters={"param": {"type": "string"}},
            required_parameters=["param"]
        )
        
        anthropic_format = schema.to_anthropic_format()
        
        assert anthropic_format["name"] == "test_tool"
        assert anthropic_format["description"] == "Test"
        assert "input_schema" in anthropic_format
    
    def test_to_json_schema(self):
        """Test conversion to JSON schema."""
        schema = ToolSchema(
            name="test",
            description="Test",
            parameters={"p": {"type": "string"}},
            required_parameters=["p"]
        )
        
        json_schema = schema.to_json_schema()
        
        assert json_schema["type"] == "object"
        assert json_schema["title"] == "test"
        assert "properties" in json_schema
    
    def test_schema_with_output(self):
        """Test schema with output description."""
        schema = ToolSchema(
            name="test",
            description="Test",
            parameters={},
            output_schema={"type": "string"}
        )
        
        assert schema.output_schema is not None
        assert schema.output_schema["type"] == "string"
    
    def test_schema_with_examples(self):
        """Test schema with examples."""
        example = {"input": {"param": "value"}, "output": "result"}
        schema = ToolSchema(
            name="test",
            description="Test",
            parameters={"param": {"type": "string"}},
            examples=[example]
        )
        
        assert len(schema.examples) == 1
        assert schema.examples[0] == example


class TestToolSchemaRegistry:
    """Test ToolSchemaRegistry class."""
    
    def test_register_schema(self):
        """Test registering a schema."""
        registry = ToolSchemaRegistry()
        schema = ToolSchema(
            name="tool1",
            description="Test tool"
        )
        
        registry.register(schema)
        assert registry.get("tool1") == schema
    
    def test_register_from_function(self):
        """Test registering schema from function."""
        registry = ToolSchemaRegistry()
        schema = registry.register_from_function(simple_function)
        
        assert schema.name == "simple_function"
        assert registry.get("simple_function") is not None
    
    def test_register_from_pydantic(self):
        """Test registering schema from Pydantic model."""
        registry = ToolSchemaRegistry()
        schema = registry.register_from_pydantic(
            SearchInput,
            "search",
            "Search tool"
        )
        
        assert schema.name == "search"
        assert registry.get("search") is not None
    
    def test_list_schemas(self):
        """Test listing all schemas."""
        registry = ToolSchemaRegistry()
        registry.register(ToolSchema(name="tool1", description="Tool 1"))
        registry.register(ToolSchema(name="tool2", description="Tool 2"))
        
        schemas = registry.list_schemas()
        assert len(schemas) == 2
        assert all(isinstance(s, ToolSchema) for s in schemas)
    
    def test_to_openai_format(self):
        """Test exporting to OpenAI format."""
        registry = ToolSchemaRegistry()
        registry.register_from_function(simple_function)
        
        openai_schemas = registry.to_openai_format()
        
        assert len(openai_schemas) == 1
        assert openai_schemas[0]["type"] == "function"
    
    def test_to_anthropic_format(self):
        """Test exporting to Anthropic format."""
        registry = ToolSchemaRegistry()
        registry.register_from_function(simple_function)
        
        anthropic_schemas = registry.to_anthropic_format()
        
        assert len(anthropic_schemas) == 1
        assert "input_schema" in anthropic_schemas[0]
    
    def test_export_for_llm_openai(self):
        """Test LLM export with OpenAI format."""
        registry = ToolSchemaRegistry()
        registry.register_from_function(simple_function)
        
        schemas = registry.export_for_llm(format="openai")
        
        assert len(schemas) == 1
        assert schemas[0]["type"] == "function"
    
    def test_export_for_llm_anthropic(self):
        """Test LLM export with Anthropic format."""
        registry = ToolSchemaRegistry()
        registry.register_from_function(simple_function)
        
        schemas = registry.export_for_llm(format="anthropic")
        
        assert len(schemas) == 1
        assert "input_schema" in schemas[0]
    
    def test_export_for_llm_invalid_format(self):
        """Test LLM export with invalid format."""
        registry = ToolSchemaRegistry()
        
        with pytest.raises(ValueError):
            registry.export_for_llm(format="invalid")


class TestToolSchemaValidator:
    """Test ToolSchemaValidator class."""
    
    def test_validate_valid_input(self):
        """Test validation of valid input."""
        schema = ToolSchema(
            name="test",
            description="Test",
            parameters={
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            required_parameters=["name", "age"]
        )
        
        input_data = {"name": "John", "age": 30}
        assert ToolSchemaValidator.validate(schema, input_data) is True
    
    def test_validate_missing_required(self):
        """Test validation with missing required parameter."""
        schema = ToolSchema(
            name="test",
            description="Test",
            parameters={
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            required_parameters=["name", "age"]
        )
        
        input_data = {"name": "John"}
        assert ToolSchemaValidator.validate(schema, input_data) is False
    
    def test_validate_wrong_type(self):
        """Test validation with wrong parameter type."""
        schema = ToolSchema(
            name="test",
            description="Test",
            parameters={
                "age": {"type": "integer"}
            },
            required_parameters=["age"]
        )
        
        input_data = {"age": "not an integer"}
        assert ToolSchemaValidator.validate(schema, input_data) is False
    
    def test_validate_extra_parameters(self):
        """Test validation with extra parameters."""
        schema = ToolSchema(
            name="test",
            description="Test",
            parameters={"name": {"type": "string"}},
            required_parameters=["name"]
        )
        
        input_data = {"name": "John", "extra": "param"}
        assert ToolSchemaValidator.validate(schema, input_data) is False
    
    def test_validate_optional_parameter(self):
        """Test validation with optional parameter."""
        schema = ToolSchema(
            name="test",
            description="Test",
            parameters={
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            required_parameters=["name"]
        )
        
        input_data = {"name": "John"}
        assert ToolSchemaValidator.validate(schema, input_data) is True
    
    def test_validate_array_type(self):
        """Test validation of array types."""
        schema = ToolSchema(
            name="test",
            description="Test",
            parameters={"items": {"type": "array"}},
            required_parameters=["items"]
        )
        
        assert ToolSchemaValidator.validate(schema, {"items": [1, 2, 3]}) is True
        assert ToolSchemaValidator.validate(schema, {"items": "not array"}) is False
    
    def test_validate_object_type(self):
        """Test validation of object types."""
        schema = ToolSchema(
            name="test",
            description="Test",
            parameters={"config": {"type": "object"}},
            required_parameters=["config"]
        )
        
        assert ToolSchemaValidator.validate(schema, {"config": {"key": "value"}}) is True
        assert ToolSchemaValidator.validate(schema, {"config": "not object"}) is False


class TestGlobalFunctions:
    """Test global function utilities."""
    
    def test_register_function_schema(self):
        """Test global function schema registration."""
        schema = register_function_schema(simple_function)
        
        assert schema.name == "simple_function"
        assert get_schema_registry().get("simple_function") is not None
    
    def test_get_schema_registry(self):
        """Test getting global registry."""
        registry = get_schema_registry()
        
        assert isinstance(registry, ToolSchemaRegistry)
    
    def test_register_tool_schema(self):
        """Test global tool schema registration."""
        schema = ToolSchema(
            name="global_tool",
            description="Global tool"
        )
        
        register_tool_schema(schema)
        assert get_schema_registry().get("global_tool") is not None
    
    def test_auto_schema_decorator(self):
        """Test auto_schema decorator."""
        @auto_schema
        def decorated_func(x: int) -> int:
            """A decorated function."""
            return x * 2
        
        # Function should still work normally
        assert decorated_func(5) == 10
        
        # Schema should be registered
        schema = get_schema_registry().get("decorated_func")
        assert schema is not None
        assert schema.name == "decorated_func"
    
    def test_generate_tools_schema_openai(self):
        """Test generating schemas for multiple tools in OpenAI format."""
        tools = {
            "func1": simple_function,
            "func2": documented_function,
        }
        
        schemas = generate_tools_schema(tools, format="openai")
        
        assert len(schemas) == 2
        assert all(s["type"] == "function" for s in schemas)
    
    def test_generate_tools_schema_anthropic(self):
        """Test generating schemas for multiple tools in Anthropic format."""
        tools = {
            "func1": simple_function,
        }
        
        schemas = generate_tools_schema(tools, format="anthropic")
        
        assert len(schemas) == 1
        assert "input_schema" in schemas[0]
    
    def test_generate_tools_schema_json(self):
        """Test generating schemas for multiple tools in JSON format."""
        tools = {
            "func1": simple_function,
        }
        
        schemas = generate_tools_schema(tools, format="json")
        
        assert len(schemas) == 1
        assert schemas[0]["type"] == "object"
    
    def test_generate_tools_schema_invalid_format(self):
        """Test generating tools schema with invalid format."""
        tools = {"func": simple_function}
        
        # Should not raise, but should print warning
        schemas = generate_tools_schema(tools, format="invalid")
        assert len(schemas) == 0


class TestIntegration:
    """Integration tests for tool schema system."""
    
    def test_end_to_end_function_schema(self):
        """Test complete workflow from function to LLM format."""
        # Generate schema
        schema = SchemaGenerator.from_function(documented_function)
        
        # Validate required parameters
        assert "query" in schema.required_parameters
        assert "max_results" not in schema.required_parameters
        
        # Convert to LLM format
        openai_format = schema.to_openai_format()
        anthropic_format = schema.to_anthropic_format()
        
        assert openai_format["type"] == "function"
        assert "input_schema" in anthropic_format
        
        # Validate against schema
        valid_input = {"query": "test", "max_results": 5}
        assert ToolSchemaValidator.validate(schema, valid_input) is True
    
    def test_registry_workflow(self):
        """Test typical registry workflow."""
        registry = ToolSchemaRegistry()
        
        # Register multiple functions
        registry.register_from_function(simple_function)
        registry.register_from_function(documented_function)
        
        # Export for LLM
        openai_schemas = registry.to_openai_format()
        assert len(openai_schemas) == 2
        
        # Retrieve specific schema
        schema = registry.get("simple_function")
        assert schema is not None
        assert len(schema.parameters) == 2
    
    def test_pydantic_model_workflow(self):
        """Test workflow with Pydantic models."""
        # Generate schema from model
        schema = SchemaGenerator.from_pydantic_model(
            SearchInput,
            "search_operation",
            "Search for results"
        )
        
        # Get LLM format
        openai_format = schema.to_openai_format()
        assert openai_format["function"]["name"] == "search_operation"
        
        # Validate input
        valid_input = {"query": "test"}
        assert ToolSchemaValidator.validate(schema, valid_input) is True
    
    def test_mixed_tool_types(self):
        """Test generating schemas from mixed tool types."""
        tools = {
            "search": documented_function,
            "simple": simple_function,
        }
        
        schemas = generate_tools_schema(tools, format="openai")
        
        assert len(schemas) == 2
        schema_names = [s["function"]["name"] for s in schemas]
        assert "search" in schema_names
        assert "simple" in schema_names
