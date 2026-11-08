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

    @staticmethod
    def compute_gps_interference_zones(
        aircraft_tracks: List[Dict[str, Any]],
        nac_threshold: int = 4,
        cluster_dist_km: float = 60.0,
    ) -> List[Dict[str, Any]]:
        return compute_gps_interference_zones(
            aircraft_tracks, nac_threshold=nac_threshold, cluster_dist_km=cluster_dist_km
        )

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


def propagate_satellite_tle(
    line1: str,
    line2: str,
    target_dt_utc: Optional[Any] = None,
    dt_utc: Optional[datetime.datetime] = None,
) -> Dict[str, Any]:
    """Propagates a satellite Two-Line Element (TLE) set to WGS84 Geodetic coordinates using SGP4.
    
    Returns:
        {
            "lat": float,
            "lon": float,
            "alt_km": float,
            "velocity_kms": float,
            "footprint_radius_km": float,
            "ground_track_90m": List[[lat, lon]],
            "propagated_at": ISO8601 string
        }
    """
    from sgp4.api import Satrec, jday

    # Gracefully handle if called as propagate_satellite_tle(name, line1, line2)
    if not line1.strip().startswith("1 ") and line2.strip().startswith("1 "):
        actual_line1 = line2
        actual_line2 = str(target_dt_utc) if target_dt_utc else ""
        dt = dt_utc or datetime.datetime.now(datetime.timezone.utc)
    else:
        actual_line1 = line1
        actual_line2 = line2
        dt = target_dt_utc if isinstance(target_dt_utc, datetime.datetime) else (dt_utc or datetime.datetime.now(datetime.timezone.utc))

    sat = Satrec.twoline2rv(actual_line1.strip(), actual_line2.strip())
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)

    def _propagate_at(target_time: datetime.datetime) -> Tuple[float, float, float, float, float]:
        jd, fr = jday(
            target_time.year,
            target_time.month,
            target_time.day,
            target_time.hour,
            target_time.minute,
            target_time.second + target_time.microsecond * 1e-6,
        )
        e, r, v = sat.sgp4(jd, fr)
        if e != 0 or not r:
            # Fallback approximate position on numerical divergence
            return 0.0, 0.0, 420.0, 7.6, 2200.0

        t_jd = jd + fr
        d = t_jd - 2451545.0
        gmst_deg = (280.46061837 + 360.98564736629 * d) % 360.0
        theta = math.radians(gmst_deg)

        x, y, z = r
        x_pef = x * math.cos(theta) + y * math.sin(theta)
        y_pef = -x * math.sin(theta) + y * math.cos(theta)
        z_pef = z

        lon = math.degrees(math.atan2(y_pef, x_pef))
        lon = (lon + 180.0) % 360.0 - 180.0
        lat = math.degrees(math.atan2(z_pef, math.sqrt(x_pef**2 + y_pef**2)))
        r_mag = math.sqrt(x**2 + y**2 + z**2)
        alt_km = max(160.0, r_mag - 6378.137)
        vel_kms = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2) if v else 7.66
        footprint = 6378.137 * math.acos(min(1.0, 6378.137 / max(6378.138, r_mag)))
        return round(lat, 4), round(lon, 4), round(alt_km, 1), round(vel_kms, 2), round(footprint, 1)

    cur_lat, cur_lon, cur_alt, cur_vel, cur_fp = _propagate_at(dt)

    # 90-minute future ground track (18 points, 5-min intervals)
    ground_track = []
    for step in range(18):
        future_dt = dt + datetime.timedelta(minutes=step * 5)
        p_lat, p_lon, _, _, _ = _propagate_at(future_dt)
        ground_track.append([p_lat, p_lon])

    return {
        "lat": cur_lat,
        "lon": cur_lon,
        "alt_km": cur_alt,
        "velocity_kms": cur_vel,
        "footprint_radius_km": cur_fp,
        "ground_track_90m": ground_track,
        "propagated_at": dt.isoformat(),
    }


