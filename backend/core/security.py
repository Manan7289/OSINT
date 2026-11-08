"""backend/core/security.py - Circuit Breaker, OPSEC Guard, and Hash-Chained Audit Logging.

M01: Security Vault, Rate Limiter, Circuit Breaker & OPSEC Guard.
"""

from __future__ import annotations

import hashlib
import threading
import time
from typing import Any, Dict, List, Literal, Tuple
from urllib.parse import urlparse


class CircuitOpenError(Exception):
    """Raised when an outbound request is attempted while circuit breaker is OPEN."""
    pass


CircuitState = Literal["CLOSED", "OPEN", "HALF_OPEN"]


class CircuitBreaker:
    """3-State Circuit Breaker for external API endpoints and connectors.
    
    States:
      - CLOSED: Normal operation. Success resets failure counter.
      - OPEN: Tripped after `threshold` consecutive failures. Outbound calls blocked for `cooldown` seconds.
      - HALF_OPEN: Cooldown has passed. Allows 1 probe call to determine recovery.
    """

    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 60.0) -> None:
        self.threshold = failure_threshold
        self.cooldown = cooldown_seconds
        self._lock = threading.Lock()
        # connector_id -> dict(state, failure_count, last_failure_time, probe_in_flight)
        self._breakers: Dict[str, Dict[str, Any]] = {}

    def _get_entry(self, connector_id: str) -> Dict[str, Any]:
        if connector_id not in self._breakers:
            self._breakers[connector_id] = {
                "state": "CLOSED",
                "failure_count": 0,
                "last_failure_time": 0.0,
                "probe_in_flight": False,
            }
        return self._breakers[connector_id]

    def get_state(self, connector_id: str) -> CircuitState:
        with self._lock:
            entry = self._get_entry(connector_id)
            state = entry["state"]
            if state == "OPEN":
                now = time.monotonic()
                if now - entry["last_failure_time"] >= self.cooldown:
                    entry["state"] = "HALF_OPEN"
                    entry["probe_in_flight"] = False
                    return "HALF_OPEN"
            return entry["state"]

    def can_execute(self, connector_id: str) -> bool:
        """Returns True if request may proceed, or raises CircuitOpenError."""
        with self._lock:
            entry = self._get_entry(connector_id)
            now = time.monotonic()
            state = entry["state"]

            if state == "CLOSED":
                return True

            if state == "OPEN":
                if now - entry["last_failure_time"] >= self.cooldown:
                    entry["state"] = "HALF_OPEN"
                    entry["probe_in_flight"] = True
                    return True
                raise CircuitOpenError(
                    f"Circuit breaker for '{connector_id}' is OPEN. "
                    f"Cooldown remaining: {max(0.0, self.cooldown - (now - entry['last_failure_time'])):.1f}s"
                )

            if state == "HALF_OPEN":
                if not entry["probe_in_flight"]:
                    entry["probe_in_flight"] = True
                    return True
                raise CircuitOpenError(f"Circuit breaker for '{connector_id}' is HALF_OPEN (probe in progress).")

            return True

    def record_success(self, connector_id: str) -> None:
        """Records a successful response, resetting the circuit to CLOSED."""
        with self._lock:
            entry = self._get_entry(connector_id)
            entry["state"] = "CLOSED"
            entry["failure_count"] = 0
            entry["probe_in_flight"] = False

    def record_failure(self, connector_id: str, status_code: int = 500) -> None:
        """Records a failure. Trips to OPEN if threshold is met."""
        with self._lock:
            entry = self._get_entry(connector_id)
            entry["probe_in_flight"] = False
            entry["failure_count"] += 1
            entry["last_failure_time"] = time.monotonic()

            if entry["failure_count"] >= self.threshold or entry["state"] == "HALF_OPEN":
                entry["state"] = "OPEN"

    def reset(self, connector_id: str | None = None) -> None:
        """Resets the circuit breaker state."""
        with self._lock:
            if connector_id:
                self._breakers.pop(connector_id, None)
            else:
                self._breakers.clear()


