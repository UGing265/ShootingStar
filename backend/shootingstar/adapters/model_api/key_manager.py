"""Gemini API key management, rate-limit awareness, and secret masking."""

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

def load_env_file() -> None:
    """Loads key-value pairs from root .env into os.environ if present."""
    env_path = Path(".env")
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key not in os.environ:
                    os.environ[key] = val
    except Exception as e:
        logger.warning("Failed to load .env file in key_manager: %s", e)


def mask_secret(secret: str) -> str:
    """Masks secret key to prevent leakage into logs, DB, or DTOs."""
    if not secret:
        return "[EMPTY]"
    if len(secret) <= 8:
        return "****"
    return f"{secret[:4]}...{secret[-4:]}"
@dataclass
class KeySlot:
    index: int
    api_key: str
    project_id: str
    is_active: bool = True
    failure_count: int = 0
    disabled_reason: Optional[str] = None
    cooldown_until: float = 0.0

    def is_available(self, current_time: Optional[float] = None) -> bool:
        if not self.is_active:
            return False
        now = current_time if current_time is not None else time.time()
        return now >= self.cooldown_until
    def get_masked_display(self) -> str:
        return f"Slot #{self.index} (Project: {self.project_id}, Key: {mask_secret(self.api_key)}, Active: {self.is_active})"


class GeminiKeyManager:
    """Manages up to 10 operator-owned Gemini keys with project-level quota discipline.

    INVARIANTS:
    1. Maximum 10 key slots.
    2. Duplicates detected and deduplicated.
    3. Keys are never logged in plaintext or exported to DB/DTOs.
    4. HTTP 429 RESOURCE_EXHAUSTED is project-level: Sets cooldown for all slots in that project.
       Rotation only permitted across DIFFERENT projects that are not on cooldown.
    5. HTTP 401/403 marks key as disabled with reason and alerts admin.
    """

    MAX_KEYS = 10
    DEFAULT_COOLDOWN_SECONDS = 60.0

    def __init__(
        self,
        key_configs: Optional[List[Tuple[str, str]]] = None,
        cooldown_seconds: Optional[float] = None,
    ):
        """Initializes with list of (api_key, project_id) tuples and cooldown."""
        self._slots: List[KeySlot] = []
        self._current_index: int = 0
        load_env_file()

        env_cd = os.environ.get("SHOOTINGSTAR_GEMINI_COOLDOWN_SECONDS")
        if cooldown_seconds is not None:
            self.cooldown_seconds = cooldown_seconds
        elif env_cd:
            try:
                self.cooldown_seconds = float(env_cd)
            except ValueError:
                self.cooldown_seconds = self.DEFAULT_COOLDOWN_SECONDS
        else:
            self.cooldown_seconds = self.DEFAULT_COOLDOWN_SECONDS

        configs = key_configs if key_configs is not None else self._load_from_env()
        seen_keys = set()
        for i, (key, proj) in enumerate(configs):
            if len(self._slots) >= self.MAX_KEYS:
                logger.warning("Reached maximum allowed Gemini keys (%d), ignoring remaining", self.MAX_KEYS)
                break
            clean_key = key.strip()
            if not clean_key or clean_key in seen_keys:
                logger.warning("Skipping duplicate or empty key in slot %d", i)
                continue
            seen_keys.add(clean_key)
            self._slots.append(
                KeySlot(
                    index=len(self._slots),
                    api_key=clean_key,
                    project_id=proj.strip() if proj else f"project-{len(self._slots)}",
                    is_active=True,
                )
            )

    @classmethod
    def _load_from_env(cls) -> List[Tuple[str, str]]:
        """Loads keys from SHOOTINGSTAR_GEMINI_KEYS env format 'key1,key2' or 'key1:proj1,key2:proj2', or single GEMINI_API_KEY."""
        load_env_file()
        configs: List[Tuple[str, str]] = []
        multi_keys = os.environ.get("SHOOTINGSTAR_GEMINI_KEYS", "").strip()
        if multi_keys:
            items = multi_keys.split(",")
            for i, it in enumerate(items):
                parts = it.split(":", 1)
                k = parts[0].strip()
                # If no colon provided, assign project-i so comma-separated keys operate independently
                p = parts[1].strip() if len(parts) > 1 else f"project-{i}"
                if k:
                    configs.append((k, p))
        else:
            single = os.environ.get("GEMINI_API_KEY", "").strip()
            if single:
                configs.append((single, "default"))
        return configs

    @property
    def total_slots(self) -> int:
        return len(self._slots)

    @property
    def active_slots(self) -> int:
        return sum(1 for s in self._slots if s.is_active)

    def get_next_slot(self, current_time: Optional[float] = None) -> Optional[KeySlot]:
        """Returns next available key slot using round-robin among active, non-cooling slots."""
        if not self._slots:
            return None
        now = current_time if current_time is not None else time.time()
        available_list = [s for s in self._slots if s.is_available(now)]
        if not available_list:
            return None

        slot = available_list[self._current_index % len(available_list)]
        self._current_index += 1
        return slot

    def record_401_403(self, slot_index: int, error_msg: str) -> None:
        """Disables invalid or revoked key."""
        for s in self._slots:
            if s.index == slot_index:
                s.is_active = False
                s.disabled_reason = f"Auth Failure: {error_msg}"
                logger.error("Disabled key slot %d due to auth failure: %s", slot_index, error_msg)

    def record_429_quota_exhausted(self, slot_index: int, cooldown_seconds: Optional[float] = None) -> None:
        """Records 429 quota exhaustion. Sets project-level cooldown across all slots of that project."""
        target_slot = next((s for s in self._slots if s.index == slot_index), None)
        if not target_slot:
            return

        cd_duration = cooldown_seconds if cooldown_seconds is not None else self.cooldown_seconds
        target_until = time.time() + cd_duration

        affected_count = 0
        for s in self._slots:
            if s.project_id == target_slot.project_id:
                s.cooldown_until = max(s.cooldown_until, target_until)
                affected_count += 1

        logger.warning(
            "Project '%s' received 429 RESOURCE_EXHAUSTED. Set cooldown for %.1fs across %d slot(s).",
            target_slot.project_id,
            cd_duration,
            affected_count,
        )
