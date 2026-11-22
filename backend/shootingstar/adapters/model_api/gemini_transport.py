"""Gemini HTTP transport with bounded retries and project-level key cooldown."""

import json
import os
import socket
import time
import urllib.error
import urllib.request

from shootingstar.adapters.model_api.key_manager import GeminiKeyManager


class GeminiAPIError(Exception):
    """Gemini request or response failed."""


class GeminiQuotaExceededError(GeminiAPIError):
    """No project quota available."""


class GeminiAuthError(GeminiAPIError):
    """Gemini rejected a key."""


class GeminiTimeoutError(GeminiAPIError):
    """Gemini request timed out."""


class GeminiTransport:
    def __init__(self, key_manager=None, model_name=None, timeout_seconds=None):
        self.key_manager = key_manager or GeminiKeyManager()
        self.model_name = model_name or os.environ.get("SHOOTINGSTAR_GEMINI_MODEL") or os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash"
        timeout = timeout_seconds or os.environ.get("SHOOTINGSTAR_GEMINI_TIMEOUT_SECONDS") or os.environ.get("GEMINI_TIMEOUT_SECONDS") or 90
        try:
            self.timeout_seconds = float(timeout)
        except ValueError:
            self.timeout_seconds = 90.0

    def send(self, request_body):
        """Send one logical request; retry transient HTTP and rotate unavailable keys."""
        data = json.dumps(request_body).encode("utf-8")
        last_error = None
        for attempt in range(max(3, self.key_manager.total_slots * 2)):
            slot = self.key_manager.get_next_slot()
            if slot is None:
                raise last_error or GeminiQuotaExceededError("No available Gemini API key slots")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "x-goog-api-key": slot.api_key}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8")), slot.index
            except urllib.error.HTTPError as error:
                if error.code in (401, 403):
                    self.key_manager.record_401_403(slot.index, f"HTTP {error.code}")
                    last_error = GeminiAuthError(f"Gemini authentication failed (HTTP {error.code})")
                elif error.code == 429:
                    self.key_manager.record_429_quota_exhausted(slot.index)
                    last_error = GeminiQuotaExceededError("Gemini quota exhausted (HTTP 429)")
                elif error.code in (500, 502, 503, 504):
                    last_error = GeminiAPIError(f"Gemini server error (HTTP {error.code})")
                    time.sleep(min(1.5 ** attempt, 6.0))
                else:
                    raise GeminiAPIError(f"Gemini request failed (HTTP {error.code})") from error
            except (TimeoutError, socket.timeout) as error:
                last_error = GeminiTimeoutError("Gemini request timed out")
            except urllib.error.URLError as error:
                if isinstance(error.reason, (TimeoutError, socket.timeout)):
                    last_error = GeminiTimeoutError("Gemini request timed out")
                else:
                    raise GeminiAPIError("Gemini network request failed") from error
            except (ValueError, UnicodeError) as error:
                raise GeminiAPIError("Gemini returned invalid JSON") from error
        raise last_error or GeminiAPIError("Gemini request failed")
