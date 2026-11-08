# M10 — 5-Zone 2D/3D Global Command Centre UI & 4D Time Scrubber

- **Target Files:** `frontend/index.html`, `frontend/assets/styles.css`, `frontend/assets/app.js`, `frontend/assets/globe_map.js`, `frontend/assets/timeline_4d.js`, `frontend/assets/sweep_delta_hud.js`, `frontend/assets/visual_studio.js`
- **Action:** Implement the 5-Zone Command Centre layout specified in `UI_UX/UI_UX_IMPLEMENTATION_SPECIFICATION.md`:
  - Synchronized 2D (`MapLibre GL JS`) and 3D (`Globe.gl` / `CesiumJS`) Earth canvas.
  - Layer Manager with live counts and honest telemetry badges (`LIVE`, `DELAYED`, `SGP4`, `HISTORICAL`, `OFFLINE_BOOTSTRAP`).
  - Crucix Sweep-Delta ticker & Global Escalation Score gauge.
  - 4D Time Scrubber with `1x`/`10x`/`60x` playback speed and historical SQLite track replay.
  - Interactive Geofence polygon drawing tool and PiP Camera / Visual Studio modal.
