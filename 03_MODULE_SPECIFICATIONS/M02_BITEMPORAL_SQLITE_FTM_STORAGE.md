# M02 — Bitemporal SQLite WAL/FTS5/R*Tree & FollowTheMoney Storage Engine

## 1. Module Name & Identifier
- **Module Title:** M02 — Bitemporal SQLite WAL/FTS5/R*Tree & FollowTheMoney Storage Engine
- **Target File Path(s):** `backend/core/database.py, backend/core/ontology.py`

## 2. Purpose
Implements the ACID relational, property-graph, bitemporal claim, full-text (`FTS5`), and spatial (`R*Tree`) persistence engine aligned with the OCCRP FollowTheMoney (FtM) ontology.

## 3. User-Facing Functionality
Supports workspace creation/switching, entity filtering, bitemporal time-slice queries, staging buffer promotion, and instant full-text search.

## 4. Internal Responsibilities
Initializes all 14 tables and virtual indices in WAL mode, canonicalizes values (IDNA punycode, lowercase domains/emails, uppercase ASNs/CVEs, stripped corporate suffixes), generates 3-pass blocking keys (`entity_blocking_keys`), and maintains RIOT-Lite common infrastructure flags (`is_shared_infra`).

## 5. Inputs
Typed entity payloads, reified claim objects (`valid_from`, `valid_until`, `epistemic_status`), raw evidence records, and search/filter predicates.

## 6. Outputs
Formatted dictionaries for Workspaces, Entities, Claims, Evidence Artifacts, Timeline Events, Tasks, and Reports.

## 7. Required Algorithms & Mathematical Formulations
1. **Unicode NFKD + Corporate Suffix Canonicalization.**
2. **Soundex / Metaphone Phonetic Key Generation** for blocking pass 1.
3. **Geohash-8 Bit-Interleaving Encoder** for spatial indexing.

## 8. Dependencies
`sqlite3`, `json`, `uuid`, `hashlib`, `idna`, `M01`.

## 9. Backend Integration
Provides `db = DatabaseManager()` singleton used by all upstream modules (`M03`–`M09`).

## 10. Frontend Integration
Backs `/api/workspaces/*`, `/api/connectors`, `/api/tasks`, and `/api/settings`.

## 11. Data Storage Requirements
Owns `data/localosint.db` (`WAL` mode, 14 tables/virtual tables).

## 12. Error-Handling Requirements
Uses `threading.RLock()` and `PRAGMA busy_timeout = 15000` to prevent `sqlite3.OperationalError: database is locked` under concurrent async collection.

## 13. Security, OPSEC & Privacy Requirements
All SQL queries use parameterized `?` placeholders (100% SQL injection immunity); cascade deletion purges FTS5 and vector tables.

## 14. Testing Requirements
`tests/test_m02_database.py`: Verify WAL pragma, workspace CRUD, entity canonicalization deduplication, bitemporal claim filtering (`as_of_time`), and FTS5 technical token queries.

## 15. Dependencies on Other Modules
Depends on `M01`.

## 16. Completion & Acceptance Criteria
All database schema tables initialize cleanly and pass `test_m02_database.py`.
