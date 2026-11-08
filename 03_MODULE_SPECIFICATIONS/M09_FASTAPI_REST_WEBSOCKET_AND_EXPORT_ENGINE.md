# M09 — FastAPI REST/WebSocket Server & Multi-Format Export Engine

## 1. Module Name & Identifier
- **Module Title:** M09 — FastAPI REST/WebSocket Server & Multi-Format Export Engine
- **Target File Path(s):** `backend/main.py, backend/exporters.py, run.py`

## 2. Purpose
Exposes all backend engines via validated FastAPI REST and WebSocket endpoints, seeds the initial demonstration workspace on first launch, and exports investigations to `JSON`, `CSV`, `STIX 2.1`, `FollowTheMoney (FtM) JSONL`, and `W3C PROV-JSON`.

## 3. User-Facing Functionality
Serves the entire HTTP API (`/api/*` and `/api/v2/*`), interactive OpenAPI docs (`/docs`), and one-click export downloads.

## 4. Internal Responsibilities
Validates requests with Pydantic models, routes commands to `M01`–`M08`, serializes standard STIX 2.1 bundles (`indicator`, `identity`, `relationship`, `note`), FollowTheMoney entity streams, and W3C PROV lineage bundles.

## 5. Inputs
HTTP REST requests and multipart file uploads.

## 6. Outputs
JSON responses, streaming CSV/JSONL downloads, and static frontend HTML/JS/CSS.

## 7. Required Algorithms & Mathematical Formulations
STIX 2.1 deterministic UUIDv5 / ID formatting and W3C PROV-JSON serialization.

## 8. Dependencies
`fastapi`, `uvicorn`, `pydantic`, `python-multipart`, `M01`–`M08`.

## 9. Backend Integration
Top-level ASGI application (`backend.main:app`).

## 10. Frontend Integration
Serves `frontend/index.html` at `/` and static assets at `/assets`.

## 11. Data Storage Requirements
Delegates all persistence to `M02`.

## 12. Error-Handling Requirements
Returns structured HTTP 400/404/422 JSON error payloads; never leaks raw stack traces or API keys.

## 13. Security, OPSEC & Privacy Requirements
Binds to `127.0.0.1` by default; enforces CORS and multipart upload size bounds.

## 14. Testing Requirements
`tests/test_m09_api_and_exports.py`: End-to-end `TestClient` verification of all endpoints and all 5 export formats (`json`, `csv`, `stix`, `ftm`, `prov`).

## 15. Dependencies on Other Modules
Depends on `M01`–`M08`.

## 16. Completion & Acceptance Criteria
All endpoints return HTTP 200 and pass `test_m09_api_and_exports.py`.