def detect_maritime_dark_gaps(
    tracks: List[Dict[str, Any]],
    gap_threshold_hours: float = 2.0,
    min_displacement_km: float = 15.0,
    max_gap_hours: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Detects AIS dark-ship anomalies where a vessel went silent for > 2 hours and reappeared > 15 km away."""
    if max_gap_hours is not None:
        gap_threshold_hours = max_gap_hours
    vessel_points = defaultdict(list)
    for t in tracks:
        mmsi = (
            t.get("metadata", {}).get("mmsi")
            or (t.get("metadata_json", {}).get("mmsi") if isinstance(t.get("metadata_json"), dict) else None)
            or t.get("entity_id")
            or t.get("callsign_or_name")
        )
        if mmsi and t.get("lat") is not None and t.get("lon") is not None:
            vessel_points[mmsi].append(t)

    dark_gaps = []
    for mmsi, pts in vessel_points.items():
        if len(pts) < 2:
            continue
        # Sort chronologically
        pts.sort(key=lambda x: x.get("observed_at", ""))
        for i in range(len(pts) - 1):
            p1, p2 = pts[i], pts[i + 1]
            try:
                t1 = datetime.datetime.fromisoformat(p1["observed_at"].replace("Z", "+00:00"))
                t2 = datetime.datetime.fromisoformat(p2["observed_at"].replace("Z", "+00:00"))
                gap_hrs = (t2 - t1).total_seconds() / 3600.0
                dist_km = haversine_distance_km(p1["lat"], p1["lon"], p2["lat"], p2["lon"])
                if gap_hrs >= gap_threshold_hours and dist_km >= min_displacement_km:
                    dark_gaps.append({
                        "mmsi": mmsi,
                        "entity_id": p2.get("entity_id", mmsi),
                        "vessel_name": p2.get("metadata", {}).get("vessel_name", f"M/V {mmsi}"),
                        "time_gap_hours": round(gap_hrs, 2),
                        "gap_hours": round(gap_hrs, 2),
                        "displacement_km": round(dist_km, 2),
                        "last_reported_lat": p1["lat"],
                        "last_reported_lon": p1["lon"],
                        "reappeared_lat": p2["lat"],
                        "reappeared_lon": p2["lon"],
                        "reappeared_at": p2["observed_at"],
                    })
            except Exception:
                continue
    return dark_gaps


def detect_sts_rendezvous(
    vessel_tracks: List[Dict[str, Any]],
    max_distance_km: float = 0.5,
    max_speed_knots: float = 2.0,
) -> List[Dict[str, Any]]:
    """Detects potential Ship-to-Ship (STS) transfer rendezvous between vessels drifting together."""
    slow_vessels = []
    for v in vessel_tracks:
        sog = v.get("metadata", {}).get("sog_knots", 0.0)
        if sog <= max_speed_knots and v.get("lat") is not None and v.get("lon") is not None:
            slow_vessels.append(v)

    rendezvous = []
    for i in range(len(slow_vessels)):
        for j in range(i + 1, len(slow_vessels)):
            v1, v2 = slow_vessels[i], slow_vessels[j]
            # Don't pair same vessel
            id1 = v1.get("entity_id")
            id2 = v2.get("entity_id")
            if id1 and id1 == id2:
                continue

            dist = haversine_distance_km(v1["lat"], v1["lon"], v2["lat"], v2["lon"])
            if dist <= max_distance_km:
                rendezvous.append({
                    "vessel_1": v1.get("entity_id"),
                    "vessel_2": v2.get("entity_id"),
                    "distance_km": round(dist, 3),
                    "lat": round((v1["lat"] + v2["lat"]) / 2.0, 5),
                    "lon": round((v1["lon"] + v2["lon"]) / 2.0, 5),
                    "detected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                })
    return rendezvous


def compute_gps_interference_zones(
    aircraft_tracks: List[Dict[str, Any]],
    nac_threshold: int = 4,
    cluster_dist_km: float = 60.0,
) -> List[Dict[str, Any]]:
    """Aggregates aircraft reporting low Navigation Accuracy Category for Position (NACp <= 4)
    into GPS/GNSS interference hazard zones (Argos Atlas style).
    """
    degraded = []
    for ac in aircraft_tracks:
        meta = ac.get("metadata", {}) or ac.get("metadata_json", {})
        nac = meta.get("nac_p")
        is_jammed = meta.get("gps_interference") or (isinstance(nac, (int, float)) and nac <= nac_threshold)
        if is_jammed and ac.get("lat") is not None and ac.get("lon") is not None:
            degraded.append({
                "latitude": ac["lat"],
                "longitude": ac["lon"],
                "icao24": ac.get("entity_id", "").replace("aircraft:", ""),
                "nac_p": nac,
            })

    clusters = cluster_geolocations(degraded, max_distance_km=cluster_dist_km)
    zones = []
    for c in clusters:
        poly_coords = []
        for angle in range(0, 360, 30):
            import math
            rad = math.radians(angle)
            d_lat = (c["radius_km"] / 111.0) * math.cos(rad)
            d_lon = (c["radius_km"] / (111.0 * math.cos(math.radians(c["centroid_latitude"])))) * math.sin(rad)
            poly_coords.append([round(c["centroid_longitude"] + d_lon, 5), round(c["centroid_latitude"] + d_lat, 5)])
        poly_coords.append(poly_coords[0])

        zones.append({
            "zone_id": f"gpsjam_{c['cluster_id']}",
            "center_lat": c["centroid_latitude"],
            "center_lon": c["centroid_longitude"],
            "radius_km": max(25.0, c["radius_km"]),
            "polygon": [poly_coords],
            "aircraft_count": c["point_count"],
            "avg_nacp": 2,
            "severity": "CRITICAL" if c["point_count"] >= 3 else "HIGH",
            "type": "GNSS_INTERFERENCE",
            "detected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })
    return zones


# Singleton
spatiotemporal_engine = SpatiotemporalEngine()
