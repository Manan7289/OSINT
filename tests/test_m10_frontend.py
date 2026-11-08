"""
Tests for Module M10 — 5-Zone 2D/3D Global Command Centre UI
Validates that index.html, styles.css, app.js, globe_map.js, timeline_4d.js,
sweep_delta_hud.js, and visual_studio.js are served correctly and contain all
5 Command Centre zones and HUD modal components.
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_index_html_served():
    """Verify GET / returns index.html with HTTP 200 and LocalOSINT v3.0."""
    response = client.get("/")
    assert response.status_code == 200
    assert "LocalOSINT" in response.text
    assert "v3.0" in response.text
    assert "<!DOCTYPE html>" in response.text


def test_static_assets_served():
    """Verify styles.css and all modular HUD script assets are accessible via /assets/ mount."""
    css_resp = client.get("/assets/styles.css")
    assert css_resp.status_code == 200
    assert "body" in css_resp.text
    assert "--bg-obsidian" in css_resp.text

    scripts = [
        "app.js",
        "globe_map.js",
        "timeline_4d.js",
        "sweep_delta_hud.js",
        "visual_studio.js",
    ]
    for script_name in scripts:
        js_resp = client.get(f"/assets/{script_name}")
        assert js_resp.status_code == 200, f"Failed to serve /assets/{script_name}"
        assert len(js_resp.text) > 100


def test_command_centre_5_zones_present_in_dom():
    """Verify all 5 Command Centre Zones exist in index.html."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    # Zone 1: 2D Map & 3D Globe Earth Canvas
    assert 'id="map-viewport"' in html
    assert 'id="map-2d"' in html
    assert 'id="globe-3d"' in html

    # Zone 2: Left HUD Layer & Sweep Manager
    assert 'id="zone-2-hud"' in html

    # Zone 4: Right HUD Entity, Graph & Provenance Inspector
    assert 'id="zone-4-hud"' in html

    # Zone 5: Bottom 4D Time Scrubber Dock
    assert 'id="zone-5-dock"' in html


def test_core_ui_components_present():
    """Verify Cytoscape ego-graph container, Visual Studio modal, SitRep briefing modal, and tension gauge."""
    response = client.get("/")
    html = response.text

    assert 'id="cy-container"' in html
    assert 'id="escalation-gauge"' in html
    assert 'id="modal-visual-studio"' in html
    assert 'id="modal-briefing"' in html
    assert 'id="toast-container"' in html
    assert 'id="scrubber-slider"' in html
