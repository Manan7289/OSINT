# UI_UX_SPECIFICATION.md — Analyst Workstation Design System & Interaction Specification

## 1. Visual Design Philosophy
The **LocalOSINT v2.0 Workstation** is designed for long-duration cyber and corporate intelligence analysis sessions on Windows 11 displays (1920×1080 and 2560×1440). It avoids bright consumer whitespace and cartoon widgets in favor of a high-contrast, dark slate palette (`#090d16` canvas, `#111827` panels, `#1e293b` cards) with semantic color-coding for **Epistemic Status** and **FollowTheMoney Entity Schemas**.

---

## 2. Typography, Color Palette & Epistemic Badge System

### 2.1 Color Tokens (`frontend/assets/styles.css`)
- **Surfaces:** `--bg-base: #090d16`, `--bg-panel: #111827`, `--bg-card: #1e293b`, `--border-subtle: #334155`.
- **Epistemic Status Badges & Graph Edge Styles:**
  - `OBSERVED_FACT`: Solid Emerald (`#10b981`)
  - `CORROBORATED_FACT`: Double-Line Cyan (`#06b6d4`)
  - `DERIVED_INFERENCE`: Dashed Purple (`#8b5cf6`)
  - `ANALYST_HYPOTHESIS`: Dotted Amber (`#f59e0b`)
  - `UNVERIFIED_CLAIM` / Conflict ($d \ge 0.25$): Rose Warning (`#f43f5e`)

### 2.2 Global Top Command Bar (Persistent Across All 11 Views)
- **Active Workspace Selector:** Dropdown showing workspace name, TLP badge (`TLP:CLEAR` to `TLP:RED`), and `PASSIVE_ONLY` OPSEC indicator.
- **Global Hybrid RRF Search Bar:** Instant search input triggering `GET /api/workspaces/{id}/search?mode=hybrid_rrf`.
- **One-Click Exports:** `JSON`, `CSV`, `STIX 2.1`, `FtM JSONL`, `W3C PROV`.
