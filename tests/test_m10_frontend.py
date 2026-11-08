"""
Tests for Module M10 — 11-View Analyst Workstation Frontend
Validates that index.html, styles.css, and app.js are served correctly and contain all 11 required intelligence views.
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_index_html_served():
    """Verify GET / returns index.html with HTTP 200 and correct title."""
    response = client.get("/")
    assert response.status_code == 200
    assert "LocalOSINT v2.0" in response.text
    assert "<!DOCTYPE html>" in response.text


def test_static_assets_served():
    """Verify styles.css and app.js are accessible via /assets/ mount."""
    css_resp = client.get("/assets/styles.css")
    assert css_resp.status_code == 200
    assert "body" in css_resp.text
    assert "--bg-base" in css_resp.text

    js_resp = client.get("/assets/app.js")
    assert js_resp.status_code == 200
    assert "LocalOSINT v2.0" in js_resp.text
    assert "initNavigation" in js_resp.text
    assert "startGraphSimulation" in js_resp.text


def test_all_11_views_present_in_dom():
    """Verify all 11 views specified in M10 and SCREEN_BY_SCREEN_REQUIREMENTS exist in index.html."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    expected_views = [
        "view-dashboard",
        "view-collect",
        "view-entities",
        "view-graph",
        "view-resolution",
        "view-timeline",
        "view-geospatial",
        "view-provenance",
        "view-ai-reports",
        "view-tasks",
        "view-settings",
    ]
    for view_id in expected_views:
        assert f'id="{view_id}"' in html, f"Missing view section: {view_id}"


def test_core_ui_components_present():
    """Verify graph canvas, inspector, ER table, world map, and modal are present."""
    response = client.get("/")
    html = response.text

    assert 'id="graph-canvas"' in html
    assert 'id="graph-inspector"' in html
    assert 'id="table-er-candidates"' in html
    assert 'id="geo-map-canvas"' in html
    assert 'id="modal-new-workspace"' in html
    assert 'id="toast-container"' in html
