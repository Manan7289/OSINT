# M01 — Configuration, Security Gateway, DPAPI Vault & CircuitBreaker

- **Target Files:** `backend/core/config.py`, `backend/core/security.py`
- **Action:** Retain existing implementation and apply mandatory thread-safety fix to `CircuitBreaker`.
- **Required Fix in `backend/core/security.py`:**
  ```python
  class CircuitBreaker:
      def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 60.0):
          self.failure_threshold = failure_threshold
          self.recovery_timeout = recovery_timeout
          self._lock = threading.Lock()
          self.failures: dict[str, int] = {}
          self.state: dict[str, str] = {}
          self.last_failure_time: dict[str, float] = {}
  ```
  Ensure `allow_request(source)`, `record_success(source)`, and `record_failure(source)` acquire `with self._lock:`.
- **SSRF Allowlist & Protection:** Retain `SSRFGuard.validate_url(url)` blocking loopback, RFC 1918 private networks, link-local `169.254.0.0/16`, and non-HTTP(S) schemes.
