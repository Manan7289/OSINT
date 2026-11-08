# M05 — Blocked Fellegi-Sunter EM Entity Resolution & OFAC Matcher

- **Target File:** `backend/core/entity_resolution.py`
- **Action:**
  1. Apply `Beta(1, 1)` Laplace smoothing to `m_probs` and `u_probs` in `FellegiSunterResolver.fit_em()`:
     ```python
     self.m_probs = np.clip((1.0 + m_num) / (2.0 + g_sum), 0.01, 0.999)
     self.u_probs = np.clip((1.0 + u_num) / (2.0 + one_minus_g_sum), 0.001, 0.99)
     ```
  2. Add `cross_reference_sanctions(entity_dict, db)` to deterministically match `mmsi`, `imo`, `icao24`, `tail_number`, and Jaro-Winkler $\ge 0.94$ vessel/aircraft names against `sanctions_index`.
