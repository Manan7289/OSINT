# M06 — W3C PROV Lineage DAG, Dong Copying Detection & Subjective Logic Fusion Engine

## 1. Module Name & Identifier
- **Module Title:** M06 — W3C PROV Lineage DAG, Dong Copying Detection & Subjective Logic Fusion Engine
- **Target File Path(s):** `backend/core/provenance_fusion.py`

## 2. Purpose
Prevents circular reporting from inflating intelligence confidence by tracking upstream source lineage, discounting copied/syndicated evidence, fusing opinions via Jøsang Subjective Logic $\omega = (b, d, u, a)$, and enforcing commit-time epistemic stratification.

## 3. User-Facing Functionality
Powers View 8 (W3C PROV & Subjective Logic Provenance Ledger) and provides Belief ($b$), Disbelief/Conflict ($d$), and Uncertainty ($u$) metrics across all views.

## 4. Internal Responsibilities
Maps NATO Admiralty grades (`A1`–`F6`) to initial opinions $\omega_i$, groups evidence supporting or contradicting a claim by `upstream_lineage_family` and SimHash overlap, applies Averaging Fusion ($\tilde{\oplus}$) within dependent groups, applies Cumulative Fusion ($\oplus$) across independent groups, and updates `claims.epistemic_status`.

## 5. Inputs
List of `EvidenceArtifact` records + `claim_evidence` stance (`SUPPORTS` or `CONTRADICTS`).

## 6. Outputs
Updated Subjective Logic tuple `(sl_belief, sl_disbelief, sl_uncertainty, projected_probability)`, `independence_weight`, and `epistemic_status`.

## 7. Required Algorithms & Mathematical Formulations
1. **Dong Copying Discount ([VLDB 2009](http://www.vldb.org/pvldb/vol2/vldb09-335.pdf)):** Discounts later evidence sharing `parent_evidence_id`, `upstream_lineage_family`, or SimHash Hamming distance $\le 6$.
2. **Jøsang Subjective Logic Cumulative Fusion ($\oplus$, [UiO 2017](https://www.mn.uio.no/ifi/english/people/aca/josang/publications/jwz2017-fusion.pdf)):**
   $$b_{1 \oplus 2} = \frac{b_1 u_2 + b_2 u_1}{u_1 + u_2 - u_1 u_2}, \quad u_{1 \oplus 2} = \frac{u_1 u_2}{u_1 + u_2 - u_1 u_2}$$
3. **Averaging Belief Fusion ($\tilde{\oplus}$):**
   $$b_{1 \tilde{\oplus} 2} = \frac{b_1 u_2 + b_2 u_1}{u_1 + u_2}, \quad u_{1 \tilde{\oplus} 2} = \frac{2 u_1 u_2}{u_1 + u_2}$$

## 8. Dependencies
`math`, `M02`.

## 9. Backend Integration
Called automatically whenever evidence is linked to an entity or claim.

## 10. Frontend Integration
Displays epistemic badges (`OBSERVED_FACT`, `CORROBORATED_FACT`, `DERIVED_INFERENCE`, `HYPOTHESIS`, `UNVERIFIED_CLAIM`) and Subjective Logic bars.

## 11. Data Storage Requirements
Updates `evidence_artifacts.independence_weight`, `claims`, and `entities`.

## 12. Error-Handling Requirements
Handles boundary case $u_1 = u_2 = 0$ via dogmatism limit $\epsilon = 10^{-4}$ so division by zero never occurs.

## 13. Security, OPSEC & Privacy Requirements
Guarantees no claim can reach `CORROBORATED_FACT` without $\ge 2$ distinct `upstream_lineage_family` sources.

## 14. Testing Requirements
`tests/test_m06_provenance_fusion.py`: Prove 5 syndicated copies from 1 lineage family yield lower belief $b$ than 2 independent `A1` sources; verify conflict detection when $d \ge 0.25$.

## 15. Dependencies on Other Modules
Depends on `M02`.

## 16. Completion & Acceptance Criteria
All mathematical invariants ($b + d + u = 1.0$) and tests in `test_m06_provenance_fusion.py` pass.
