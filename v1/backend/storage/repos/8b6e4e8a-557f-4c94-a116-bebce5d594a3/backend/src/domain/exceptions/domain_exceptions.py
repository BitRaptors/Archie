"""Domain exceptions."""
from typing import Any


class DomainException(Exception):
    """Base domain exception."""

    def __init__(
        self,
        message: str,
        code: str = "DOMAIN_ERROR",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class NotFoundError(DomainException):
    """Entity not found."""

    def __init__(self, entity_type: str, entity_id: str):
        super().__init__(
            message=f"{entity_type} with id '{entity_id}' not found",
            code="NOT_FOUND",
            details={"entity_type": entity_type, "entity_id": entity_id},
        )


class ValidationError(DomainException):
    """Validation failed."""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details={"field": field} if field else {},
        )


class ConflictError(DomainException):
    """Entity already exists."""

    def __init__(self, entity_type: str, field: str, value: str):
        super().__init__(
            message=f"{entity_type} with {field}='{value}' already exists",
            code="CONFLICT",
            details={"entity_type": entity_type, "field": field, "value": value},
        )


class AuthorizationError(DomainException):
    """User not authorized."""

    def __init__(self, message: str = "Not authorized"):
        super().__init__(message=message, code="FORBIDDEN")


