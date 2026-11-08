# FEATURE_PRIORITIZATION.md — Meaningful OSINT Platform Innovations & Value-vs-Complexity Matrix

## 1. Executive Summary
To ensure **LocalOSINT v2.0** is a genuine leap beyond existing open-source tools ([SpiderFoot](https://github.com/smicallef/spiderfoot), [Recon-ng](https://github.com/lanmaster53/recon-ng), [theHarvester](https://github.com/laramies/theharvester)) rather than a superficial dashboard, we evaluate 12 core platform innovations. Each innovation is analyzed by the specific analytical failure mode it solves, existing approaches, our proposed algorithmic solution, technical feasibility on a 16 GB RAM Windows 11 PC, and strict MoSCoW prioritization (**P0 Core MVP**, **P1 Enhanced v2.0**, **P2 Advanced**).

---

## 2. Deep Analysis of 12 Platform Innovations

### Innovation 1: Source Independence & Circular-Reporting Mitigation Engine (P0 — Core MVP)
- **Problem Solved:** In standard OSINT tools, if 6 threat feeds or news articles repeat the same unverified claim originally posted on one blog, the system boosts confidence to 99%, fooling the analyst into believing 6 independent sources confirmed the fact.
- **Existing Approaches:** SpiderFoot and OpenCTI either take the max/average confidence or increment a raw hit counter without modeling upstream source lineage.
- **Our Proposed Approach:** Every connector tags its `upstream_lineage_family` (e.g., `ABUSECH_SWISS_CTI`, `ICANN_RIR_RDAP_REGISTRY`), extracts outbound hyperlink citations (`W3C PROV wasDerivedFrom`), and computes **Dong et al. ([VLDB 2009](http://www.vldb.org/pvldb/vol2/vldb09-335.pdf)) copying discounts + SimHash 64-bit textual overlap**. **Jøsang Subjective Logic ([UiO 2017](https://www.mn.uio.no/ifi/english/people/aca/josang/publications/jwz2017-fusion.pdf))** then applies **Cumulative Fusion ($\oplus$)** *only* across distinct lineage families and **Averaging Fusion ($\tilde{\oplus}$)** within the same lineage family.
- **Feasibility & Limitations:** $O(k^2)$ over the $k$ evidence items attached to a single claim (typically $k < 20$, running in $< 0.2\text{ ms}$). Cannot detect offline private communication between two journalists if neither cites the other and they completely rewrite the text.

### Innovation 2: Super-Node (CDN / Public Resolver) Dampening via Inverse Entity Frequency (IEF) (P0 — Core MVP)
- **Problem Solved:** Two unrelated domains hosted behind Cloudflare (`104.21.x.x` / `AS13335`), registered at `Namecheap`, or using `Let's Encrypt` appear tightly linked in naive graph tools, creating giant hairball components.
- **Existing Approaches:** Manual blocklists or deleting nodes from the canvas.
- **Our Proposed Approach:** Combine a built-in **RIOT-Lite Common Infrastructure Dataset** (`is_shared_infra = 1` for major CDNs, cloud ASNs, public DNS resolvers, and top CAs) with **IEF Edge Weighting** $w(u,v) = c(u,v) \cdot \log(1 + |V| / \text{deg}(v))$. Graph clustering (**Leiden algorithm**) and **Personalized PageRank** use $w(u,v)$, preventing super-nodes from bridging unrelated clusters while keeping the super-node visible in the entity inspector.

### Innovation 3: Unsupervised Fellegi-Sunter EM Entity Resolution with Waterfall Explanations & Reversible Merge (P0 — Core MVP)
- **Problem Solved:** Analysts need to know *why* two records matched and must be able to **undo** a merge weeks later if new evidence proves two similarly named companies are distinct.
- **Existing Approaches:** Irreversible SQL `UPDATE/DELETE` merges based on opaque fuzzy scores.
- **Our Proposed Approach:** Multi-pass Sorted Neighborhood ($w=15$) blocking + **Splink-style Fellegi-Sunter EM scoring** with per-field **Bayes Factor Waterfall Charts** (`+4.1 LEI match`, `+2.8 Jaro-Winkler name`, `-1.4 different country`) and a full JSON snapshot stored in `entity_merge_ledger` enabling one-click **Unmerge**.

### Innovation 4: Bitemporal Reified Claims & Epistemic Stratification (P0 — Core MVP)
- **Problem Solved:** Infrastructure and corporate ownership change over time (a domain resolved to IP `A` in 2023 during an attack, but resolves to benign parking IP `B` today). Overwriting attributes destroys historical truth.
- **Our Proposed Approach:** Every relationship and contested attribute is stored as a reified `claim` with `valid_from`, `valid_until`, `first_observed_at`, `last_observed_at`, and a strict `epistemic_status` (`OBSERVED_FACT`, `CORROBORATED_FACT`, `DERIVED_INFERENCE`, `ANALYST_HYPOTHESIS`, `UNVERIFIED_CLAIM`). Supports a **"Time-Travel Graph Slider"** to view the graph as of any historical date $T$.

### Innovation 5: CISA KEV + FIRST EPSS + NVD Composite Vulnerability Triage (P0 — Core MVP)
- **Problem Solved:** Thousands of CVEs have CVSS $\ge 7.0$, overwhelming defensive analysts.
- **Our Proposed Approach:** Automatically enriches discovered CVEs with **[FIRST.org EPSS](https://api.first.org/epss/)** exploitation probability (30-day forecast) and **[CISA KEV](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)** active exploitation status, prioritizing confirmed in-the-wild exploits at the top of the risk matrix.

### Innovation 6: GLEIF Level-2 Corporate Ownership Tree + OpenSanctions Screening (P1 — Enhanced Core)
- **Problem Solved:** Connecting technical domains/IPs to their ultimate parent corporation and checking whether directors or parent entities appear on international sanctions/PEP lists.
- **Our Proposed Approach:** Integrates the keyless **[GLEIF Global LEI API](https://api.gleif.org/)** (mapping direct and ultimate parent relationships) with **[OpenSanctions (`yente` / FtM)](https://www.opensanctions.org/docs/api/)**.

### Innovation 7: Staging & Confidence Triage Buffer for High-Volume Collectors (P1 — Enhanced Core)
- **Problem Solved:** Prevents a single `crt.sh` or `wayback_cdx` query from dumping 2,000 nodes onto the visual graph canvas.
- **Our Proposed Approach:** High-volume child observables land in `is_staged = 1` where they are indexed for search and anomaly scoring, allowing the analyst to promote only high-risk or corroborated nodes to the main graph.

### Innovation 8: Dual-Engine WebGL (Sigma.js) + Canvas (Cytoscape.js) Graph Workbench (P1 — Enhanced Core)
- **Problem Solved:** DOM SVG graphs freeze above ~500 nodes.
- **Our Proposed Approach:** **[Sigma.js](https://github.com/jacomyal/sigma.js/) WebGL** renders macro graphs up to 50,000 nodes at 60 FPS with ForceAtlas2 WebWorkers, while **[Cytoscape.js](https://github.com/cytoscape/cytoscape.js/)** renders structured ego-networks and W3C PROV lineage trees.

### Innovation 9: Hybrid BM25 + INT8 Dense Vector Search with Reciprocal Rank Fusion (RRF) (P1 — Enhanced Core)
- **Problem Solved:** Keyword search misses semantic concepts; pure vector search misses exact CVEs, hashes, and IP addresses.
- **Our Proposed Approach:** Combines SQLite FTS5 `bm25()` (custom technical tokenizer) with 384-d INT8 embeddings via **Reciprocal Rank Fusion ($k=60$)** in $<15\text{ ms}$.

### Innovation 10: Zero-Shot ONNX INT8 GLiNER + Defang Parser (P1 — Enhanced Core)
- **Problem Solved:** Extracting custom OSINT entities (`Threat Actor`, `Malware`, `Crypto Wallet`, `Vessel`, `Executive`) from unstructured text and defanged threat advisories (`hxxps://evil[.]com`) on a CPU-only PC.
- **Our Proposed Approach:** Deterministic defang normalizer + **[GLiNER](https://aclanthology.org/2024.naacl-long.300/) (`gliner_small-v2.1` INT8 ONNX)** running locally in ~180 MB RAM.

### Innovation 11: Spatiotemporal HDBSCAN + Kleinberg Burst Anomaly Detection (P2 — Advanced Analytics)
- **Problem Solved:** Spotting coordinated campaigns—such as sudden spikes in certificate issuance (`crt.sh`) or GDELT news volume—and geographic clustering of physical addresses/IPs.
- **Our Proposed Approach:** **Kleinberg 2-state burst automaton / Poisson Z-score** on timelines + **Haversine HDBSCAN** on geospatial coordinates.

### Innovation 12: Reproducible Investigation Playbooks & Court-Defensible Audit Bundles (P2 — Advanced Analytics)
- **Problem Solved:** Ensuring another analyst can audit or reproduce every step of an investigation.
- **Our Proposed Approach:** Exports a signed ZIP/JSON-LD **W3C PROV + FollowTheMoney + STIX 2.1 Verification Bundle** containing the hash-chained audit log, raw evidence SHA-256 digests, and Fellegi-Sunter merge ledger.
