"""tests/test_m07_graph_spatiotemporal.py - Comprehensive Unit Tests for M07.

Validates IEF Edge Weighting, Leiden Community Detection, Personalized PageRank,
Adamic-Adar Link Prediction, Haversine Spatial Clustering, and Timeline Burst Z-Scores.
"""

from __future__ import annotations

import pytest

from backend.core.database import DatabaseManager
from backend.core.graph_analytics import (
    GraphAnalyticsEngine,
    compute_adamic_adar,
    compute_ief_edge_weight,
    run_leiden_communities,
    run_power_iteration_pagerank,
)
from backend.core.spatiotemporal import (
    SpatiotemporalEngine,
    cluster_geolocations,
    detect_timeline_bursts,
    haversine_distance_km,
)


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_m07_localosint.db"
    return DatabaseManager(db_path=db_file)


def test_ief_edge_weight_dampening():
    """Test that RIOT-Lite shared infrastructure nodes receive 0.15 dampening."""
    # Standard node
    w_std = compute_ief_edge_weight(total_nodes=100, deg_v=10, is_shared_infra=False)
    # Shared infra node (e.g. Cloudflare AS13335)
    w_shared = compute_ief_edge_weight(total_nodes=100, deg_v=10, is_shared_infra=True)

    assert w_std > 0.0
    assert w_shared > 0.0
    # Shared infra weight must be exactly 0.15 of standard weight
    assert round(w_shared / w_std, 2) == 0.15


def test_leiden_community_detection():
    """Test modularity community partitioning separating distinct clusters."""
    # Two distinct triangles with a single bridge edge (A3 - B1)
    nodes = ["A1", "A2", "A3", "B1", "B2", "B3"]
    edges = [
        ("A1", "A2", 1.0), ("A2", "A3", 1.0), ("A3", "A1", 1.0),
        ("B1", "B2", 1.0), ("B2", "B3", 1.0), ("B3", "B1", 1.0),
        ("A3", "B1", 0.1),  # weak bridge
    ]

    comms = run_leiden_communities(nodes, edges)
    # A nodes should be in one community, B nodes in another
    assert comms["A1"] == comms["A2"] == comms["A3"]
    assert comms["B1"] == comms["B2"] == comms["B3"]
    assert comms["A1"] != comms["B1"]


def test_power_iteration_pagerank():
    """Test that hub nodes accumulate higher PageRank centrality."""
    nodes = ["Hub", "Spoke1", "Spoke2", "Spoke3"]
    # Spokes all point to Hub
    edges = [
        ("Spoke1", "Hub", 1.0),
        ("Spoke2", "Hub", 1.0),
        ("Spoke3", "Hub", 1.0),
    ]

    pr = run_power_iteration_pagerank(nodes, edges)
    assert pr["Hub"] > pr["Spoke1"]
    assert pr["Hub"] > pr["Spoke2"]


def test_adamic_adar_link_prediction():
    """Test Adamic-Adar missing link prediction between nodes sharing common neighbors."""
    # Node X and Node Y both connect to Z1 and Z2, but not to each other
    adj = {
        "X": {"Z1", "Z2"},
        "Y": {"Z1", "Z2"},
        "Z1": {"X", "Y"},
        "Z2": {"X", "Y"},
    }
    degrees = {"X": 2, "Y": 2, "Z1": 2, "Z2": 2}

    preds = compute_adamic_adar(adj, degrees, top_k=5)
    assert len(preds) == 2  # The two diagonal pairs in the 4-cycle: (X, Y) and (Z1, Z2)
    pair_sets = [set([p["source_id"], p["target_id"]]) for p in preds]
    assert {"X", "Y"} in pair_sets
    assert {"Z1", "Z2"} in pair_sets
    assert preds[0]["adamic_adar_score"] > 0.0
    assert preds[0]["common_neighbors_count"] == 2


def test_haversine_and_spatial_clustering():
    """Test great-circle distance and spatial clustering."""
    # London (~51.5074, -0.1278) to Paris (~48.8566, 2.3522) is approx 343 km
    dist = haversine_distance_km(51.5074, -0.1278, 48.8566, 2.3522)
    assert 340 < dist < 350

    # Test clustering: 2 points in London area, 1 point in Paris
    points = [
        {"id": "p1", "latitude": 51.50, "longitude": -0.12, "label": "Westminster"},
        {"id": "p2", "latitude": 51.52, "longitude": -0.10, "label": "City of London"},
        {"id": "p3", "latitude": 48.85, "longitude": 2.35, "label": "Paris Center"},
    ]
    clusters = cluster_geolocations(points, max_distance_km=30.0)
    assert len(clusters) == 2  # London cluster (2 pts) + Paris cluster (1 pt)
    london_cluster = [c for c in clusters if c["point_count"] == 2][0]
    assert london_cluster["radius_km"] < 10.0


def test_timeline_burst_detection():
    """Test Poisson / Gaussian Z-score detection of sudden event surges."""
    events = []
    # 5 baseline days with 1 event each
    for day in range(1, 6):
        events.append({"event_time": f"2026-05-0{day}T12:00:00Z", "title": f"Routine Log {day}"})

    # 1 burst day with 20 events
    for i in range(20):
        events.append({"event_time": "2026-05-06T14:00:00Z", "title": f"C2 Beacon Burst {i}"})

    timeline, bursts = detect_timeline_bursts(events, z_threshold=2.0)
    assert len(bursts) == 1
    assert bursts[0]["date"] == "2026-05-06"
    assert bursts[0]["burst_z_score"] >= 2.0
    assert bursts[0]["event_count"] == 20
