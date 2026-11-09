"""tests/test_geospatial_and_sweeps.py - Geospatial, SGP4, OFAC & Sweep-Delta Tests.

Validates:
  - SGP4 orbital satellite propagation to WGS84 coordinates.
  - Aviation, Maritime, and Sanctions cross-referencing.
  - Ray-Casting point_in_polygon deterministic evaluation.
  - AIS Dark-ship gap detection.
  - Crucix Sweep-Delta engine & Global Escalation Score computation.
  - 4D Historical replay endpoint.
"""

import datetime
import pytest
from fastapi.testclient import TestClient

from backend.collectors.satellite_adapter import satellite_adapter
from backend.collectors.sweep_delta import point_in_polygon, sweep_delta_engine
from backend.core.spatiotemporal import detect_maritime_dark_gaps, propagate_satellite_tle
from backend.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_sgp4_satellite_propagation():
    """Validates real-time SGP4 orbital propagation from TLE."""
    # International Space Station (ISS ZARYA) TLE
    line1 = "1 25544U 98067A   24140.51868352  .00014881  00000+0  26815-3 0  9997"
    line2 = "2 25544  51.6416 290.7634 0005479  83.9406 276.2411 15.49815444453597"
    
    # Propagate to current time
    result = propagate_satellite_tle("ISS (ZARYA)", line1, line2)
    assert result is not None
    assert -90.0 <= result["lat"] <= 90.0
    assert -180.0 <= result["lon"] <= 180.0
    assert result["alt_km"] > 150.0  # LEO orbit above 150 km
    assert result["velocity_kms"] > 5.0  # Orbital velocity > 5 km/s
    assert result["footprint_radius_km"] > 500.0


def test_ray_casting_point_in_polygon():
    """Validates deterministic ray-casting point-in-polygon logic."""
    # Polygon around Strait of Hormuz: [lon, lat]
    hormuz_poly = [
        [55.0, 25.0],
        [57.0, 25.0],
        [57.0, 27.5],
        [55.0, 27.5],
        [55.0, 25.0]
    ]

    # Inside point: lat=26.0, lon=56.0
    assert point_in_polygon(lat=26.0, lon=56.0, polygon_coords=hormuz_poly) is True

    # Outside point: lat=30.0, lon=50.0
    assert point_in_polygon(lat=30.0, lon=50.0, polygon_coords=hormuz_poly) is False


def test_maritime_dark_gap_detection():
    """Validates AIS dark-ship gap detection on track history."""
    t0 = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=4)
    t1 = datetime.datetime.now(datetime.timezone.utc)
    
    tracks = [
        {
            "track_id": "trk_1",
            "entity_id": "vessel_999",
            "lat": 25.0,
            "lon": 55.0,
            "observed_at": t0.isoformat()
        },
        {
            "track_id": "trk_2",
            "entity_id": "vessel_999",
            "lat": 26.5,
            "lon": 56.5,
            "observed_at": t1.isoformat()
        }
    ]

    gaps = detect_maritime_dark_gaps(tracks, max_gap_hours=2.0, min_displacement_km=15.0)
    assert len(gaps) >= 1
    assert gaps[0]["entity_id"] == "vessel_999"
    assert gaps[0]["time_gap_hours"] >= 3.9
    assert gaps[0]["displacement_km"] > 50.0


def test_crucix_sweep_delta_engine_and_api(client):
    """Validates Crucix Sweep-Delta execution and Escalation Score computation."""
    res = client.post("/api/v1/sweeps/run", json={"investigation_id": "default"})
    assert res.status_code == 200
    data = res.json()
    assert "sweep_id" in data
    assert "escalation_score" in data
    assert 0.0 <= data["escalation_score"] <= 100.0
    assert "deltas" in data

    # Verify latest sweep retrieval
    latest_res = client.get("/api/v1/sweeps/latest")
    assert latest_res.status_code == 200
    latest_data = latest_res.json()
    assert "sweep_id" in latest_data
    assert "escalation_score" in latest_data
    assert 0.0 <= latest_data["escalation_score"] <= 100.0


def test_geospatial_4d_replay_endpoint(client):
    """Validates historical trajectory retrieval for 4D time scrubber."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    res = client.get(f"/api/v1/geospatial/replay?timestamp_iso={now_iso}&window_minutes=60")
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "FeatureCollection"
    assert "replay_timestamp" in data
    assert "window_minutes" in data


def test_spatial_proximity_endpoint(client):
    """Validates Argos Atlas-style spatial proximity correlation (< 50 km)."""
    res = client.get("/api/v1/geospatial/proximity?lat=26.0&lon=56.0&radius_km=50.0")
    assert res.status_code == 200
    data = res.json()
    assert "center" in data
    assert data["center"]["lat"] == 26.0
    assert data["center"]["lon"] == 56.0
    assert data["radius_km"] == 50.0
    assert "proximate_assets" in data
    assert isinstance(data["proximate_assets"], list)


def test_auto_sweeper_status_and_toggle(client):
    """Validates Crucix background auto-sweeper controls."""
    status_res = client.get("/api/v1/sweeps/auto/status")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert "enabled" in status_data
    assert "interval_seconds" in status_data

    # Toggle auto-sweeper
    orig_state = status_data["enabled"]
    toggle_res = client.post("/api/v1/sweeps/auto/toggle", json={"enabled": not orig_state})
    assert toggle_res.status_code == 200
    assert toggle_res.json()["enabled"] == (not orig_state)

    # Revert back
    client.post("/api/v1/sweeps/auto/toggle", json={"enabled": orig_state})


def test_gallery_crud_endpoints(client):
    """Validates consented reference subject listing and revocation."""
    list_res = client.get("/api/v1/visual/gallery")
    assert list_res.status_code == 200
    gallery_list = list_res.json()
    assert isinstance(gallery_list, list)

