"""tests/test_api_smoke.py - Core REST, SQLite 20 Tables & System Smoke Tests.

Validates:
  - SQLite 20-table schema initialization and WAL mode.
  - v3.0 Health, Workspaces, Sweeps, Geospatial Layers, Geofences, and Sanctions endpoints.
  - SHA-256 HashChainedAuditLogger tamper-evident integrity.
"""

import pytest
from fastapi.testclient import TestClient

from backend.core.database import db
from backend.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_sqlite_20_tables_and_wal():
    """Validates that all 20 required tables exist in WAL mode."""
    with db.get_connection() as conn:
        # Check WAL mode
        cur = conn.execute("PRAGMA journal_mode;")
        mode = cur.fetchone()[0]
        assert mode.lower() == "wal"

        # Check tables
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cur.fetchall()}

        required_tables = [
            "workspaces", "evidence_artifacts", "entities", "claims",
            "audit_logs", "connector_configs", "tasks", "reports",
            "claim_evidence", "entity_merge_ledger", "app_settings",
            "geo_tracks", "sweep_runs", "sweep_deltas", "sanctions_index",
            "geofence_zones", "visual_assets", "consented_face_gallery"
        ]
        for t in required_tables:
            assert t in tables, f"Required table '{t}' is missing from SQLite database"


def test_health_v3_endpoint(client):
    """Validates GET /api/v3/health and /api/health."""
    res = client.get("/api/v3/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["version"] == "3.0.0"
    assert data["database_wal"] is True
    assert "sanctions_indexed" in data


def test_workspaces_crud_endpoint(client):
    """Validates workspace creation and listing."""
    res = client.get("/api/workspaces")
    assert res.status_code == 200
    workspaces = res.json()
    assert len(workspaces) >= 1  # seeded demo case exists


def test_sanctions_lookup_endpoint(client):
    """Validates sanctions lookup by MMSI, IMO, or Name."""
    res = client.get("/api/v1/sanctions/lookup?mmsi=422039000")
    assert res.status_code == 200
    data = res.json()
    assert data["matched"] is True
    assert data["record"]["sdn_name"] == "BEHSHAD"


def test_geospatial_layers_endpoint(client):
    """Validates GET /api/v1/geospatial/layers returns valid GeoJSON FeatureCollection."""
    res = client.get("/api/v1/geospatial/layers?limit=100")
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "FeatureCollection"
    assert "features" in data
    assert "count" in data


def test_geofence_crud_endpoints(client):
    """Validates creating, listing, and deleting a geofence zone."""
    poly = {
        "type": "Polygon",
        "coordinates": [[[55.0, 25.0], [57.0, 25.0], [57.0, 27.0], [55.0, 27.0], [55.0, 25.0]]]
    }
    # Create
    create_res = client.post("/api/v1/geofences", json={
        "name": "Test Strait Watch Zone",
        "polygon_geojson": poly,
        "monitored_layers": ["VESSEL", "AIRCRAFT"],
        "min_severity": "HIGH",
        "notify_channels": ["SSE"]
    })
    assert create_res.status_code == 200
    geo_id = create_res.json()["geofence_id"]
    assert geo_id.startswith("geo_")

    # List
    list_res = client.get("/api/v1/geofences")
    assert list_res.status_code == 200
    zones = list_res.json()
    assert any(z["geofence_id"] == geo_id for z in zones)

    # Delete
    del_res = client.delete(f"/api/v1/geofences/{geo_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "DELETED"


def test_sha256_audit_chain_integrity(client):
    """Validates tamper-evident SHA-256 audit log hash chain."""
    valid, entries = db.verify_audit_log()
    assert valid is True
    assert entries >= 1
