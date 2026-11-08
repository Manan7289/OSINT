# M03 — Concurrent OSINT Collector Orchestrator & 18 Live Feeds

- **Target Files:** `backend/collectors/orchestrator.py`, `backend/collectors/aviation_adapter.py`, `backend/collectors/maritime_adapter.py`, `backend/collectors/satellite_adapter.py`, `backend/collectors/natural_events_adapter.py`, `backend/collectors/camera_adapter.py`, `backend/collectors/sanctions_loader.py`
- **Action:**
  1. Refactor `CollectorOrchestrator.run_collection()` to use `concurrent.futures.ThreadPoolExecutor(max_workers=8)` so all active adapters run in parallel.
  2. Implement the 6 new geospatial/kinetic adapter modules as specified in `RESEARCH/DATA_SOURCE_AND_INTEGRATION_PLAN.md`.
  3. Tag every returned feature/track with an accurate `telemetry_status` (`LIVE`, `DELAYED`, `ORBITAL_PROPAGATED`, `HISTORICAL`, or `OFFLINE_BOOTSTRAP`).
