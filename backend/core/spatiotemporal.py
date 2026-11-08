"""backend/core/spatiotemporal.py - Haversine Spatial Clustering & Kleinberg / Poisson Burst Z-Scores.

M07: Graph Analytics (Leiden, IEF-PageRank, Adamic-Adar) & Spatiotemporal/Burst Engine.
"""

from __future__ import annotations

import datetime
import math
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from backend.core.database import DatabaseManager, db


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two GPS coordinates in kilometers."""
    r = 6371.0  # Earth mean radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 3)


def cluster_geolocations(
    points: List[Dict[str, Any]], max_distance_km: float = 50.0
) -> List[Dict[str, Any]]:
    """Hierarchical density-based spatial clustering for geospatial coordinates.
    
    Returns:
        List of cluster objects with centroid_lat, centroid_lon, radius_km, and member entities.
    """
    if not points:
        return []

    clusters: List[List[Dict[str, Any]]] = []

    for pt in points:
        lat = pt.get("latitude")
        lon = pt.get("longitude")
        if lat is None or lon is None:
            continue

        assigned = False
        for c in clusters:
            # Check distance to cluster centroid
            c_lat = sum(p["latitude"] for p in c) / len(c)
            c_lon = sum(p["longitude"] for p in c) / len(c)
            dist = haversine_distance_km(lat, lon, c_lat, c_lon)
            if dist <= max_distance_km:
                c.append(pt)
                assigned = True
                break

        if not assigned:
            clusters.append([pt])

    results: List[Dict[str, Any]] = []
    for idx, c in enumerate(clusters):
        c_lat = sum(p["latitude"] for p in c) / len(c)
        c_lon = sum(p["longitude"] for p in c) / len(c)
        # Compute maximum distance from centroid as radius
        radius = max(haversine_distance_km(c_lat, c_lon, p["latitude"], p["longitude"]) for p in c)
        results.append({
            "cluster_id": idx + 1,
            "centroid_latitude": round(c_lat, 6),
            "centroid_longitude": round(c_lon, 6),
            "radius_km": round(max(0.5, radius), 2),
            "point_count": len(c),
            "points": c,
        })

    return results


def detect_timeline_bursts(
    events: List[Dict[str, Any]], z_threshold: float = 2.0
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Computes Poisson / Gaussian Z-score over chronological event buckets to detect intelligence spikes.
    
    Returns:
        (bucketed_timeline: List[Dict], burst_windows: List[Dict])
    """
    if not events:
        return [], []

    # Sort events by timestamp
    valid_events = []
    for ev in events:
        ts = ev.get("event_time") or ev.get("observed_at") or ev.get("first_seen_at")
        if ts:
            valid_events.append(dict(ev, _parsed_ts=ts))

    if not valid_events:
        return [], []

    valid_events.sort(key=lambda x: x["_parsed_ts"])

    # Bucket events by date (YYYY-MM-DD)
    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for ev in valid_events:
        day_key = str(ev["_parsed_ts"])[:10]
        buckets[day_key].append(ev)

    sorted_days = sorted(buckets.keys())
    counts = np.array([len(buckets[day]) for day in sorted_days], dtype=np.float64)

    mean_count = float(np.mean(counts))
    std_count = float(np.std(counts))
    denom = max(1.0, std_count)

    timeline_series = []
    burst_windows = []

    for idx, day in enumerate(sorted_days):
        cnt = int(counts[idx])
        z_score = round(float((cnt - mean_count) / denom), 2)
        is_burst = z_score >= z_threshold

        entry = {
            "date": day,
            "event_count": cnt,
            "burst_z_score": z_score,
            "is_burst": is_burst,
            "events": buckets[day],
        }
        timeline_series.append(entry)

        if is_burst:
            burst_windows.append({
                "date": day,
                "event_count": cnt,
                "burst_z_score": z_score,
                "sample_event": buckets[day][0].get("title", ""),
            })

    return timeline_series, burst_windows


class SpatiotemporalEngine:
    """Spatiotemporal analytics facade."""

    def __init__(self, database: DatabaseManager = db) -> None:
        self.db = database

    def get_geospatial_clusters(self, workspace_id: str) -> Dict[str, Any]:
        """Fetches all entities with coordinates and clusters them via Haversine."""
        entities = self.db.list_entities(workspace_id=workspace_id, limit=5000)
        geolocated = []
        for e in entities:
            if e.get("latitude") is not None and e.get("longitude") is not None:
                geolocated.append({
                    "id": e["id"],
                    "label": e["display_label"],
                    "schema": e["ftm_schema"],
                    "latitude": e["latitude"],
                    "longitude": e["longitude"],
                    "location_label": e.get("location_label", ""),
                })

        clusters = cluster_geolocations(geolocated)
        return {
            "workspace_id": workspace_id,
            "total_geolocated_points": len(geolocated),
            "cluster_count": len(clusters),
            "clusters": clusters,
        }

    def get_timeline_burst_analysis(self, workspace_id: str) -> Dict[str, Any]:
        """Fetches timeline events and computes burst Z-scores."""
        events: List[Dict[str, Any]] = []
        with self.db.get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM timeline_events WHERE workspace_id = ? ORDER BY event_time ASC;",
                (workspace_id,),
            )
            events = [dict(r) for r in cur.fetchall()]

        # If no timeline_events exist, fallback to evidence observation dates
        if not events:
            evs = self.db.list_evidence(workspace_id=workspace_id, limit=1000)
            events = [{"event_time": e["observed_at"], "title": e["title"], "source": e["source_name"]} for e in evs]

        series, bursts = detect_timeline_bursts(events)
        return {
            "workspace_id": workspace_id,
            "total_events": len(events),
            "burst_window_count": len(bursts),
            "timeline": series,
            "burst_windows": bursts,
        }


# Singleton
spatiotemporal_engine = SpatiotemporalEngine()
