class DomainException(Exception):
    """Base class for domain-layer exceptions."""


class SecurityError(DomainException):
    """Raised when a cross-tenant access is attempted."""


class DataIntegrityError(DomainException):
    """Raised when data invariants are violated."""
