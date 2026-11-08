# SCREEN_BY_SCREEN_REQUIREMENTS.md — Detailed Requirements for All 11 Workstation Screens

## Screen 1: Command Dashboard (`view-dashboard`)
- **KPI Strip:** Total Entities, Active Claims/Relationships, Staged Entities (`is_staged=1`), Provenance Artifacts (`W3C PROV`), and Contradiction Alerts ($d \ge 0.25$).
- **Workspace Creation Form:** Name, Description, TLP Marking (`TLP:CLEAR`, `TLP:GREEN`, `TLP:AMBER`, `TLP:RED`), OPSEC Mode (`STANDARD` vs. `PASSIVE_ONLY`), Max Pivot Depth (`1..3`).
- **Split Tables:** Top IEF-PageRank Centrality Hubs (left) and Latest W3C PROV Evidence Captures with Admiralty grades (right).

## Screen 2: OSINT Playbook Launcher, Staging Triage & Document Forensics (`view-collect`)
- **Playbook Launcher:** Target input, Type selector (`AUTO`, `Domain`, `IPv4Address`, `AutonomousSystem`, `Company`, `Vulnerability`, `URL`, `Email`), Pivot Depth (`0..2`), and 24-connector grid showing live Circuit Breaker status (`READY`, `CIRCUIT_OPEN`, `API_KEY_REQUIRED`).
- **Staging & Confidence Triage Panel:** Lists entities currently held in `is_staged = 1` with a **"Promote Selected / Promote All Above Risk Threshold"** button.
- **Document & Paste Forensics Panel:** Textarea for defanged threat advisories/headers + File Upload input for PDF/DOCX/Image EXIF forensics.

## Screen 3: Entity Explorer & Hybrid RRF Search (`view-entities`)
- **Search Mode Selector:** `Hybrid RRF (BM25 + INT8 Vec)`, `Exact BM25`, or `Semantic Vector`.
- **Entity Table:** Displays `ftm_schema`, `display_label`, `admiralty_code`, Subjective Logic belief/uncertainty bar (`b / d / u`), `risk_score` with expandable triggered risk rules, `leiden_community_id`, and `independent_source_count`.

## Screen 4: Dual-Engine Relationship Graph & Bitemporal Time-Travel (`view-graph`)
- **Graph Toolbar:**
  - Engine Toggle (`Canvas/WebGL Fast Render` vs. `SVG Tactical Graph`)
  - **Bitemporal Time-Travel Filter (`As-Of Date` input)** filtering claims by `valid_from <= T <= valid_until`
  - **"Dampen / Hide Shared CDN & Resolver Super-Nodes (`is_shared_infra`)"** checkbox
  - Zoom `+`/`-` and `Reset ForceAtlas2 Layout` buttons
- **Right Inspector Pane:** Displays clicked node's Subjective Logic tuple $\omega=(b,d,u,a)$, Leiden community, IEF-PageRank, Adamic-Adar predicted missing links, and a **"Pivot OSINT Playbook on Node"** button.

## Screen 5: Fellegi-Sunter EM Entity Resolution & Waterfall Workbench (`view-resolution`)
- **Candidate Pairs Table:** Shows `Entity A`, `Entity B`, `FS Log2 Weight`, `Match Probability`, and **Bayes-Factor Waterfall Bars** (`+4.1 name_jw`, `+1.4 shared_asn`, `-0.8 country_mismatch`).
- **Actions:** `Merge Duplicate` button + **Reversible Merge History Table** with one-click `Unmerge / Revert` button.

## Screen 6: Bitemporal Timeline & Kleinberg Burst Analyzer (`view-timeline`)
- **Burst Alert Banner:** Highlights time windows where Poisson/Kleinberg Z-score $\ge 2.5$ (e.g., sudden spike in certificate issuance or news volume).
- **Chronological Event Stream:** Color-coded by severity and linked to source URLs.

## Screen 7: Geospatial Intelligence & Haversine HDBSCAN Map (`view-geospatial`)
- **World Graticule Map:** Plots entity coordinates and overlays **Haversine HDBSCAN spatial cluster circles** (`Cluster #1: 4 assets within 12 km`).
- **Coordinate & Geohash Table:** Lists `display_label`, `location_label`, `latitude`, `longitude`, `geohash_8`, and `hdbscan_cluster_id`.

## Screen 8: W3C PROV Lineage & Subjective Logic Ledger (`view-provenance`)
- **Provenance Table:** Displays `observed_at`, `admiralty_rating`, `upstream_lineage_family`, `independence_weight` (showing Dong copying discounts), `title`/`summary`, and 64-char `payload_sha256`.

## Screen 9: GraphRAG AI Assistant & Epistemically Stratified Reports (`view-ai-reports`)
- **GraphRAG Query Panel:** Natural-language input returning structured sections (`1. Observed & Corroborated Facts [ev_xxx]`, `2. Graph-Derived Inferences`, `3. Contradictions & Gaps`, `4. Citation Audit Status`).
- **Formal Report Builder:** Generates and previews saved Markdown reports.

## Screen 10: Task, Rate-Limiter & Circuit-Breaker Monitor (`view-tasks`)
- Displays historical and running collection tasks with `pivot_depth`, `entities_found`, `staged_count`, and error diagnostics.

## Screen 11: Fernet API Key Vault, OPSEC & Audit Chain Verification (`view-settings`)
- **OPSEC & Runtime Settings:** Toggle `PASSIVE_ONLY` mode, `offline_mode`, and local Ollama URL/model.
- **Audit Log Integrity Banner:** Displays `Audit Hash-Chain Verified (N entries, 0 tampering detected)`.
- **24-Connector API Vault Table:** Masked keys + encrypted key save inputs.
