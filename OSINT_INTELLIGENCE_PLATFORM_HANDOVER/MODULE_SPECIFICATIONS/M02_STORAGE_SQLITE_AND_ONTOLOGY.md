# M02 — 20-Table SQLite WAL + FTS5 + R*Tree Storage & Ontology

- **Target Files:** `backend/core/database.py`, `backend/core/ontology.py`
- **Action:** Retain all 14 existing tables and add the 6 new v3.0 tables (`geo_tracks`, `sweep_runs`, `sweep_deltas`, `sanctions_index`, `geofence_zones`, `visual_assets`, `consented_face_gallery`) defined in `ARCHITECTURE/DATABASE_AND_DATA_MODEL.md`.
- **Key Methods to Add to `DatabaseManager` (`backend/core/database.py`):**
  - `insert_geo_tracks_batch(tracks: list[dict]) -> int`
  - `query_geo_tracks(layer_types: list[str], since_iso: str, until_iso: str, bbox: tuple | None) -> list[dict]`
  - `upsert_sanctions_batch(records: list[dict]) -> int`
  - `match_sanction(mmsi: str = None, imo: str = None, icao24: str = None, tail_number: str = None, name: str = None) -> dict | None`
  - `create_sweep_run(investigation_id: str) -> str`
  - `complete_sweep_run(sweep_id: str, stats: dict, deltas: list[dict]) -> None`
  - `save_visual_asset(asset: dict) -> str`
  - `find_similar_visual_assets(phash_hex: str, max_hamming: int = 10) -> list[dict]`
