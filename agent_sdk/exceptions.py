"""Custom exception types for Agent SDK"""


class AgentSDKException(Exception):
    """Base exception for all Agent SDK errors"""

    def __init__(self, message: str, code: str = None, context: dict = None):
        self.message = message
        self.code = code
        self.context = context or {}
        super().__init__(message)

    def __str__(self):
        if self.code:
            return f"[{self.code}] {self.message}"
        return self.message


class ConfigError(AgentSDKException):
    """Raised when configuration is invalid or missing"""

    pass


class RateLimitError(AgentSDKException):
    """Raised when rate limit is exceeded"""

    pass


class ToolError(AgentSDKException):
    """Raised when tool execution fails"""

    pass


class LLMError(AgentSDKException):
    """Raised when LLM API call fails"""

    pass


class ValidationError(AgentSDKException):
    """Raised when input validation fails"""

    pass


class TimeoutError(AgentSDKException):
    """Raised when operation times out"""

    pass
