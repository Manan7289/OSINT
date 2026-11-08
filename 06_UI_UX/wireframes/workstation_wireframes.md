# workstation_wireframes.md — Layout Wireframes for LocalOSINT v2.0

## 1. Master Workstation Frame & Graph View (`view-graph`)
```text
+------------------------------------------------------------------------------------------------------+
| [OS] LocalOSINT v2.0   | Active Case: [Operation Sentinel (TLP:AMBER) v] [PASSIVE_ONLY]              |
|                        | [Hybrid RRF Search...          ] [Export: JSON | CSV | STIX 2.1 | FtM | PROV]|
+------------------------+-----------------------------------------------------------------------------+
| INVESTIGATION VIEWS    | TOOLBAR: [As-Of Date: 2026-11-08] [x] Dampen CDN Super-Nodes [Zoom+][Zoom-] |
| > 1. Command Dashboard |---------------------------------------------------+-------------------------+
|   2. OSINT Collection  |                                                   | NODE & PIVOT INSPECTOR  |
|   3. Entity Explorer   |          [example.org] (Domain, b=0.94)           | [Domain] example.org    |
| * 4. Relationship Graph|               /                 \                 | Admiralty: A1           |
|   5. Entity Resolution |   RESOLVES_TO (FACT)     HAS_SUBDOMAIN (FACT)     | Opinion: b=0.94 u=0.06  |
|   6. Timeline & Bursts |             /                     \               | Leiden Comm: #1         |
|   7. Geospatial Map    |   [93.184.216.34]           [api.example.org]     | IEF-PageRank: 0.412     |
|   8. W3C PROV Ledger   |          |                                        |-------------------------|
|   9. GraphRAG & Reports|   ANNOUNCED_BY (CORROBORATED)                     | PREDICTED MISSING LINKS |
|                        |          v                                        | -> auth.example.org     |
| SYSTEM & OPERATIONS    |     [AS15133 Edgecast] (Shared Infra Dampened)    |    (Adamic-Adar: 1.84)  |
|  10. Task Monitor      |                                                   |-------------------------|
|  11. API Vault & OPSEC |                                                   | [Pivot Playbook on Node]|
+------------------------+---------------------------------------------------+-------------------------+
```

## 2. Fellegi-Sunter EM Entity Resolution & Waterfall View (`view-resolution`)
```text
+------------------------------------------------------------------------------------------------------+
| FELLEGI-SUNTER EM PROBABILISTIC RECORD LINKAGE (Blocking Reduction: 71.7x | EM Converged: 8 iters)   |
+------------------------------------------------------------------------------------------------------+
| Entity A                 | Entity B                  | Log2 Weight | Match Prob | Waterfall Factors  |
|--------------------------+---------------------------+-------------+------------+--------------------|
| ShadowNet Security Inc   | ShadowNet Security LLC    |   +6.42     |   93.8%    | [++++] name_jw +4.1|
| (Company, US)            | (Company, US)             |             | CONFIRMED  | [++]   asn     +1.4|
|                          |                           |             |            | [+]    country +0.9|
|                                                                                 | [Merge Duplicate]  |
+------------------------------------------------------------------------------------------------------+
| REVERSIBLE MERGE AUDIT LEDGER (`entity_merge_ledger`)                                                |
| Merge ID     | Winner Entity          | Absorbed Snapshot      | Merged At            | Action       |
| mrg_89a1c02  | Acme Holdings Corp     | Acme Holdings Ltd      | 2026-11-08T10:15:00Z | [Unmerge]    |
+------------------------------------------------------------------------------------------------------+
```
