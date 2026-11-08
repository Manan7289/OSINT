"""backend/core/config.py - Configuration, CryptoVault, and TokenBucketRateLimiter.

M01: Security Vault, Rate Limiter, Circuit Breaker & OPSEC Guard.
"""

from __future__ import annotations

import base64
import os
import threading
import time
from pathlib import Path
from typing import Dict, Tuple

from cryptography.fernet import Fernet, InvalidToken

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.environ.get("LOCALOSINT_DATA_DIR", BASE_DIR / "data")).resolve()
FRONTEND_DIR = (BASE_DIR / "frontend").resolve()
DB_PATH = Path(os.environ.get("LOCALOSINT_DB_PATH", DATA_DIR / "localosint.db")).resolve()

# Network settings
HOST = os.environ.get("LOCALOSINT_HOST", "127.0.0.1")
PORT = int(os.environ.get("LOCALOSINT_PORT", "8000"))

# AI / Ollama settings
OLLAMA_URL = os.environ.get("LOCALOSINT_OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("LOCALOSINT_OLLAMA_MODEL", "llama3.1:8b")

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)


class CryptoVault:
    """Fernet (AES-128-CBC + HMAC-SHA256) authenticated encryption for API keys."""

    def __init__(self, key_path: Path | None = None, explicit_key: str | None = None) -> None:
        self.key_path = key_path or (DATA_DIR / ".vault_key")
        self._key = self._load_or_create_key(explicit_key)
        self._fernet = Fernet(self._key)

    def _load_or_create_key(self, explicit_key: str | None) -> bytes:
        if explicit_key:
            raw = explicit_key.encode("utf-8")
            if len(raw) == 44:
                return raw
            # Derive 32-byte urlsafe base64 key from arbitrary secret
            import hashlib
            digest = hashlib.sha256(raw).digest()
            return base64.urlsafe_b64encode(digest)

        env_key = os.environ.get("LOCALOSINT_SECRET_KEY")
        if env_key:
            raw = env_key.encode("utf-8")
            if len(raw) == 44:
                return raw
            import hashlib
            digest = hashlib.sha256(raw).digest()
            return base64.urlsafe_b64encode(digest)

        if self.key_path.exists():
            key_bytes = self.key_path.read_bytes().strip()
            if len(key_bytes) == 44:
                return key_bytes

        # Generate new key
        new_key = Fernet.generate_key()
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        self.key_path.write_bytes(new_key)
        try:
            # Set restrictive permissions where supported
            os.chmod(self.key_path, 0o600)
        except Exception:
            pass
        return new_key

    def encrypt(self, plaintext: str) -> str:
        """Encrypts a plaintext string and returns a base64 Fernet token."""
        if not plaintext:
            return ""
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypts a Fernet token. Returns empty string on invalid/corrupted token."""
        if not ciphertext:
            return ""
        try:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except (InvalidToken, Exception):
            return ""

    @staticmethod
    def mask_key(key: str) -> str:
        """Masks an API key for safe display (e.g. shod****3210)."""
        if not key:
            return ""
        if len(key) <= 8:
            return "****"
        prefix = key[:4]
        suffix = key[-4:]
        return f"{prefix}****{suffix}"


class TokenBucketRateLimiter:
    """Thread-safe per-source Token Bucket Rate Limiter.
    
    Formula: T_new = min(C, T_old + dt * (RPM / 60))
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # connector_id -> (tokens: float, last_updated: float, capacity: float)
        self._buckets: Dict[str, Tuple[float, float, float]] = {}

    def acquire(self, connector_id: str, rpm: int = 30) -> Tuple[bool, float]:
        """Attempts to consume 1 token for connector_id.
        
        Returns:
            (allowed: bool, wait_seconds: float)
        """
        if rpm <= 0:
            return True, 0.0

        capacity = float(max(1, rpm))
        rate_per_sec = float(rpm) / 60.0
        now = time.monotonic()

        with self._lock:
            if connector_id not in self._buckets:
                # Initialize full bucket
                self._buckets[connector_id] = (capacity - 1.0, now, capacity)
                return True, 0.0

            tokens, last_time, _ = self._buckets[connector_id]
            dt = max(0.0, now - last_time)
            tokens = min(capacity, tokens + (dt * rate_per_sec))

            if tokens >= 1.0:
                tokens -= 1.0
                self._buckets[connector_id] = (tokens, now, capacity)
                return True, 0.0
            else:
                needed = 1.0 - tokens
                wait_seconds = needed / rate_per_sec if rate_per_sec > 0 else 1.0
                self._buckets[connector_id] = (tokens, now, capacity)
                return False, wait_seconds

    def reset(self, connector_id: str | None = None) -> None:
        """Resets token state for a specific connector or all connectors."""
        with self._lock:
            if connector_id:
                self._buckets.pop(connector_id, None)
            else:
                self._buckets.clear()


# Singletons
vault = CryptoVault()
rate_limiter = TokenBucketRateLimiter()
