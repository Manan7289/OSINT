# START_HERE.md — Master Entry Point for the Next-Generation OSINT Intelligence Platform

## 1. Welcome & Architectural Paradigm Shift
This handover folder (`OSINT_INTELLIGENCE_PLATFORM_HANDOVER/`) contains the complete research, competitive teardown, unified product architecture, database schema, module specifications, visual intelligence pipelines, and phased implementation roadmap for **LocalOSINT v3.0 (Codename: ARGON-OMEGA)**.

### Why We Redesigned the Platform
An ordinary OSINT dashboard with a text search bar, static tables, and a few DNS/WHOIS lookups is no longer sufficient. **LocalOSINT v3.0** unifies four pillars into a single local-first Global Intelligence Command Centre inside [`https://github.com/Manan7289/OSINT.git`](https://github.com/Manan7289/OSINT.git):
1. **[Argos Atlas](https://www.argos.foundation/) Operational Picture:** Live multi-layer geospatial fusion of global conflict/crisis events, aircraft (`OpenSky` / `adsb.lol`), maritime vessels (`AISStream` / `Digitraffic`) cross-referenced against **OFAC/OpenSanctions sanctioned vessel & aircraft registries**, GPS-jamming zones, critical infrastructure, and 200,000+ documented public DOT/municipal traffic & weather cameras.
2. **[Crucix (`calesthio/Crucix`)](https://github.com/calesthio/Crucix) Autonomous Sweep-Delta & Alerting Engine:** Scheduled background collection sweeps across 28+ public telemetry and OSINT feeds, computing a mathematical **Sweep Delta** (what newly appeared, escalated, moved into a geofence, or de-escalated since the previous sweep), streaming live updates via WebSockets/SSE, and dispatching multi-tier alerts to **Telegram, Discord, Email, and Desktop Notifications**.
3. **[God's Eye View (`bilawalsidhu/gods-eye-view`)](https://github.com/bilawalsidhu/gods-eye-view) Unified 2D/3D Globe & Time-Machine:** Seamless toggle between a keyless **3D Globe (`CesiumJS` / `Globe.gl` with Esri World Imagery + OSM fallback + optional Cesium ion / Google Photorealistic 3D Tiles)** and a high-speed **2D Tactical Map (`MapLibre GL JS`)**, featuring real-time `SGP4` satellite orbital propagation (`CelesTrak`), USGS earthquakes, NASA FIRMS/EONET wildfires, NOAA weather alerts, and a **4D Historical Playback Scrubber**.
4. **Privacy-Preserving Visual Intelligence & Deep Graph/Provenance Analytics:** Dedicated Computer Vision workspace (`OpenCV YuNet` ONNX face detection, automatic bystander face blurring/redaction, Laplacian/Brenner image quality scoring, 64-bit `pHash`/`dHash` duplicate detection, EXIF/C2PA forensics, and strictly consent-gated enrolled-gallery verification via `SFace`/`ArcFace` ONNX) fused with the existing **SQLite WAL + FTS5 + R*Tree + Fellegi-Sunter EM + W3C PROV + Jøsang Subjective Logic** engine already built in `https://github.com/Manan7289/OSINT.git`.

---

## 2. Mandatory Reading Order for Implementation
Read the documents in `OSINT_INTELLIGENCE_PLATFORM_HANDOVER/` in this exact sequence before modifying any code in `https://github.com/Manan7289/OSINT.git`:

1. **`START_HERE.md`** *(This orientation guide)*
2. **`RESEARCH/REFERENCE_PLATFORM_RESEARCH.md`** *(Deep technical teardown of Argos Atlas, Crucix, God's Eye View, and existing repo audit)*
3. **`RESEARCH/COMPETITIVE_FEATURE_COMPARISON.md`** *(Feature matrix, gap analysis, and license compliance rules)*
4. **`RESEARCH/TECHNOLOGY_AND_ALGORITHM_RESEARCH.md`** *(Geospatial 2D/3D engines, SGP4, AIS/ADS-B, YuNet/SFace ONNX, pHash, Sweep-Delta math)*
5. **`IMPLEMENTATION/FINAL_PRODUCT_VISION.md`** *(Unified product workflows, honest data-freshness badges, and scope guardrails)*
6. **`ARCHITECTURE/SYSTEM_ARCHITECTURE.md`** *(End-to-end architecture, existing repo retention vs. redesign map, and Mermaid diagrams)*
7. **`ARCHITECTURE/DATABASE_AND_DATA_MODEL.md`** *(Extended SQLite WAL + R*Tree + Spatiotemporal Track + Visual Evidence + Sweep-Delta DDL)*
8. **`ARCHITECTURE/DATA_SOURCE_AND_INTEGRATION_PLAN.md`** *(28 verified live geospatial, orbital, aviation, maritime, environmental, camera, and OSINT feeds)*
9. **`AI_AND_ALGORITHMS/VISUAL_INTELLIGENCE_SPECIFICATION.md`** *(Consent-gated facial analysis, bystander blurring, quality scoring, pHash, EXIF)*
10. **`AI_AND_ALGORITHMS/AI_AND_CORRELATION_ENGINE_SPECIFICATION.md`** *(Spatiotemporal cross-source correlation, Sweep-Delta engine, GraphRAG regional briefings, Telegram/Discord alerts)*
11. **`UI_UX/UI_UX_IMPLEMENTATION_SPECIFICATION.md`** *(Command Centre layout, 2D/3D globe switcher, layer manager, time scrubber, visual workspace)*
12. **`MODULE_SPECIFICATIONS/` (`M01` through `M12`)** *(Read each module spec before coding that module)*
13. **`IMPLEMENTATION/IMPLEMENTATION_ROADMAP.md`** *(Phased build plan preserving working code in `Manan7289/OSINT.git`)*
14. **`TESTING/TESTING_AND_ACCEPTANCE_CRITERIA.md`** *(Verification tests required for every phase)*
15. **`OTHER_SUPPORTING_DOCUMENTATION/`** (`SECURITY_AND_PRIVACY_ARCHITECTURE.md`, `LOCAL_SETUP_AND_DEPLOYMENT.md`, `FINAL_CHANGELOG.md`)
