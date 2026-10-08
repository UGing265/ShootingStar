"""Domain exceptions for ShootingStar."""


class DomainError(Exception):
    """Base exception for domain layer errors."""
    pass


class InvalidCandleError(DomainError):
    """Raised when candle data violates financial or temporal invariants."""
    pass


class DiscontinuousDataError(DomainError):
    """Raised when expected interval continuity is broken unexpectedly."""
    pass
