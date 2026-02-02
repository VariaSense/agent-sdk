"""Tool schema generation and management for LLM understanding and validation."""

import json
from typing import Any, Callable, Dict, List, Optional, get_args, get_origin
from pydantic import BaseModel, Field, create_model
from enum import Enum


class ToolSchema(BaseModel):
    """Schema definition for a tool that LLMs can understand."""
    
    name: str = Field(..., description="Unique tool identifier")
    description: str = Field(..., description="Human-readable description of what the tool does")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="JSON schema for input parameters")
    required_parameters: List[str] = Field(default_factory=list, description="List of required parameter names")
    output_schema: Optional[Dict[str, Any]] = Field(default=None, description="JSON schema for output")
    examples: List[Dict[str, Any]] = Field(default_factory=list, description="Usage examples")
    
    def to_openai_format(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required_parameters,
                }
            }
        }
    
    def to_anthropic_format(self) -> Dict[str, Any]:
        """Convert to Anthropic tool use format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": self.parameters,
                "required": self.required_parameters,
            }
        }
    
    def to_json_schema(self) -> Dict[str, Any]:
        """Return as standard JSON schema."""
        return {
            "type": "object",
            "title": self.name,
            "description": self.description,
            "properties": self.parameters,
            "required": self.required_parameters,
        }


class SchemaGenerator:
    """Generate JSON schemas from Python type hints."""
    
    # Type mapping to JSON schema types
    TYPE_MAPPING = {
        str: {"type": "string"},
        int: {"type": "integer"},
        float: {"type": "number"},
        bool: {"type": "boolean"},
        list: {"type": "array", "items": {}},
        dict: {"type": "object", "additionalProperties": True},
    }
    
    @staticmethod
    def python_type_to_json_schema(python_type: Any, description: str = "") -> Dict[str, Any]:
        """Convert Python type to JSON schema."""
        # Handle None
        if python_type is type(None):
            return {"type": "null"}
        
        # Handle Pydantic models
        if isinstance(python_type, type) and issubclass(python_type, BaseModel):
            model_schema = python_type.model_json_schema()
            return {
                "type": "object",
                "properties": model_schema.get("properties", {}),
                "required": model_schema.get("required", []),
            }
        
        # Handle built-in types
        if python_type in SchemaGenerator.TYPE_MAPPING:
            schema = SchemaGenerator.TYPE_MAPPING[python_type].copy()
            if description:
                schema["description"] = description
            return schema
        
        # Handle Optional types
        origin = get_origin(python_type)
        args = get_args(python_type)
        
        if origin is type(Optional):
            # Optional[X] = Union[X, None]
            base_type = args[0] if args else str
            return SchemaGenerator.python_type_to_json_schema(base_type, description)
        
        if origin is list:
            item_type = args[0] if args else dict
            return {
                "type": "array",
                "items": SchemaGenerator.python_type_to_json_schema(item_type),
                "description": description,
            }
        
        if origin is dict:
            return {
                "type": "object",
                "additionalProperties": True,
                "description": description,
            }
        
        # Default to string
        return {"type": "string", "description": description}
    
    @staticmethod
    def from_pydantic_model(model: type[BaseModel], name: str, description: str) -> ToolSchema:
        """Generate ToolSchema from a Pydantic model."""
        schema = model.model_json_schema()
        
        parameters = {}
        required_params = schema.get("required", [])
        
        # Extract properties
        for prop_name, prop_schema in schema.get("properties", {}).items():
            parameters[prop_name] = prop_schema
        
        return ToolSchema(
            name=name,
            description=description,
            parameters=parameters,
            required_parameters=required_params,
        )
    
    @staticmethod
    def from_function(func: Callable, name: Optional[str] = None, description: Optional[str] = None) -> ToolSchema:
        """Generate ToolSchema from a Python function."""
        import inspect
        
        name = name or func.__name__
        description = description or (func.__doc__ or "").strip().split("\n")[0]
        
        sig = inspect.signature(func)
        parameters = {}
        required_params = []
        
        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
            
            param_schema = SchemaGenerator.python_type_to_json_schema(
                param.annotation,
                description=param.annotation.__doc__ if hasattr(param.annotation, '__doc__') else ""
            )
            
            parameters[param_name] = param_schema
            
            # Required if no default value
            if param.default == inspect.Parameter.empty:
                required_params.append(param_name)
        
        # Get return type schema if available
        return_schema = None
        if sig.return_annotation != inspect.Signature.empty:
            return_schema = SchemaGenerator.python_type_to_json_schema(sig.return_annotation)
        
        return ToolSchema(
            name=name,
            description=description,
            parameters=parameters,
            required_parameters=required_params,
            output_schema=return_schema,
        )


class ToolSchemaRegistry:
    """Registry for managing tool schemas."""
    
    def __init__(self):
        self._schemas: Dict[str, ToolSchema] = {}
    
    def register(self, schema: ToolSchema) -> None:
        """Register a tool schema."""
        self._schemas[schema.name] = schema
    
    def register_from_function(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> ToolSchema:
        """Generate and register schema from a function."""
        schema = SchemaGenerator.from_function(func, name, description)
        self.register(schema)
        return schema
    
    def register_from_pydantic(
        self,
        model: type[BaseModel],
        name: str,
        description: str
    ) -> ToolSchema:
        """Generate and register schema from a Pydantic model."""
        schema = SchemaGenerator.from_pydantic_model(model, name, description)
        self.register(schema)
        return schema
    
    def get(self, name: str) -> Optional[ToolSchema]:
        """Get schema by name."""
        return self._schemas.get(name)
    
    def list_schemas(self) -> List[ToolSchema]:
        """Get all registered schemas."""
        return list(self._schemas.values())
    
    def to_openai_format(self) -> List[Dict[str, Any]]:
        """Export all schemas in OpenAI format."""
        return [schema.to_openai_format() for schema in self._schemas.values()]
    
    def to_anthropic_format(self) -> List[Dict[str, Any]]:
        """Export all schemas in Anthropic format."""
        return [schema.to_anthropic_format() for schema in self._schemas.values()]
    
    def to_json_schemas(self) -> List[Dict[str, Any]]:
        """Export all schemas as JSON schemas."""
        return [schema.to_json_schema() for schema in self._schemas.values()]
    
    def export_for_llm(self, format: str = "openai") -> List[Dict[str, Any]]:
        """Export schemas in LLM-compatible format.
        
        Args:
            format: One of "openai", "anthropic", "json"
        """
        if format == "openai":
            return self.to_openai_format()
        elif format == "anthropic":
            return self.to_anthropic_format()
        elif format == "json":
            return self.to_json_schemas()
        else:
            raise ValueError(f"Unsupported format: {format}")


class ToolSchemaValidator:
    """Validate tool inputs against their schemas."""
    
    @staticmethod
    def validate(schema: ToolSchema, input_data: Dict[str, Any]) -> bool:
        """Validate input against schema.
        
        Returns:
            True if valid, False otherwise
        """
        # Check required fields
        for required in schema.required_parameters:
            if required not in input_data:
                return False
        
        # Check types (basic)
        for param_name, param_value in input_data.items():
            if param_name not in schema.parameters:
                return False
            
            param_schema = schema.parameters[param_name]
            param_type = param_schema.get("type")
            
            if not ToolSchemaValidator._check_type(param_value, param_type):
                return False
        
        return True
    
    @staticmethod
    def _check_type(value: Any, json_type: str) -> bool:
        """Check if value matches JSON schema type."""
        type_checks = {
            "string": lambda v: isinstance(v, str),
            "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "number": lambda v: isinstance(v, (int, float)),
            "boolean": lambda v: isinstance(v, bool),
            "array": lambda v: isinstance(v, list),
            "object": lambda v: isinstance(v, dict),
            "null": lambda v: v is None,
        }
        
        check_func = type_checks.get(json_type)
        return check_func(value) if check_func else True


# Global registry instance
_global_registry = ToolSchemaRegistry()


def get_schema_registry() -> ToolSchemaRegistry:
    """Get the global schema registry."""
    return _global_registry


def register_tool_schema(schema: ToolSchema) -> None:
    """Register a tool schema globally."""
    _global_registry.register(schema)


def register_function_schema(
    func: Callable,
    name: Optional[str] = None,
    description: Optional[str] = None
) -> ToolSchema:
    """Register schema for a function globally."""
    return _global_registry.register_from_function(func, name, description)


__all__ = [
    "ToolSchema",
    "SchemaGenerator",
    "ToolSchemaRegistry",
    "ToolSchemaValidator",
    "get_schema_registry",
    "register_tool_schema",
    "register_function_schema",
]