class OPSECGuard:
    """Enforces Operational Security policies (e.g. PASSIVE_ONLY mode).
    
    In PASSIVE_ONLY mode:
    - Direct connections to investigated target domains/IPs are blocked.
    - Aggregator/registry APIs (DNS-over-HTTPS, WHOIS/RDAP, CT logs, Shodan, etc.) are permitted.
    """

    ALLOWED_PASSIVE_SERVICES = {
        "cloudflare-dns.com",
        "rdap.org",
        "rdap.arin.net",
        "rdap.ripe.net",
        "rdap.apnic.net",
        "rdap.lacnic.net",
        "rdap.afrinic.net",
        "crt.sh",
        "stat.ripe.net",
        "urlscan.io",
        "internetdb.shodan.io",
        "services.nvd.nist.gov",
        "www.cisa.gov",
        "api.first.org",
        "threatfox-api.abuse.ch",
        "urlhaus-api.abuse.ch",
        "mb-api.abuse.ch",
        "api.gleif.org",
        "data.sec.gov",
        "api.opensanctions.org",
        "query.wikidata.org",
        "api.openalex.org",
        "web.archive.org",
        "api.gdeltproject.org",
        "api.github.com",
        "nominatim.openstreetmap.org",
        "api.shodan.io",
        "www.virustotal.com",
        "api.greynoise.io",
        "api.securitytrails.com",
        "search.censys.io",
        "otx.alienvault.com",
    }

    @classmethod
    def validate_request(
        cls,
        target_url_or_host: str,
        opsec_mode: str = "STANDARD",
        is_passive_connector: bool = True,
        investigated_target: str | None = None,
    ) -> Tuple[bool, str]:
        """Validates if an outbound request is permissible under the active OPSEC mode.
        
        Returns:
            (allowed: bool, reason: str)
        """
        if opsec_mode != "PASSIVE_ONLY":
            return True, "STANDARD mode allows all traffic"

        # In PASSIVE_ONLY mode, active connectors are blocked
        if not is_passive_connector:
            return False, "Active reconnaissance is blocked in PASSIVE_ONLY mode"

        # Parse target host
        host = target_url_or_host.strip()
        if "://" in host:
            parsed = urlparse(host)
            host = parsed.hostname or host

        host = host.lower()

        # If user attempts to connect directly to the target they are investigating
        if investigated_target:
            inv_target = investigated_target.lower().strip()
            if host == inv_target or host.endswith("." + inv_target):
                return False, f"Direct connection to investigated target '{host}' is forbidden in PASSIVE_ONLY mode"

        # Check if connecting to a recognized passive intermediary
        if any(allowed in host for allowed in cls.ALLOWED_PASSIVE_SERVICES):
            return True, f"Request to verified passive aggregator '{host}' permitted"

        # Default permit if connector is marked passive and not direct target
        return True, "Passive request permitted"


class HashChainedAuditLogger:
    """Tamper-evident append-only ledger using SHA-256 cryptographic hash chaining.
    
    Chain formula:
      H_k = SHA256(H_{k-1} || seq_no || timestamp || action || details)
      Genesis: H_0 = "0" * 64
    """

    GENESIS_HASH = "0" * 64

    @classmethod
    def compute_entry_hash(
        cls, prev_hash: str, seq_no: int, timestamp: str, action: str, details: str
    ) -> str:
        """Computes deterministic SHA-256 hash for an audit log entry."""
        payload = f"{prev_hash}|{seq_no}|{timestamp}|{action}|{details}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @classmethod
    def verify_chain(cls, entries: List[Dict[str, Any]]) -> Tuple[bool, int, str]:
        """Verifies the cryptographic integrity of an ordered list of audit entries.
        
        Returns:
            (is_valid: bool, verified_count: int, error_message: str)
        """
        if not entries:
            return True, 0, "Audit log is empty (valid)"

        current_prev_hash = cls.GENESIS_HASH
        for idx, entry in enumerate(entries):
            seq = entry.get("seq_no", idx + 1)
            ts = entry.get("timestamp", "")
            action = entry.get("action", "")
            details = entry.get("details", "")
            entry_prev = entry.get("prev_hash", "")
            entry_hash = entry.get("entry_hash", "")

            # Check link to previous hash
            if entry_prev != current_prev_hash:
                return (
                    False,
                    idx,
                    f"Hash break at seq_no={seq}: expected prev_hash '{current_prev_hash}', got '{entry_prev}'",
                )

            # Recompute hash
            expected_hash = cls.compute_entry_hash(current_prev_hash, seq, ts, action, details)
            if entry_hash != expected_hash:
                return (
                    False,
                    idx,
                    f"Tampered record at seq_no={seq}: expected hash '{expected_hash}', found '{entry_hash}'",
                )

            current_prev_hash = entry_hash

        return True, len(entries), "Audit log verified: cryptographic chain intact"


# Singletons
circuit_breaker = CircuitBreaker()
