# FINAL_PROJECT_SPECIFICATION.md — Functional Scope, Use Cases & Non-Functional Requirements

## 1. Project Objective & Core Problem Solved
Analysts conducting defensive cybersecurity investigations, corporate due diligence, supply-chain risk assessments, and journalistic verification face a stark divide:
- **Point CLI tools** ([theHarvester](https://github.com/laramies/theharvester), [Sherlock](https://github.com/sherlock-project/sherlock), [Recon-ng](https://github.com/lanmaster53/recon-ng)) produce disconnected flat files with no entity resolution, no bitemporal history, and no protection against circular reporting.
- **Heavyweight enterprise platforms** ([OpenCTI](https://github.com/opencti-platform/opencti), [Maltego Enterprise](https://www.maltego.com/transform-hub/), [Recorded Future](https://www.recordedfuture.com/platform)) require multi-container cloud infrastructure or five-to-six-figure annual subscriptions.

**LocalOSINT v2.0** bridges this gap by delivering a **self-contained, local-first intelligence analysis workstation** that runs natively on a single Windows 11 PC (~16 GB RAM, CPU-only) with court-defensible cryptographic provenance (`W3C PROV` + `SHA-256`), unsupervised probabilistic entity resolution ([Fellegi-Sunter EM](https://moj-analytical-services.github.io/splink/index.html)), mathematical source-independence fusion ([Subjective Logic](https://www.mn.uio.no/ifi/english/people/aca/josang/publications/jwz2017-fusion.pdf)), and interactive WebGL link analysis.

---

## 2. Target Users & Primary Investigation Use Cases
1. **Defensive SOC & Threat Intelligence Analysts:** Triaging suspicious domains, IPv4/IPv6 hosts, ASNs, TLS certificates, and prioritizing vulnerabilities using combined **NIST NVD CVSS + FIRST.org EPSS + CISA KEV** status.
2. **Corporate Due Diligence & Financial Crime Investigators:** Mapping corporate parent/subsidiary ownership hierarchies via **GLEIF Global LEI (Level 1 & Level 2)**, **SEC EDGAR**, and **OpenAlex**, and screening entities against **OpenSanctions (`yente` / FollowTheMoney)** watchlists.
3. **Investigative Journalists & Researchers:** Extracting metadata (`Author`, `Producer`, `EXIF`, embedded IOCs) from public PDF/DOCX/Image documents, tracking historical website modifications via the **Wayback Machine CDX API**, and monitoring global multilingual media spikes via **GDELT DOC 2.0**.

---

## 3. Functional Scope Breakdown

### 3.1 Essential Core Features (Must Operate 100% Locally / Keyless)
1. **Multi-Workspace Case Management:** Isolated workspaces with Traffic Light Protocol (`TLP:CLEAR`, `TLP:GREEN`, `TLP:AMBER`, `TLP:RED`) markings, custom scope domain definitions, and `PASSIVE_ONLY` OPSEC mode.
2. **24 Modular OSINT Connectors (18 Keyless Public + 6 Optional Keyed):**
   - *Keyless Public (18):* Cloudflare DoH (`dns_doh`), IANA RDAP (`rdap_bootstrap`), crt.sh CT (`crtsh_ct`), RIPEstat BGP/ASN (`ripestat_data`), URLScan Public (`urlscan_public`), Shodan InternetDB (`shodan_internetdb`), NIST NVD CVE v2 (`nvd_cve_v2`), CISA KEV (`cisa_kev`), FIRST EPSS (`first_epss`), Abuse.ch ThreatFox (`abusech_threatfox`), Abuse.ch URLhaus (`abusech_urlhaus`), Abuse.ch MalwareBazaar (`abusech_bazaar`), GLEIF LEI & Ownership (`gleif_lei`), SEC EDGAR (`sec_edgar`), OpenSanctions (`opensanctions`), Wikidata SPARQL (`wikidata_sparql`), OpenAlex (`openalex_orgs`), Wayback CDX (`wayback_cdx`), GDELT 2.0 (`gdelt_doc_v2`), GitHub Public REST (`github_rest`), OpenStreetMap Nominatim (`nominatim_osm`), and Local Document/HTML/PDF/EXIF Forensics (`local_doc_forensics`).
   - *Optional BYO-Key (6):* Shodan Pro, VirusTotal v3, GreyNoise Community, SecurityTrails Passive DNS, Censys Search v2, AlienVault OTX.
3. **Staging & Confidence Triage Buffer:** Automatically intercepts high-volume collector bursts ($>50$ entities) into `is_staged = 1` for analyst filtering before graph promotion.
4. **Unsupervised Fellegi-Sunter EM Entity Resolution & Reversible Merge:** 3-pass blocking, EM weight estimation, Bayes-factor waterfall charts, and one-click Merge/Unmerge.
5. **W3C PROV Lineage & Subjective Logic Belief Fusion:** Tracks `upstream_lineage_family`, discounts copied claims, computes $\omega=(b,d,u,a)$, and enforces 5-state epistemic stratification.
6. **Graph, Spatiotemporal & Anomaly Analytics:** Leiden communities, RIOT-Lite super-node dampening, IEF-Personalized PageRank, Adamic-Adar link prediction, Haversine HDBSCAN spatial clusters, Kleinberg burst detection, DGA entropy, and Isolation Forest anomalies.
7. **Hybrid RRF Search & GraphRAG Assistant:** SQLite FTS5 `bm25()` + INT8 384-d vectors fused via RRF ($k=60$), plus deterministic GraphRAG report synthesis with optional local Ollama LLM and `[ev_id]` citation verification.
8. **Multi-Format Export:** `JSON` (full workspace + W3C PROV bundle), `CSV`, `STIX 2.1` JSON bundle, `FollowTheMoney (FtM)` JSONL, and `Markdown` intelligence reports.

### 3.2 Explicitly Excluded Features (Hard Ethical & Legal Guardrails)
- **Excluded:** Active exploit payloads, brute-force password cracking, unauthorized active port scanning, CAPTCHA/authentication bypass, session-cookie theft, commercial mobile ad-bidstream tracking, and hosting/querying stolen plaintext credential dumps.

---

## 4. Non-Functional Requirements (Windows 11 Target)
- **Memory Envelope:** $< 350	ext{ MB}$ RAM in Core Mode; $< 750	ext{ MB}$ RAM with INT8 ONNX NLP models loaded; $< 5.5	ext{ GB}$ RAM if optional 7B/8B Q4 Ollama LLM is active.
- **Cold Startup Time:** $< 2.0	ext{ seconds}$ to interactive UI at `http://127.0.0.1:8000`.
- **Search & Graph Latency:** $< 25	ext{ ms}$ for hybrid RRF search over 10,000 records; $< 100	ext{ ms}$ for Leiden + IEF-PageRank on 5,000 nodes; 60 FPS WebGL graph panning/zooming.
- **Reliability & Offline Resilience:** Zero unhandled exceptions when internet connectivity is absent (`offline_mode = true`) or when upstream public APIs return HTTP `429/502/503` (handled by 3-state circuit breakers and SQLite HTTP cache).
