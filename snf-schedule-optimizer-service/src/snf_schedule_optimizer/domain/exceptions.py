class DomainException(Exception):
    """Base class for domain-layer exceptions."""


class SecurityError(DomainException):
    """Raised when a cross-tenant access is attempted."""


class DataIntegrityError(DomainException):
    """Raised when data invariants are violated."""


class EntityNotFoundError(DomainException):
    """Raised when a requested entity cannot be found in the data store."""


class InvalidRequestError(DomainException):
    """Raised when the service layer receives a malformed or incomplete command query request."""


class BusinessRuleViolationError(DomainException):
    """Raised when a domain business rule is violated during a command."""
