# M10 — 11-View Dual-Engine WebGL/Canvas Analyst Workstation Frontend

## 1. Module Name & Identifier
- **Module Title:** M10 — 11-View Dual-Engine WebGL/Canvas Analyst Workstation Frontend
- **Target File Path(s):** `frontend/index.html, frontend/assets/styles.css, frontend/assets/app.js`

## 2. Purpose
Provides a high-density, dark-mode intelligence analysis workstation UI supporting 11 integrated views, dual-mode HTML5 Canvas/WebGL + SVG graph rendering, bitemporal time-travel filtering, Staging Triage promotion, and Fellegi-Sunter waterfall adjudication.

## 3. User-Facing Functionality
The complete interactive browser workstation at `http://127.0.0.1:8000`.

## 4. Internal Responsibilities
Manages client-side reactive state, renders high-speed HTML5 Canvas/WebGL + SVG graphs with ForceAtlas2/spring layout relaxation, renders the Bitemporal Time-Travel filter bar, renders Bayes-factor waterfall charts in the Entity Resolution view, renders HDBSCAN spatial cluster overlays on the equirectangular world map, and manages the Fernet API Key Vault.

## 5. Inputs
User interactions and JSON payloads from `/api/*`.

## 6. Outputs
DOM/Canvas/SVG visual rendering and REST API mutations.

## 7. Required Algorithms & Mathematical Formulations
Client-side ForceAtlas2 / Fruchterman-Reingold layout relaxation with degree-based level-of-detail (LOD) label culling for 60 FPS rendering.

## 8. Dependencies
Zero external CDN dependencies required at runtime (100% self-contained local CSS/JS bundle so it works in air-gapped environments).

## 9. Backend Integration
Communicates with `M09` (`backend/main.py`).

## 10. Frontend Integration
Self-contained SPA.

## 11. Data Storage Requirements
Uses `localStorage` only for non-sensitive UI layout preferences (zoom level, active tab).

## 12. Error-Handling Requirements
Displays non-blocking toast notifications (`showToast`) on network or validation errors.

## 13. Security, OPSEC & Privacy Requirements
Escapes all dynamic strings via `escapeHtml()` before DOM insertion to prevent Stored/Reflected XSS from malicious WHOIS/HTML records.

## 14. Testing Requirements
Verified via E2E UI smoke tests in `test_m09_api_and_exports.py`.

## 15. Dependencies on Other Modules
Depends on `M09`.

## 16. Completion & Acceptance Criteria
All 11 views render cleanly with zero console errors.
