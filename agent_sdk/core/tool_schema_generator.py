"""
Tool Schema Generation: Auto-generate JSON schemas from Pydantic models.

Converts Pydantic model definitions into JSON schemas that LLMs can understand
and use to invoke tools with proper parameter validation.
"""

from typing import Any, Dict, List, Optional, Type, get_args, get_origin
from pydantic import BaseModel, Field
from enum import Enum
import json
import inspect


class ToolSchemaGenerator:
    """Generates JSON schemas from Pydantic models for LLM tool usage."""

    def __init__(self):
        self._schema_cache: Dict[str, Dict[str, Any]] = {}
        self._tool_registry: Dict[str, Dict[str, Any]] = {}

    def generate_tool_schema(
        self,
        tool_name: str,
        pydantic_model: Type[BaseModel],
        description: str = "",
    ) -> Dict[str, Any]:
        """
        Generate a JSON schema for a tool from a Pydantic model.

        Args:
            tool_name: Name of the tool
            pydantic_model: Pydantic BaseModel class defining tool parameters
            description: Human-readable description of the tool

        Returns:
            JSON schema dict with type, properties, required fields
        """
        if tool_name in self._schema_cache:
            return self._schema_cache[tool_name]

        schema = pydantic_model.model_json_schema()

        tool_schema = {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": description or pydantic_model.__doc__ or "",
                "parameters": {
                    "type": "object",
                    "properties": schema.get("properties", {}),
                    "required": schema.get("required", []),
                },
            },
        }

        # Add field descriptions from Pydantic Field info
        self._add_field_descriptions(tool_schema, pydantic_model)

        self._schema_cache[tool_name] = tool_schema
        return tool_schema

    def register_tool_schema(
        self,
        tool_name: str,
        pydantic_model: Type[BaseModel],
        description: str = "",
        handler: Optional[callable] = None,
    ) -> None:
        """
        Register a tool schema for later retrieval.

        Args:
            tool_name: Unique name for the tool
            pydantic_model: Pydantic model defining parameters
            description: Tool description
            handler: Optional async/sync function that implements the tool
        """
        schema = self.generate_tool_schema(tool_name, pydantic_model, description)

        self._tool_registry[tool_name] = {
            "schema": schema,
            "model": pydantic_model,
            "handler": handler,
        }

    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get registered tool schema by name."""
        if tool_name in self._tool_registry:
            return self._tool_registry[tool_name]["schema"]
        return None

    def get_all_tool_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered tool schemas as a dict."""
        return {
            name: info["schema"]
            for name, info in self._tool_registry.items()
        }

    def validate_tool_input(
        self,
        tool_name: str,
        input_data: Dict[str, Any],
    ) -> tuple[bool, Optional[BaseModel], Optional[str]]:
        """
        Validate input against a registered tool schema.

        Args:
            tool_name: Name of registered tool
            input_data: Input parameters to validate

        Returns:
            Tuple of (is_valid, parsed_model, error_message)
        """
        if tool_name not in self._tool_registry:
            return False, None, f"Tool '{tool_name}' not registered"

        try:
            model_class = self._tool_registry[tool_name]["model"]
            instance = model_class(**input_data)
            return True, instance, None
        except Exception as e:
            return False, None, str(e)

    def get_tool_handler(self, tool_name: str) -> Optional[callable]:
        """Get the handler function for a registered tool."""
        if tool_name in self._tool_registry:
            return self._tool_registry[tool_name]["handler"]
        return None

    def parse_pydantic_schema(
        self,
        pydantic_model: Type[BaseModel],
    ) -> Dict[str, Any]:
        """
        Parse a Pydantic model into a flattened schema.

        Args:
            pydantic_model: Pydantic BaseModel to parse

        Returns:
            Flattened schema with type, properties, descriptions
        """
        schema = pydantic_model.model_json_schema()

        parsed = {
            "properties": {},
            "required": schema.get("required", []),
            "definitions": schema.get("$defs", {}),
        }

        # Extract properties with descriptions
        for prop_name, prop_schema in schema.get("properties", {}).items():
            parsed["properties"][prop_name] = self._flatten_property(
                prop_name,
                prop_schema,
            )

        return parsed

    def _flatten_property(
        self,
        prop_name: str,
        prop_schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Flatten a property schema for easier consumption."""
        flattened = {
            "name": prop_name,
            "type": prop_schema.get("type", "unknown"),
            "description": prop_schema.get("description", ""),
        }

        # Handle enums
        if "enum" in prop_schema:
            flattened["enum_values"] = prop_schema["enum"]

        # Handle arrays
        if prop_schema.get("type") == "array":
            flattened["items"] = prop_schema.get("items", {})

        # Handle objects
        if prop_schema.get("type") == "object":
            flattened["properties"] = prop_schema.get("properties", {})

        # Add default if present
        if "default" in prop_schema:
            flattened["default"] = prop_schema["default"]

        return flattened

    def _add_field_descriptions(
        self,
        tool_schema: Dict[str, Any],
        pydantic_model: Type[BaseModel],
    ) -> None:
        """Add field descriptions from Pydantic Field definitions."""
        properties = tool_schema["function"]["parameters"]["properties"]

        for field_name, field_info in pydantic_model.model_fields.items():
            if field_name in properties:
                if field_info.description:
                    properties[field_name]["description"] = (
                        field_info.description
                    )
                if field_info.default is not None:
                    properties[field_name]["default"] = field_info.default

    def generate_openai_schema(
        self,
        tool_name: str,
        pydantic_model: Type[BaseModel],
        description: str = "",
    ) -> Dict[str, Any]:
        """
        Generate schema in OpenAI Functions format.

        Args:
            tool_name: Tool name
            pydantic_model: Pydantic model
            description: Tool description

        Returns:
            OpenAI Functions-compatible schema
        """
        schema = self.generate_tool_schema(tool_name, pydantic_model, description)
        return schema["function"]

    def generate_anthropic_schema(
        self,
        tool_name: str,
        pydantic_model: Type[BaseModel],
        description: str = "",
    ) -> Dict[str, Any]:
        """
        Generate schema in Anthropic format.

        Args:
            tool_name: Tool name
            pydantic_model: Pydantic model
            description: Tool description

        Returns:
            Anthropic-compatible schema
        """
        schema = self.generate_tool_schema(tool_name, pydantic_model, description)
        return schema["function"]

    def to_json_schema(self, schema: Dict[str, Any]) -> str:
        """Convert schema dict to JSON string."""
        # Filter out undefined values
        def clean_undefined(obj):
            if isinstance(obj, dict):
                return {
                    k: clean_undefined(v)
                    for k, v in obj.items()
                    if v is not None and str(type(v)) != "<class 'pydantic_core._pydantic_core.PydanticUndefinedType'>"
                }
            elif isinstance(obj, list):
                return [clean_undefined(item) for item in obj]
            return obj

        cleaned = clean_undefined(schema)
        return json.dumps(cleaned, indent=2, default=str)

    def from_json_schema(self, json_str: str) -> Dict[str, Any]:
        """Parse JSON schema string."""
        return json.loads(json_str)

    def merge_schemas(
        self,
        *schemas: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Merge multiple tool schemas.

        Args:
            *schemas: Multiple tool schemas to merge

        Returns:
            Merged schema dict
        """
        merged = {
            "tools": [],
            "total_tools": 0,
        }

        for schema in schemas:
            if "function" in schema:
                merged["tools"].append(schema)
            elif "type" in schema and schema["type"] == "function":
                merged["tools"].append(schema)

        merged["total_tools"] = len(merged["tools"])
        return merged


# Global singleton instance
_generator = ToolSchemaGenerator()


def generate_schema(
    tool_name: str,
    pydantic_model: Type[BaseModel],
    description: str = "",
) -> Dict[str, Any]:
    """
    Module-level function to generate tool schema.

    Args:
        tool_name: Name of the tool
        pydantic_model: Pydantic model defining parameters
        description: Tool description

    Returns:
        JSON schema dict
    """
    return _generator.generate_tool_schema(tool_name, pydantic_model, description)


def register_tool(
    tool_name: str,
    pydantic_model: Type[BaseModel],
    description: str = "",
    handler: Optional[callable] = None,
) -> None:
    """
    Module-level function to register a tool.

    Args:
        tool_name: Unique tool name
        pydantic_model: Pydantic model
        description: Description
        handler: Handler function
    """
    _generator.register_tool_schema(tool_name, pydantic_model, description, handler)


def get_registry() -> ToolSchemaGenerator:
    """Get the global schema registry."""
    return _generator
