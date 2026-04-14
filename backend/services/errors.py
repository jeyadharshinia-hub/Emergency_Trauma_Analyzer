class NonMedicalImageError(Exception):
    """Raised when uploaded image is not a valid medical scan."""


class AIServiceUnavailableError(Exception):
    """Raised when external AI service is unavailable or misconfigured."""


class AIContractError(Exception):
    """Raised when AI response violates expected JSON contract."""

