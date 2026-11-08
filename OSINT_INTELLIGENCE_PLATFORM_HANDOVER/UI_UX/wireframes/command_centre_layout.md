# 10 — UI/UX IMPLEMENTATION SPECIFICATION (`M10`)

**Target Repository:** [`https://github.com/Manan7289/OSINT.git`](https://github.com/Manan7289/OSINT.git)  
**Target Files:** `frontend/index.html`, `frontend/assets/styles.css`, `frontend/assets/app.js`, `frontend/assets/globe_map.js`, `frontend/assets/timeline_4d.js`, `frontend/assets/sweep_delta_hud.js`, `frontend/assets/visual_studio.js`

---

## 1. Visual Design Language: Tactical Global Command Centre

The redesigned UI abandons the traditional multi-page CRUD dashboard in favor of a **Full-Viewport (`100vw x 100vh`) Geospatial HUD Command Centre** combining:
- **God's Eye View (`godseyeview.ai`):** Seamless 2D/3D globe toggle, smooth fly-to camera presets, orbital satellite paths, and floating glassmorphic HUD panels.
- **Argos Atlas (`argosatlas.com`):** Real-time military/commercial aircraft, maritime vessels, sanctions warning badges (`OFAC FLAGGED`), public camera picture-in-picture viewer, and event-to-asset proximity rings.
- **Crucix (`crucix.live`):** Live 15-minute Sweep-Delta ticker, Global Escalation Score gauge, and 1-click AI Intelligence Briefing drawer.

### Color Palette & Typography (`frontend/assets/styles.css`)
- **Canvas Background:** Deep Orbital Obsidian `#060911`
- **HUD Panel Surface:** Glassmorphic Slate `rgba(13, 19, 33, 0.84)` with `backdrop-filter: blur(14px)` and `1px solid rgba(56, 189, 248, 0.22)` border
- **Primary Accent (Cyan Telemetry):** `#38BDF8`
- **Layer Semantic Colors:**
  - Commercial Aviation: `#38BDF8` (Sky Cyan)
  - Military Aviation: `#F59E0B` (Tactical Amber)
  - Maritime Vessels: `#10B981` (Emerald)
  - **Sanctioned Asset (`OFAC SDN`) / Emergency Squawk**: `#EF4444` (Crimson Pulse with animated halo)
  - Orbital Satellites & Ground Tracks: `#A855F7` (Orbital Violet)
  - Earthquakes / Wildfires / Severe Weather: `#F97316` (Hazard Orange)
  - Cyber Threats (`CISA KEV` / `URLHaus`): `#EC4899` (Cyber Magenta)
  - Public Cameras: `#22D3EE` (Teal Camera Pin)
- **Typography:** `Inter` / `Segoe UI` for UI labels; `JetBrains Mono` / `Cascadia Code` for coordinates, MMSI/ICAO24 hex codes, TLE elements, and Subjective Logic `(b, d, u)` tuples.

---

## 2. 5-Zone Command Centre Layout Wireframe

```text
+------------------------------------------------------------------------------------------------------------------+
| [LOCALOSINT v3.0] | [2D Map | 3D Globe] | Region: [Global|Hormuz|Taiwan|RedSea|Europe] | Tension: 42/100 [SWEEP] |
| Search: [ Hybrid RRF Search / Coordinates / MMSI / ICAO24 / CVE ... (Ctrl+K) ]   | [Visual Studio] [Briefing]    |
+--------------------------+------------------------------------------------------------+--------------------------+
| ZONE 2: LAYER & SWEEP    |                                                            | ZONE 4: ENTITY, GRAPH    |
| MANAGER (Left HUD 300px) |             ZONE 1: INTERACTIVE 2D / 3D EARTH              | & PROVENANCE INSPECTOR   |
|                          |             (MapLibre GL JS + CesiumJS / Globe.gl)         | (Right HUD 380px)        |
| [x] Aviation (1,420) LIVE|                                                            |                          |
|  [x] Military Only (118) |                   *  [SAT: USA-326 (NRO)]                  | Selected: M/V BEHSHAD    |
|  [x] OFAC Sanctioned (4) |                      /                                     | Badge: [LIVE] [SANCTION] |
| [x] Maritime (890) LIVE  |        +------------+                                      | MMSI: 422039000 (Iran)   |
|  [x] Dark-Ship Alerts (2)|        |  [AIR: RCH412 (USAF C-17)]                        | OFAC: IRAN-EO13846       |
| [x] Satellites (540) SGP4|        |                                                   | Speed: 11.4 kn | HDG 142 |
| [x] Quakes & Fires (64)  |   (( [VESSEL: M/V BEHSHAD - OFAC FLAGGED] ))               |                          |
| [x] Weather Alerts (19)  |         \--- 18.4 km ---> [CAM: Port CCTV #04]             | [Subjective Logic Opinion|
| [x] Conflict & Cyber(112)|                                                            |  b:0.89 | d:0.02 | u:0.09|
| [x] Public Cameras (310) |   +----------------------------------------------------+   |  Admiralty: A1]          |
|                          |   | PIP CAMERA / VISUAL STUDIO OVERLAY (Draggable)     |   |                          |
| --- SWEEP DELTAS (15m)---|   | [Camera Feed / Uploaded Photo w/ Bystander Blur]   |   | --- EGO GRAPH (Cytoscape)|
| ! [CRIT] Vessel entered  |   | Quality: HIGH (Laplacian 164.2) | pHash: 8f3a9c01  |   | (Interactive 2-Hop Node  |
|   Strait of Hormuz Zone  |   +----------------------------------------------------+   |  Neighborhood & Fellegi- |
| ^ [HIGH] M5.8 Earthquake |                                                            |  Sunter Merge Audit)     |
| + [NEW] 14 CISA KEV CVEs |                                                            |                          |
+--------------------------+------------------------------------------------------------+--------------------------+
| ZONE 5: 4D SPATIOTEMPORAL TIME SCRUBBER & TELEMETRY STATUS BAR (Bottom Dock 68px)                                |
| [|<] [Play/Pause] [1x|10x|60x] |=====[2025-05-12 14:30 UTC]=====*--------------------| [Draw Geofence] [Export]  |
+------------------------------------------------------------------------------------------------------------------+
```

---

## 3. Detailed Zone Specifications

### 3.1 Zone 1: Dual 2D/3D Geospatial Canvas (`frontend/assets/globe_map.js`)
- **2D Tactical Map (`MapLibre GL JS`):**
  - Uses keyless Esri World Imagery (`https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}`) + Carto Dark Matter / OpenStreetMap vector labels out of the box.
  - Renders WebGL GeoJSON layers for aircraft (rotated directional aircraft icons), vessels (directional ship chevrons), earthquakes (magnitude-scaled pulsing circles), weather polygons, geofences, and GPS interference hex grids.
- **3D Orbital Globe (`Globe.gl` / `CesiumJS`):**
  - 1-click toggle synchronizes camera `(lat, lon, altitude, heading, pitch)` between 2D and 3D views.
  - Renders 3D altitude-elevated satellite points propagated every 1,000ms in browser via `satellite.js` / backend `/api/v1/geospatial/satellites`, orbital trajectory arcs, and 3D flight paths.
- **Region Presets Bar:** Instant camera fly-to presets for **Global Overview**, **Strait of Hormuz / Middle East**, **Red Sea / Bab el-Mandeb**, **Taiwan Strait / Indo-Pacific**, **Eastern Europe / Black Sea**, **North America**, and **India / Indian Ocean**.

### 3.2 Zone 2: Layer Manager & Sweep-Delta HUD (`frontend/assets/sweep_delta_hud.js`)
- **Layer Toggles with Live Telemetry Pills:** Each layer displays its item count and honest telemetry badge (`LIVE`, `DELAYED`, `SGP4`, `BOOTSTRAP`).
- **Crucix Sweep-Delta Stream:** Displays real-time delta cards (`NEW_ENTITY`, `SANCTION_MATCH_DETECTED`, `ESCALATED_RISK`, `ENTERED_GEOFENCE`, `AIS_DARK_GAP`). Clicking any delta card flies the globe directly to the asset/event and opens Zone 4.
- **Interactive Geofence Drawing:** Clicking `[Draw Geofence]` lets the analyst click polygon vertices on the map, name the watch zone, choose notification channels (`SSE`, `Telegram`, `Discord`), and save to `/api/v1/geofences`.

### 3.3 Zone 3: Privacy-Preserving Visual Intelligence Studio Modal/Drawer (`frontend/assets/visual_studio.js`)
- **Drag-and-Drop Image Dropzone:** Accepts local image files or 1-click snapshot capture from a selected public camera pin.
- **Forensic & Quality Scorecard:** Displays image dimensions, SHA-256, 64-bit `pHash`/`dHash`/`aHash`, Laplacian sharpness variance $\sigma_L^2$, quality badge (`HIGH_SHARPNESS` / `MODERATE` / `POOR_BLURRY`), and EXIF/GPS/C2PA table (with a `[Fly to EXIF GPS]` button if GPS tags exist).
- **Mandatory Bystander Redaction Preview:** Displays the image with all detected faces automatically blurred (`blur_bystanders = true` toggle on by default) alongside bounding-box quality metrics.
- **Consent-Gated Verification Panel:** Locked behind an explicit checkbox (`"I attest that I have documented legal consent/authorization to verify this image against the enrolled local reference gallery"`) and purpose input before calling `/api/v1/visual/verify`.

### 3.4 Zone 4: Entity, Graph & W3C Provenance Inspector
- Displays full entity details, OFAC sanctions match specifics, embedded **Cytoscape.js 2-hop Ego-Graph**, Josang Subjective Logic `(b, d, u, a)` bars, NATO Admiralty source reliability badges, Fellegi-Sunter merge history (with 1-click Undo), and the **Grounded GraphRAG Briefing Assistant**.

### 3.5 Zone 5: 4D Spatiotemporal Time Scrubber (`frontend/assets/timeline_4d.js`)
- Scrubbing backward transitions the canvas badge to `HISTORICAL` and queries `/api/v1/geospatial/replay?timestamp=...&window_minutes=30` while propagating satellites via `SGP4` to that exact historical UTC timestamp.
