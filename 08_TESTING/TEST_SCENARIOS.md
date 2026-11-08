# TEST_SCENARIOS.md — Concrete End-to-End Investigation Test Scenarios

## Scenario 1: Corporate & Infrastructure Due Diligence Playbook
1. Create workspace `"Operation Atlas"` (`TLP:AMBER`, `opsec_mode="PASSIVE_ONLY"`).
2. Run playbook on `"cloudflare.com"` across `dns_doh`, `rdap_bootstrap`, `crtsh_ct`, `ripestat_data`, `gleif_lei`, `sec_edgar`, `opensanctions`.
3. Verify `PASSIVE_ONLY` mode allows all registry lookups while blocking direct target crawling.
4. Verify `gleif_lei` and `sec_edgar` (two distinct `upstream_lineage_family` values) corroborate the corporate entity to `epistemic_status = "CORROBORATED_FACT"`.

## Scenario 2: Defanged Threat Advisory & Vulnerability Triage
1. Paste a threat advisory containing defanged indicators (`hxxps://portal[.]malicious-actor[.]org`, `185.220.101[.]34`, `CVE-2024-3400`) into `POST /api/collect/document-text`.
2. Run `nvd_cve_v2`, `cisa_kev`, and `first_epss` on `CVE-2024-3400`.
3. Verify the CVE entity receives a composite risk score $\ge 90$ reflecting active exploitation and appears in the timeline and STIX 2.1 export bundle.

## Scenario 3: Duplicate Entity Resolution, Waterfall Inspection & Unmerge Rollback
1. Insert `"Acme Global Defense Inc."` (`US`, `AS15133`) and `"Acme Global Defense LLC"` (`US`, `AS15133`) with separate relationships.
2. Call `GET /api/workspaces/{id}/entity-resolution` and inspect the `waterfall_factors` array.
3. Call `POST /api/workspaces/{id}/entity-resolution/merge`, verify relationships consolidate onto the winner entity, then call `POST /api/workspaces/{id}/entity-resolution/unmerge/{merge_id}` and verify both entities and their original relationships are restored.
