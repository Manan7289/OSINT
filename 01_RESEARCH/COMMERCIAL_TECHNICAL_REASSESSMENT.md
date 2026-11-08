# COMMERCIAL_TECHNICAL_REASSESSMENT.md — Deep Engineering Reverse-Analysis of Commercial OSINT Systems

## 1. Executive Summary
Rather than comparing commercial OSINT platforms at a superficial marketing level, this reassessment examines **how leading commercial systems actually engineer their pipelines**—based on published patents, technical documentation, transform specifications, API schemas, and academic collaborations—and determines where a local-first workstation can **match or exceed** their analytical tradecraft while maintaining strict honesty about proprietary data moats.

---

## 2. Subsystem-by-Subsystem Technical Analysis of Commercial Platforms

### 2.1 Data Ingestion & Transform Orchestration
- **How Commercial Systems Work:**
  - **[Maltego One](https://www.identintel.com/state-of-osint/) & [Transform Hub](https://www.maltego.com/transform-hub/):** Uses a stateless request-response Transform protocol (XML/JSON) where a client sends an input Entity (`maltego.Domain`) + slider limit (e.g., 12, 50, 255) to a Transform Distribution Server (iTDS), which returns child Entities and Link properties ([Maltego SecurityTrails Docs](https://docs.maltego.com/en/support/solutions/articles/15000045562-maltego-securitytrails-transforms)).
  - **[Recorded Future](https://www.recordedfuture.com/platform/intelligence-graph):** Continuously ingests RSS, paste sites, registry feeds, NVD/EPSS, and dark-web forums into a streaming NLP pipeline that maps mentions to canonical ontology IDs ([TalTech Technical Architecture Analysis](https://digikogu.taltech.ee/et/Download/11909a8b-63e8-4b30-b9bf-e698e471161b)).
  - **[Social Links (`SL API`)](https://sociallinks.io/products/sl-api-cybersecurity) & [ShadowDragon (`SocialNet`)](https://www.identintel.com/state-of-osint/):** Broker real-time headless browser/API queries across 500+ platforms and return normalized entity-link graphs.
- **What LocalOSINT Should Reproduce & Improve:**
  - *Reproduce:* Maltego's granular **"Transform / Playbook"** execution model (run a single targeted transform on one selected node, or chain a multi-step playbook) alongside Recorded Future's continuous background feed polling (RSS, CISA KEV, NVD, ThreatFox).
  - *Improve:* Maltego transforms often dump hundreds of noisy nodes directly onto the analyst's canvas without staging or deduplication. LocalOSINT introduces a **"Staging & Confidence Triage Buffer"** so analysts can preview, filter by Admiralty grade, or auto-suppress high-degree CDN super-nodes before committing nodes to the main graph.

### 2.2 Entity Resolution & Cross-Lingual Identity Matching
- **How Commercial Systems Work:**
  - **[Babel Street (`Babel X` / Rosette Text Analytics)](https://www.joinmassive.com/blog/osint-market-map):** Uses hybrid phonetic transliteration, script normalization (Cyrillic/Arabic/CJK to Latin), and weighted n-gram similarity to match names across languages ([Y2 Evaluation Guide](https://y2.dev/blog/best-osint-aggregation-tools-2026/)).
  - **Quantexa & Palantir Gotham ([OSINT Market Map](https://www.joinmassive.com/blog/osint-market-map)):** Use dynamic compound record linkage where entities are resolved not just by lexical similarity, but by shared structural context (shared address, shared director, shared phone/domain).
- **What LocalOSINT Should Reproduce & Improve:**
  - Implement **transliteration/Unicode NFKD normalization + Soundex/Metaphone phonetic blocking + Fellegi-Sunter with EM and graph-neighbor agreement**, plus explainable **Waterfall Match Charts** (showing exactly how much each field agreement or disagreement contributed to the final probability).

### 2.3 Intelligence Correlation, Risk Scoring & De-Noising
- **How Commercial Systems Work:**
  - **[Recorded Future Risk Score (0–99)](https://digikogu.taltech.ee/et/Download/11909a8b-63e8-4b30-b9bf-e698e471161b):** Computes a composite score driven by transparent, triggered "Risk Rules" (e.g., *"+35: Historically linked to C2", "+25: Recently registered domain", "+15: Self-signed TLS certificate"*) combined with temporal decay.
  - **[GreyNoise (`RIOT` & `Noise`)](https://azutech.medium.com/threat-intelligence-in-practice-investigating-indicators-with-open-and-free-tier-tools-fee59a6579eb):** Separates benign common business infrastructure (`RIOT`: Cloudflare, Googlebot, Akamai, Microsoft 365) and indiscriminate background internet scanners (`Noise`) from targeted adversary infrastructure.
- **What LocalOSINT Should Reproduce & Improve:**
  - **Explainable Rule-Based Risk & Decay Engine:** Never output an opaque "Risk = 75" integer. Every entity risk score in LocalOSINT must store an array of **Triggered Risk Evidence Rules** with explicit point weights and temporal half-life decay.
  - **Local "Common Infrastructure / CDN Whitelist (RIOT-Lite)":** Ship a local CIDR/ASN/Domain reference list of major CDNs, cloud providers, public DNS resolvers, and top-1,000 benign domains so the graph engine automatically marks them as `SHARED_INFRASTRUCTURE` (`hub_penalty = 0.15`) rather than treating them as dedicated adversary links.

### 2.4 Evidence Custody & Court-Defensible Provenance
- **How Commercial Systems Work:**
  - **[Maltego + Hunchly](https://www.identintel.com/state-of-osint/) & [Skopenow Workbench](https://www.identintel.com/state-of-osint/):** Capture timestamped web pages, HTTP headers, DOM snapshots, and SHA-256 hashes so investigative findings survive legal or peer review.
- **What LocalOSINT Should Reproduce & Improve:**
  - Implement a **W3C PROV-Compliant Evidence Vault** storing the raw HTTP payload, response headers, UTC retrieval timestamp, SHA-256 hash, source independence factor, and epistemic status (`OBSERVED_FACT`, `CORROBORATED_FACT`, `DERIVED_INFERENCE`, `HYPOTHESIS`).

---

## 3. Honest Classification: What Can vs. Cannot Be Done Locally

| Capability Category | 100% Local & Offline (Core Tier) | Local + Free Public APIs (Enhanced Tier) | Requires Paid Commercial API Keys (Optional BYO Tier) | Not Pursued (Unethical, Illegal, or Proprietary Data Moat) |
| :--- | :--- | :--- | :--- | :--- |
| **Infrastructure & Network** | Zone file/PCAP/log parsing, CIDR/ASN math, RIOT-Lite CDN filtering, DGA entropy | Live DoH DNS, IANA RDAP, `crt.sh` CT logs, RIPEstat BGP/ASN, Shodan InternetDB, URLScan public | Shodan Pro full banner search, SecurityTrails historical DNS, Censys host search, GreyNoise API | Unauthorized active port/vulnerability scanning of third-party networks |
| **Vulnerability & Threat Intel** | Local STIX/MISP bundle analysis, CVSS/EPSS composite risk math, YARA/regex scanning | NIST NVD API 2.0, CISA KEV catalog, FIRST.org EPSS API, Abuse.ch URLhaus/ThreatFox/MalwareBazaar | VirusTotal v3 multi-engine & passive DNS, AlienVault OTX pulses, Recorded Future / Flashpoint | Purchasing or hosting stolen credential dumps / stealer logs |
| **Corporate, Sanctions & News** | FollowTheMoney entity resolution, PDF/DOCX/EXIF forensics, graph centrality & Leiden clustering | GLEIF Global LEI & ownership trees, SEC EDGAR XBRL/filings, OpenAlex, OpenSanctions, Wikidata SPARQL, GDELT 2.0 | OpenCorporates commercial API, LexisNexis / Dow Jones | Scraping behind authenticated corporate paywalls |
| **Geospatial & Identity** | Haversine HDBSCAN clustering, Geohash R*Tree indexing, Kleinberg burst detection | OpenStreetMap Nominatim geocoding, GitHub public profile/commit API | Commercial satellite tasking (Maxar/Planet) | Mobile advertising bidstream tracking (Locate X), covert personal doxxing, CAPTCHA/auth bypass |
