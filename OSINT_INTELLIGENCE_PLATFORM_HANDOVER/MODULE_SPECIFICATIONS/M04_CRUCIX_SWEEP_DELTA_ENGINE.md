# M04 — Crucix-Style Scheduled Sweep & Delta Analysis Engine

- **Target File:** `backend/collectors/sweep_delta.py`
- **Action:** Create `SweepDeltaEngine` to compare the current sweep state $S_t$ against $S_{t-1}$ and emit structured `SweepDelta` records:
  - `NEW_ENTITY`: Newly discovered high-priority entity or hazard event.
  - `SANCTION_MATCH_DETECTED`: Active aircraft or vessel matched against `sanctions_index` (`OFAC SDN`).
  - `ESCALATED_RISK`: Entity belief/risk score increased by $\ge 0.15$ or emergency squawk `7500`/`7600`/`7700`.
  - `ENTERED_GEOFENCE`: Track point crossed into an active `geofence_zones` polygon.
  - `AIS_DARK_GAP`: Vessel reappeared after $> 2	ext{ hours}$ gap with $> 15	ext{ km}$ displacement.
  - `RESOLVED_EVENT`: Previous active hazard/alert expired.
