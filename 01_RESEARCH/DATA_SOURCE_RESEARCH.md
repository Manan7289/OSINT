# DATA_SOURCE_RESEARCH.md — Comprehensive Public & Commercial OSINT Data Source Specification

## 1. Overview & Source Independence Taxonomy
Every data source integrated into **LocalOSINT v2.0** is cataloged with its exact endpoint, authentication model, rate-limit budget, NATO Admiralty baseline reliability (`A`–`F`), **Upstream Lineage Family** (used by our Dong et al. copying-detection engine to prevent circular corroboration when two APIs mirror the same underlying registry), and temporal cache TTL.

---

## 2. Master Catalog of 24 Verified OSINT Data Sources

### 2.1 Domain, DNS, Certificate & Routing Infrastructure

| Source ID | Official Name & Documentation URL | Data Returned | Auth & Pricing | Rate Limits & Cache TTL | Upstream Lineage Family | Admiralty Baseline |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| `dns_doh` | [Cloudflare DNS-over-HTTPS (`1.1.1.1`)](https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-https/) | Authoritative A, AAAA, CNAME, MX, NS, TXT, SPF, DMARC, SOA, CAA records | Keyless / Free | 60 req/min; TTL 30m | `LIVE_DNS_AUTHORITATIVE` | `A1` |
| `rdap_bootstrap` | [IANA RDAP Bootstrap & `rdap.org`](https://about.rdap.org/) ([Protocol Guide](https://www.homehost.com.br/blog/dominio/whois-rdap-protocolo-de-dominios/)) | RFC 7480–7484 structured JSON domain/IP/ASN registration, registrar vCard, status flags, registration/expiration timestamps | Keyless / Free | 30 req/min; TTL 24h | `ICANN_RIR_RDAP_REGISTRY` | `A1` |
| `crtsh_ct` | [crt.sh Certificate Transparency Aggregator](https://crt.sh/) ([Technical Overview](https://learn.secbyte.org/tools/crt-sh)) | RFC 6962 X.509 certificate logs, Subject Alternative Names (SANs), issuer CAs, serials, notBefore/notAfter | Keyless / Free | 15 req/min; TTL 12h | `RFC6962_CT_LOGS` | `A1` |
| `ripestat_data` | [RIPEstat Data API](https://stat.ripe.net/docs/02.data-api) & [Looking Glass](https://stat.ripe.net/docs/data-api/api-endpoints/looking-glass) | BGP announced prefixes, AS holders, routing consistency, RIR allocation history, MaxMind GeoLite country/city | Keyless / Free (Max 8 concurrent req/IP) | 45 req/min; TTL 2h | `RIPE_RIS_BGP_COLLECTORS` | `A1` |
| `urlscan_public` | [URLScan.io Public Search API](https://www.xftf.org/lessons/intro-to-osint/osint-sources/domains-dns-infrastructure) | Historical DOM snapshots, contacted IPs/ASNs, HTTP headers, TLS certificate hashes, page titles | Keyless public search (Optional free key for higher quota) | 20 req/min; TTL 6h | `URLSCAN_SANDBOX_CRAWL` | `A2` |

---

### 2.2 Defensive Cyber Intelligence, Vulnerabilities & Exploit Prioritization

| Source ID | Official Name & Documentation URL | Data Returned | Auth & Pricing | Rate Limits & Cache TTL | Upstream Lineage Family | Admiralty Baseline |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| `shodan_internetdb` | [Shodan InternetDB](https://internetdb.shodan.io/) ([12 Open APIs Reference](https://medium.verylazytech.com/12-open-apis-every-osint-researcher-should-know-a-practical-guide-to-powerful-cyber-investigations-2eb36ee2a4b0)) | Open TCP ports, CPE software strings, hostnames, tags (`vpn`, `cloud`, `tor`), and associated CVEs for any IPv4 | Keyless / Free | 40 req/min; TTL 1h | `SHODAN_CRAWL_ENGINE` | `A2` |
| `nvd_cve_v2` | [NIST National Vulnerability Database API 2.0](https://nvd.nist.gov/developers/vulnerabilities) | Official CVE descriptions, CVSS v3.1/v4.0 vectors, CWE weaknesses, affected CPE configurations | Keyless (5 req/30s) or Free API Key (50 req/30s) | 10–50 req/min; TTL 24h | `NIST_NVD_CVE` | `A1` |
| `cisa_kev` | [CISA Known Exploited Vulnerabilities (KEV) Catalog](https://www.cisa.gov/known-exploited-vulnerabilities-catalog) ([GitHub Mirror](https://github.com/cisagov/kev-data)) | Authoritative list of CVEs confirmed exploited in the wild, ransomware campaign usage flag, remediation due dates | Keyless / Free JSON feed | Bulk daily sync; Local SQLite lookup in `<1ms` | `CISA_US_GOV_KEV` | `A1` |
| `first_epss` | [FIRST.org Exploit Prediction Scoring System (EPSS) API](https://api.first.org/epss/) ([Elastic Docs](https://www.elastic.co/docs/reference/integrations/first_epss)) | Daily probability ($0.0–1.0$) and percentile that a CVE will be exploited in the wild within 30 days | Keyless / Free (`https://api.first.org/data/v1/epss`) | 30 req/min; TTL 24h | `FIRST_EPSS_MODEL` | `A1` |
| `abusech_threatfox` | [Abuse.ch ThreatFox IOC API](https://threatfox.abuse.ch/) | Botnet C2 IP:port, malicious domains, payload hashes, malware family tags, confidence levels | Keyless / Optional free Auth-Key | 30 req/min; TTL 30m | `ABUSECH_SWISS_CTI` | `B2` |
| `abusech_urlhaus` | [Abuse.ch URLhaus API](https://urlhaus.abuse.ch/api/) | Active and historical malware distribution URLs, payload SHA-256 hashes, ASN/host takedown status | Keyless / Optional free Auth-Key | 30 req/min; TTL 30m | `ABUSECH_SWISS_CTI` | `B2` |
| `abusech_bazaar` | [Abuse.ch MalwareBazaar API](https://bazaar.abuse.ch/api/) ([Guide](https://casrai.org/guides/malwarebazaar)) | Malware sample metadata by SHA-256/MD5/TLSH/imphash, YARA rule hits, code-signing certificate serials | Free Community Auth-Key | 30 req/min; TTL 6h | `ABUSECH_SWISS_CTI` | `A2` |

---

### 2.3 Corporate Ownership, Legal Entities, Sanctions & Academic Registries

| Source ID | Official Name & Documentation URL | Data Returned | Auth & Pricing | Rate Limits & Cache TTL | Upstream Lineage Family | Admiralty Baseline |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| `gleif_lei` | [GLEIF Global LEI API v1](https://documenter.getpostman.com/view/7679680/SVYrrxuU) ([API Store](https://apis.apievangelist.com/store/gleif-search-api/)) | ISO 17442 Legal Entity Identifiers (LEI), registered legal addresses, registration authority IDs, and **Level-2 direct/ultimate parent & child ownership trees** | Keyless / Free (`https://api.gleif.org/api/v1/lei-records`) | 60 req/min; TTL 24h | `GLEIF_LOU_REGISTRY` | `A1` |
| `sec_edgar` | [U.S. SEC EDGAR API](https://stackoverflow.com/questions/2614767/using-r-to-analyze-balance-sheets-and-income-statements) | Public company CIK numbers, SIC codes, 10-K/8-K/13F filings, insider ownership, XBRL financial facts | Keyless / Free (Requires `User-Agent: AppName ContactEmail`) | 10 req/sec; TTL 24h | `US_SEC_EDGAR` | `A1` |
| `opensanctions` | [OpenSanctions API (`yente`)](https://www.opensanctions.org/docs/api/) ([Swagger UI](https://api.opensanctions.org/docs)) | Consolidated global sanctions (OFAC, EU, UN, UK), Politically Exposed Persons (PEPs), and criminal watchlists in FollowTheMoney format | Local bulk JSONL import (Free for research) or API key | Local SQLite FTS5 `<5ms` or 30 req/min API | `OPENSANCTIONS_CONSOLIDATED` | `A1` |
| `wikidata_sparql` | [Wikidata Linked Open Data / SPARQL](https://storage.imrpress.com/IMR/2115645204216127500/application/2942-3309-53-6-50577.pdf) | Multilingual organization/person aliases, official websites (`P856`), parent organizations (`P749`), founders (`P112`), headquarters coordinates (`P625`) | Keyless / Free | 30 req/min; TTL 24h | `WIKIMEDIA_WIKIData` | `B2` |
| `openalex_orgs` | [OpenAlex Institutions & Authors API](https://www.slideshare.net/slideshow/winston-intro-to-the-openalex-api/251908093) | Research & corporate institution profiles, ROR IDs, geolocation coordinates, associated domains, publication co-authorship graphs | Keyless / Free | 60 req/min; TTL 24h | `OPENALEX_ROR` | `A2` |

---

### 2.4 Web Archives, Global News, Code Footprints & Geospatial

| Source ID | Official Name & Documentation URL | Data Returned | Auth & Pricing | Rate Limits & Cache TTL | Upstream Lineage Family | Admiralty Baseline |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| `wayback_cdx` | [Internet Archive Wayback Machine CDX API](https://systemweakness.com/zero-to-pro-the-ultimate-guide-to-cdx-api-for-your-bug-bounty-recon-journey-lets-talk-about-the-353946e67872) | Historical URL captures, timestamps, MIME types, HTTP status codes, SHA-1 content digests (enables change detection across snapshots) | Keyless / Free | 25 req/min; TTL 12h | `INTERNET_ARCHIVE_WAYBACK` | `A1` |
| `gdelt_doc_v2` | [GDELT Project DOC 2.0 API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) ([Agent Query Guide](https://www.swytchcode.com/content/gdelt-api-research-agents)) | Global news articles across 65+ languages, volume timeline curves (`timelinevolinfo`), tone/sentiment, source domains | Keyless / Free | 30 req/min; TTL 30m | `GDELT_GLOBAL_MEDIA` | `B2` |
| `github_rest` | [GitHub Public REST API](https://portal.findresearcher.sdu.dk/files/304653603/s10664-025-10742-x.pdf) & [Commit Attribution Analysis](https://teamusec.de/pdf/conf-ndss-holtgrave25.pdf) | User/Org profiles, repositories, commit author/committer email metadata, GPG key IDs, declared blog URLs | Keyless (60 req/hr) or Free PAT (5,000 req/hr) | 20–60 req/min; TTL 1h | `GITHUB_API` | `A2` |
| `nominatim_osm` | [OpenStreetMap Nominatim Geocoding API](https://nominatim.org/release-docs/develop/api/Search/) | Forward & reverse geocoding, WGS84 bounding boxes, OSM relation IDs, administrative boundaries | Keyless / Free (1 req/sec policy with custom User-Agent) | 20 req/min; TTL 7d | `OPENSTREETMAP_DB` | `A1` |

---

### 2.5 Optional BYO-Key Commercial Threat & Infrastructure APIs
- **[Shodan Host & Search API](https://www.shodan.io/)**, **[VirusTotal v3 API](https://www.virustotal.com/)**, **[GreyNoise Community/Enterprise API](https://azutech.medium.com/threat-intelligence-in-practice-investigating-indicators-with-open-and-free-tier-tools-fee59a6579eb)**, **[SecurityTrails Passive DNS API](https://docs.maltego.com/en/support/solutions/articles/15000045562-maltego-securitytrails-transforms)**, **[Censys Search 2.0 API](https://medium.verylazytech.com/12-open-apis-every-osint-researcher-should-know-a-practical-guide-to-powerful-cyber-investigations-2eb36ee2a4b0)**, and **[AlienVault OTX DirectConnect API](https://otx.alienvault.com/api)**.
- **Lineage Deduplication Note:** Because Shodan InternetDB and Shodan Pro share `SHODAN_CRAWL_ENGINE`, and Abuse.ch ThreatFox/URLhaus/MalwareBazaar share `ABUSECH_SWISS_CTI`, our Subjective Logic engine groups observations by `Upstream Lineage Family` before applying Cumulative Belief Fusion.
