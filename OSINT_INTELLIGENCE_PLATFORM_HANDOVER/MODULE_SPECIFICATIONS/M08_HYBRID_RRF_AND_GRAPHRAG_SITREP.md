# M08 — Hybrid RRF Search & Grounded GraphRAG SitRep Generator

- **Target Files:** `backend/ai/search_rrf.py`, `backend/ai/assistant.py`
- **Action:**
  1. Fix `validate_citations()` in `backend/ai/assistant.py` so `is_valid = (valid_ratio == 1.0 and len(stripped_sentences) == 0)`.
  2. Add `generate_sweep_briefing(sweep_id: str)` which synthesizes the top deltas, sanctions matches, geofence breaches, and spatial clusters into an executive Markdown SitRep where every claim carries a `[PROV:...]` or `[DELTA:...]` citation.
