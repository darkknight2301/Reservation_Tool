"""
Custom exception hierarchy.

Services raise these domain-specific exceptions instead of HTTPException so
that business logic stays framework-agnostic (testable without FastAPI in
the loop). A single global exception handler (see
``app.middleware.error_handler``) translates each exception type into the
appropriate HTTP status code and the standard error envelope.
"""
from typing import Any, Dict, Optional


class AppError(Exception):
    """Base class for all application-raised (expected) errors."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppError):
    """Raised when a requested entity does not exist."""

    status_code = 404
    error_code = "NOT_FOUND"


class ConflictError(AppError):
    """Raised when an operation would violate a uniqueness/business constraint."""

    status_code = 409
    error_code = "CONFLICT"


class ValidationAppError(AppError):
    """Raised when input fails a business validation rule (beyond schema-level)."""

    status_code = 422
    error_code = "VALIDATION_ERROR"


class AuthenticationError(AppError):
    """Raised when credentials are missing, invalid, or a token is unusable."""

    status_code = 401
    error_code = "AUTHENTICATION_ERROR"


class AuthorizationError(AppError):
    """Raised when an authenticated user lacks permission for an action."""

    status_code = 403
    error_code = "AUTHORIZATION_ERROR"


class AccountNotApprovedError(AuthenticationError):
    """Raised when a registered user has not yet been approved by a Lead+."""

    error_code = "ACCOUNT_NOT_APPROVED"


class AccountDisabledError(AuthenticationError):
    """Raised when a user account has been disabled."""

    error_code = "ACCOUNT_DISABLED"


class ReservationConflictError(ConflictError):
    """Raised when a requested reservation window overlaps an active one."""

    error_code = "RESERVATION_CONFLICT"


class SetupUnavailableError(ConflictError):
    """Raised when a setup is not in a state that allows the requested action."""

    error_code = "SETUP_UNAVAILABLE"


class InvalidStateTransitionError(ConflictError):
    """Raised when an entity's status cannot transition to the requested value."""

    error_code = "INVALID_STATE_TRANSITION"


class SwapMappingValidationError(ValidationAppError):
    """Raised when a multi-node swap mapping fails the node-uniqueness/availability rules."""

    error_code = "SWAP_MAPPING_INVALID"


class ImportValidationError(ValidationAppError):
    """Raised when an uploaded Excel file fails structural or row validation."""

    error_code = "IMPORT_VALIDATION_ERROR"

    def __init__(self, message: str, row_errors: Optional[Any] = None) -> None:
        super().__init__(message, details={"row_errors": row_errors or []})
