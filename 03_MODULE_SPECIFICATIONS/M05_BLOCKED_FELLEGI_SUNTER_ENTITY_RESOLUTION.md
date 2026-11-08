# M05 — 3-Pass Blocking, Unsupervised Fellegi-Sunter EM & Reversible Merge Engine

## 1. Module Name & Identifier
- **Module Title:** M05 — 3-Pass Blocking, Unsupervised Fellegi-Sunter EM & Reversible Merge Engine
- **Target File Path(s):** `backend/core/entity_resolution.py`

## 2. Purpose
Resolves duplicate and alias entities across heterogeneous OSINT sources in $O(N \log N)$ time using multi-pass blocking, unsupervised Expectation-Maximization (EM) Fellegi-Sunter parameter estimation, Inverse Entity Frequency (IEF) weight scaling, and a 100% reversible merge ledger.

## 3. User-Facing Functionality
Powers View 5 (Entity Resolution Workbench), displaying candidate match probabilities, Bayes-factor waterfall charts, and one-click **Merge** / **Unmerge** buttons.

## 4. Internal Responsibilities
Generates candidate pairs via 3 blocking passes (`PHONETIC_SORT` window $w=15$, `APEX_PREFIX`, and `MINHASH_LSH`), computes comparison vectors $\gamma$, runs EM to estimate $m_k$ and $u_k$ probabilities, applies IEF adjustments, and records full snapshots in `entity_merge_ledger` during merges.

## 5. Inputs
`workspace_id: str`, `min_probability: float`, or `(primary_entity_id, duplicate_entity_id)`.

## 6. Outputs
Ranked candidate pairs with `waterfall_factors`, `blocking_stats`, and `MergedEntity` / `RevertedEntity` states.

## 7. Required Algorithms & Mathematical Formulations
1. **Sorted Neighborhood ($w=15$) + 3-Gram MinHash LSH Blocking.**
2. **Jaro-Winkler & Token Jaccard Similarity.**
3. **Unsupervised Fellegi-Sunter EM ([arXiv:2008.04443v3](https://arxiv.org/html/2008.04443v3)):** E-step computes posterior match probability $p_i^{(t)}$ for each candidate pair; M-step updates $m_{k,l}^{(t+1)}$ and $u_{k,l}^{(t+1)}$; IEF adjustment adds $\log_2(N / \text{freq}(v))$ for exact rare attribute matches.

## 8. Dependencies
`math`, `json`, `numpy`, `M02`, `M06`.

## 9. Backend Integration
Exposes `/api/workspaces/{id}/entity-resolution`, `/merge`, and `/unmerge/{merge_id}`.

## 10. Frontend Integration
Renders waterfall contribution bars and merge/unmerge history in View 5.

## 11. Data Storage Requirements
Reads/writes `entity_blocking_keys`, `entities`, `claims`, and `entity_merge_ledger`.

## 12. Error-Handling Requirements
Prevents self-merge (`primary_id == duplicate_id`) and validates workspace ownership before merge/unmerge.

## 13. Security, OPSEC & Privacy Requirements
Logs every merge and unmerge operation to the hash-chained `audit_logs` table.

## 14. Testing Requirements
`tests/test_m05_entity_resolution.py`: Verify $>50\times$ pair reduction on 1,000+ entities, EM convergence, waterfall factor generation, and bit-for-bit restoration after Merge $\rightarrow$ Unmerge.

## 15. Dependencies on Other Modules
Depends on `M02`, `M06`.

## 16. Completion & Acceptance Criteria
All tests in `test_m05_entity_resolution.py` pass.
