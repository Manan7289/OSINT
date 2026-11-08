# 08 — AI AND CORRELATION ENGINE SPECIFICATION (`M04`, `M05`, `M06`, `M07`, `M08`, `M09`)

**Target Repository:** [`https://github.com/Manan7289/OSINT.git`](https://github.com/Manan7289/OSINT.git)  
**Scope:** Mathematical and Algorithmic Specification of the Cross-Source Correlation Engine, Sweep-Delta Analyzer, Sanctions Matcher, Spatiotemporal Co-Traveler/Anomaly Detector, Hybrid RRF Search, and Grounded GraphRAG Assistant

---

## 1. Cross-Source Correlation & Intelligence Fusion Pipeline

Unlike basic dashboards that plot isolated feeds on separate tabs, `LocalOSINT v3.0` fuses signals across **kinetic geospatial tracks (aircraft, vessels, satellites)**, **event feeds (earthquakes, wildfires, conflict news, weather)**, **sanctions lists (OFAC SDN)**, and **cyber infrastructure (CVEs, domains, IPs, certificates)** into a single unified Knowledge Graph.

### 1.1 Automated Cross-Source Correlation Rules (`backend/core/spatiotemporal.py` & `entity_resolution.py`)

| Rule ID | Correlation Name | Trigger Condition | Generated Graph Edge / Alert |
| :--- | :--- | :--- | :--- |
| **CORR-01** | **Sanctioned Kinetic Asset Match** | Aircraft `icao24`/tail or Vessel `mmsi`/`imo`/name matches an `OFAC SDN` record (exact ID or Jaro-Winkler $\ge 0.94$ on vessel name + flag). | Creates `SANCTIONED_UNDER` edge to `SANCTIONED_ENTITY` + sets `risk_score = max(risk_score, 0.92)` + emits `CRITICAL` delta. |
| **CORR-02** | **Event-to-Asset Spatial Proximity** | A kinetic asset (`AIRCRAFT`, `VESSEL`) or critical infrastructure (`DOMAIN`/`IP` geolocated, `CAMERA`) is within $D \le 50	ext{ km}$ and $\Delta t \le 2	ext{ hours}$ of a high-severity `EVENT` (Earthquake $\ge 	ext{M5.0}$, Wildfire, Conflict Event, Emergency Squawk). | Creates `PROXIMATE_TO_EVENT` edge with Haversine distance $d_{	ext{km}}$ and subjective logic opinion $\omega$. |
| **CORR-03** | **Maritime Co-Traveler / Ship-to-Ship (STS) Rendezvous** | Two vessels $V_1, V_2$ maintain Haversine distance $d(V_1, V_2) \le 0.5	ext{ km}$ with speeds $s_1, s_2 < 2.0	ext{ knots}$ outside a known port for $\ge 30	ext{ minutes}$ (especially if one is sanctioned or recently had an AIS dark gap). | Creates `POTENTIAL_STS_TRANSFER` edge between $V_1$ and $V_2$ + emits `HIGH` severity alert. |
| **CORR-04** | **Cyber-to-Physical Infrastructure Attribution** | An `ORGANIZATION` or `GOVERNMENT_AGENCY` linked to an exploited `VULNERABILITY` (`CISA KEV`) or `MALWARE_URL` shares an operator/owner name or headquarters coordinate with tracked physical assets or regional crisis events. | Creates `OPERATES_ASSET` / `LOCATED_AT` cross-domain edges in the graph. |
| **CORR-05** | **Visual-to-Geospatial Correlation** | An uploaded image in `M11` contains EXIF GPS coordinates $(\phi, \lambda)$ within $10	ext{ km}$ of an active `EVENT` or matches an existing OSINT image via `pHash` ($d_H \le 10$). | Creates `CAPTURED_NEAR` and `VISUALLY_SIMILAR_TO` edges and plots a camera-pin marker on the 2D/3D globe. |

---

## 2. Crucix-Style Sweep-Delta Engine (`backend/collectors/sweep_delta.py`)

Inspired by [`calesthio/Crucix`](https://github.com/calesthio/Crucix) (clean-room engineered in Python), every scheduled or manual collection sweep creates a `sweep_runs` record ($S_t$) and compares the resulting world state against the immediately preceding sweep ($S_{t-1}$).

### 2.1 Delta Classification Taxonomy
For each entity or track updated in Sweep $S_t$:
1. **`NEW_ENTITY`**: Entity ID was not present in SQLite prior to $S_t$.
2. **`SANCTION_MATCH_DETECTED`**: An active aircraft or vessel matched an OFAC SDN entry during $S_t$.
3. **`ESCALATED_RISK`**: Entity's fused risk/belief score increased by $\Delta b = b_t - b_{t-1} \ge 0.15$, or an aircraft changed its squawk to `7500`/`7600`/`7700`, or an earthquake of magnitude $\ge 5.5$ occurred.
4. **`ENTERED_GEOFENCE`**: An entity's $(	ext{lat}_t, 	ext{lon}_t)$ is inside an active user-defined `geofence_zones` polygon whereas $(	ext{lat}_{t-1}, 	ext{lon}_{t-1})$ was outside.
5. **`AIS_DARK_GAP`**: A tracked vessel reappeared after an unscheduled AIS transmission gap $> 2	ext{ hours}$.
6. **`DEESCALATED_OR_RESOLVED`**: An active weather/disaster alert expired or an entity exited a monitored geofence.

### 2.2 Composite Sweep Escalation Score ($E_{	ext{sweep}}$)
Each sweep computes an overall **Global Tension / Escalation Index** $E_{	ext{sweep}} \in [0, 100]$ displayed in the Top Command Bar:
$$E_{	ext{sweep}} = \min\left(100, \; 15 \cdot N_{	ext{sanction}} + 10 \cdot N_{	ext{geofence}} + 8 \cdot N_{	ext{emergency}} + 3 \cdot N_{	ext{escalated}} + 0.5 \cdot N_{	ext{new\_high\_risk}}ight)$$

---

## 3. Existing Core Algorithms (Retained & Hardened from v2.0)

### 3.1 Blocked Fellegi-Sunter EM Entity Resolution (`backend/core/entity_resolution.py`)
- Uses 3-pass blocking (Identifier Prefix, Soundex Phonetic Key, $1^\circ 	imes 1^\circ$ Spatial Grid Tile) to avoid $O(N^2)$ comparisons.
- **Required Fix in v3.0:** Add `Beta(1, 1)` Laplace smoothing to the M-step inside `fit_em()` so $m_k$ and $u_k$ never collapse to `0.0` or `1.0` on small batches:
  $$m_k^{(t+1)} = rac{1.0 + \sum_{i=1}^P g_i \gamma_{i,k}}{2.0 + \sum_{i=1}^P g_i}, \quad u_k^{(t+1)} = rac{1.0 + \sum_{i=1}^P (1 - g_i) \gamma_{i,k}}{2.0 + \sum_{i=1}^P (1 - g_i)}$$

### 3.2 Josang Subjective Logic & W3C PROV-DM (`backend/core/provenance_fusion.py`)
- Every observation carries an opinion $\omega_X^A = (b_X, d_X, u_X, a_X)$ where $b_X + d_X + u_X = 1$.
- Independent sources are fused via the **Cumulative Fusion Operator ($\oplus$)**:
  $$b_{X}^{A \diamond B} = rac{b_X^A u_X^B + b_X^B u_X^A}{u_X^A + u_X^B - u_X^A u_X^B}, \quad u_{X}^{A \diamond B} = rac{u_X^A u_X^B}{u_X^A + u_X^B - u_X^A u_X^B}$$
- Dependent/mirrored feeds (sharing an upstream origin URL) are fused via the **Averaging Fusion Operator ($	ilde{\oplus}$)** to prevent circular reporting amplification.

### 3.3 Grounded GraphRAG Assistant & Sweep-Delta Briefing Generator (`backend/ai/assistant.py`)
- **Strict Citation Enforcement Fix:** Update `validate_citations()` so that **100% (`valid_ratio == 1.0`)** of sentences containing factual claims must carry a valid `[PROV:prov_...]` or `[DELTA:delta_...]` citation ID from the local SQLite database. Any uncited LLM sentence is stripped before returning to the UI.
- **Automated Sweep-Delta Executive Briefing (`GET /api/v1/sweeps/latest/briefing`):** Synthesizes the latest sweep's top deltas, sanctions matches, geofence breaches, and spatial clusters into a structured, fully cited 5-bullet intelligence SitRep (works deterministically offline via template synthesis, and optionally enhances prose via local Ollama `qwen2.5:7b` when running).
