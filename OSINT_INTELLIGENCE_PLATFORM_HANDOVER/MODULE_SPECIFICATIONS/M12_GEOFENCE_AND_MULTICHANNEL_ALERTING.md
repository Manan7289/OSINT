# M12 — Geofence Watch Zones, SSE Real-Time Push & Multi-Channel Alerting

- **Target File:** `backend/alerts/alert_engine.py`
- **Action:**
  - Implement deterministic Ray-Casting `point_in_polygon(lat, lon, polygon_coords)` to evaluate all active `geofence_zones` during every sweep.
  - Provide `GET /api/v1/stream` (Server-Sent Events) pushing real-time `sweep_completed`, `geofence_breach`, and `sanction_match` events to the browser HUD.
  - Implement optional outbound notification dispatchers for **Telegram Bot API** (`https://api.telegram.org/bot{token}/sendMessage`) and **Discord Webhooks** when configured in the Credential Vault or `.env`.
