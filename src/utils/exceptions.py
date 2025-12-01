"""
Custom exception hierarchy for categorized error handling
"""


class AgentException(Exception):
    """Base exception for all agent-related errors"""
    def __init__(self, message: str, agent_name: str = None, recoverable: bool = True):
        self.agent_name = agent_name
        self.recoverable = recoverable
        super().__init__(message)


class LLMAPIError(AgentException):
    """LLM API call failed (rate limit, timeout, auth, model error)"""
    def __init__(self, message: str, status_code: int = None, provider: str = "groq"):
        self.status_code = status_code
        self.provider = provider
        super().__init__(message, recoverable=True)


class DataValidationError(AgentException):
    """Data doesn't meet expected schema or quality standards"""
    def __init__(self, message: str, missing_columns: list = None, invalid_rows: int = 0):
        self.missing_columns = missing_columns or []
        self.invalid_rows = invalid_rows
        super().__init__(message, recoverable=False)


class SchemaError(AgentException):
    """Schema mismatch between expected and actual data"""
    def __init__(self, message: str, expected_schema: dict = None, actual_schema: dict = None):
        self.expected_schema = expected_schema
        self.actual_schema = actual_schema
        super().__init__(message, recoverable=False)


class JSONParseError(AgentException):
    """Failed to parse JSON from LLM response"""
    def __init__(self, message: str, raw_response: str = None, agent_name: str = None):
        self.raw_response = raw_response
        super().__init__(message, agent_name=agent_name, recoverable=True)


class TimeoutError(AgentException):
    """Operation timed out"""
    def __init__(self, message: str, timeout_seconds: int = None):
        self.timeout_seconds = timeout_seconds
        super().__init__(message, recoverable=True)


class InsufficientDataError(AgentException):
    """Not enough data to perform analysis"""
    def __init__(self, message: str, required_rows: int = None, actual_rows: int = None):
        self.required_rows = required_rows
        self.actual_rows = actual_rows
        super().__init__(message, recoverable=False)


class EvaluationFailedError(AgentException):
    """Insights failed quality evaluation after max retries"""
    def __init__(self, message: str, quality_score: float = None, attempts: int = 0):
        self.quality_score = quality_score
        self.attempts = attempts
        super().__init__(message, recoverable=False)
