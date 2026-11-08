# LocalOSINT v2.0 — Open-Source Intelligence & Link Analysis Workstation

LocalOSINT v2.0 is a self-contained, local-first intelligence analysis platform designed to run natively on a single Windows 11 machine (~16 GB RAM, CPU-only). It provides court-defensible cryptographic provenance (W3C PROV + SHA-256), unsupervised probabilistic entity resolution (Fellegi-Sunter EM), mathematical source-independence belief fusion (Jøsang Subjective Logic), bitemporal claim versioning, and interactive graph and geospatial analysis.

## Key Capabilities
- **Bitemporal Knowledge Graph:** FollowTheMoney-aligned entities with reified `claims` tracking both occurrence time (`valid_from`, `valid_until`) and observation time (`observed_at`), with 5-state epistemic stratification.
- **W3C PROV Lineage & Subjective Logic:** Prevents circular reporting and syndicated echo chambers from inflating confidence using Dong copying discounts and Jøsang Cumulative ($\oplus$) vs. Averaging ($\tilde{\oplus}$) belief fusion.
- **3-Pass Blocked Fellegi-Sunter Entity Resolution:** Sorted Neighborhood ($w=15$) + Identifier Prefix + 3-Gram MinHash LSH blocking with unsupervised EM parameter estimation, Bayes-factor waterfall charts, and 100% reversible unmerge.
- **Modular Intelligence Collectors:** 24 OSINT connectors (18 keyless public + 6 optional BYO-key) with per-source Token Bucket rate limiting, Circuit Breaker fault isolation, and Staging Triage buffering ($>50$ child nodes).
- **Hybrid Search & GraphRAG:** SQLite FTS5 `bm25()` combined with 384-d INT8 vectors via Reciprocal Rank Fusion ($k=60$) and deterministic graph synthesis with citation verification.
- **Dual-Engine Analyst Workstation UI:** WebGL and Canvas graph rendering, bitemporal time-travel slider, waterfall ER workbench, and multi-format export (JSON, CSV, STIX 2.1, FollowTheMoney JSONL, W3C PROV).

## Quick Start (Windows 11)
```cmd
# 1. Clone repository
git clone https://github.com/Manan7289/OSINT.git
cd OSINT

# 2. Run automated installer
install.bat

# 3. Start LocalOSINT Workstation
start.bat
```
Navigate to `http://127.0.0.1:8000` in any modern web browser.
