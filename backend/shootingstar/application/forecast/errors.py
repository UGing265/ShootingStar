"""Forecast history errors."""

from shootingstar.domain.exceptions import DomainError


class InsufficientHistoryError(DomainError):
    """Insufficient continuous completed candle history for the forecast."""
