"""tests/test_m09_api_and_exports.py - Comprehensive Unit Tests for M09.

Validates FastAPI REST Endpoints, Demonstration Workspace Seeding,
and Multi-Format Exporters (JSON, CSV, STIX 2.1, FtM JSONL, W3C PROV).
"""

from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_api_health_endpoint(client):
    """Test GET /api/health returns system diagnostics."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["version"] == "2.0.0"
    assert data["database_wal"] is True
    assert data["connectors_total"] >= 24


def test_workspaces_crud_and_demo_seed(client):
    """Test workspace listing and creation."""
    resp = client.get("/api/workspaces")
    assert resp.status_code == 200
    workspaces = resp.json()
    assert len(workspaces) >= 1
    # Check demo workspace
    assert any("Operation Sentinel" in w.get("name", "") for w in workspaces)

    # Create new workspace
    new_ws = client.post(
        "/api/workspaces",
        json={
            "name": "API Test Case",
            "description": "Integration test workspace",
            "tlp_marking": "TLP:CLEAR",
            "opsec_mode": "STANDARD",
        },
    ).json()
    assert new_ws["name"] == "API Test Case"
    assert new_ws["id"].startswith("ws_")


def test_entities_and_claims_endpoints(client):
    """Test entity and claim creation via REST API."""
    workspaces = client.get("/api/workspaces").json()
    ws_id = workspaces[0]["id"]

    # Create entity
    ent = client.post(
        f"/api/workspaces/{ws_id}/entities",
        json={
            "ftm_schema": "Domain",
            "raw_value": "api-target.com",
            "display_label": "api-target.com",
            "risk_score": 40,
        },
    ).json()
    assert ent["canonical_value"] == "api-target.com"

    # List entities
    ents = client.get(f"/api/workspaces/{ws_id}/entities?q=api-target").json()
    assert len(ents) >= 1
    assert ents[0]["id"] == ent["id"]


def test_graph_and_search_endpoints(client):
    """Test graph analytics and hybrid search endpoints."""
    workspaces = client.get("/api/workspaces").json()
    ws_id = workspaces[0]["id"]

    # Graph
    graph_resp = client.get(f"/api/workspaces/{ws_id}/graph")
    assert graph_resp.status_code == 200
    graph_data = graph_resp.json()
    assert "nodes" in graph_data
    assert "edges" in graph_data
    assert "top_hubs" in graph_data
    assert "predicted_links" in graph_data

    # Search
    search_resp = client.get(f"/api/workspaces/{ws_id}/search?q=darkshadow")
    assert search_resp.status_code == 200
    results = search_resp.json()
    assert isinstance(results, list)


def test_multi_format_exporters(client):
    """Test export endpoints for JSON, CSV, STIX 2.1, FtM JSONL, and W3C PROV."""
    workspaces = client.get("/api/workspaces").json()
    ws_id = workspaces[0]["id"]

    # 1. JSON Export
    json_resp = client.get(f"/api/workspaces/{ws_id}/export?format=json")
    assert json_resp.status_code == 200
    json_data = json_resp.json()
    assert json_data["format"] == "LocalOSINT_Workspace_JSON"
    assert "entities" in json_data
    assert "claims" in json_data

    # 2. CSV Export
    csv_resp = client.get(f"/api/workspaces/{ws_id}/export?format=csv")
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    assert "ftm_schema,canonical_value,display_label" in csv_resp.text

    # 3. STIX 2.1 Export
    stix_resp = client.get(f"/api/workspaces/{ws_id}/export?format=stix")
    assert stix_resp.status_code == 200
    stix_data = stix_resp.json()
    assert stix_data["type"] == "bundle"
    assert "objects" in stix_data
    types = {obj["type"] for obj in stix_data["objects"]}
    assert "infrastructure" in types or "ipv4-addr" in types or "identity" in types

    # 4. FollowTheMoney JSONL Export
    ftm_resp = client.get(f"/api/workspaces/{ws_id}/export?format=ftm")
    assert ftm_resp.status_code == 200
    first_line = ftm_resp.text.strip().split("\n")[0]
    ftm_obj = json.loads(first_line)
    assert "schema" in ftm_obj
    assert "properties" in ftm_obj

    # 5. W3C PROV-JSON Export
    prov_resp = client.get(f"/api/workspaces/{ws_id}/export?format=prov")
    assert prov_resp.status_code == 200
    prov_data = prov_resp.json()
    assert "prefix" in prov_data
    assert "entity" in prov_data
    assert "agent" in prov_data


def test_connectors_and_settings_endpoints(client):
    """Test connector listing and tamper-evident audit log verification."""
    conns = client.get("/api/connectors").json()
    assert len(conns) >= 24

    settings_resp = client.get("/api/settings").json()
    assert "settings" in settings_resp
    assert "audit_integrity" in settings_resp
    assert settings_resp["audit_integrity"]["is_valid"] is True

    audit_resp = client.get("/api/audit-logs").json()
    assert len(audit_resp) >= 1
    assert audit_resp[0]["prev_hash"] == "0" * 64
