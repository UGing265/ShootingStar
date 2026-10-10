"""Model API adapter package."""

from shootingstar.adapters.model_api.key_manager import GeminiKeyManager, KeySlot
from shootingstar.adapters.model_api.gemini_adapter import GeminiModelAdapter, GeminiTimeoutError

__all__ = [
    "GeminiKeyManager",
    "GeminiModelAdapter",
    "GeminiTimeoutError",
    "KeySlot",
]
