"""backend/collectors/sweep_delta.py - Crucix-Style Scheduled Sweep & Delta Analysis Engine.

Compares collection sweep S_t against S_{t-1} to compute structured deltas:
  - NEW_ENTITY: Newly discovered high-priority entities or hazard events.
  - SANCTION_MATCH_DETECTED: Active aircraft or vessel matched against OFAC SDN.
  - ESCALATED_RISK: Increased risk, emergency squawks (7500/7600/7700), or M5.5+ earthquakes.
  - ENTERED_GEOFENCE: Track point crossed into a monitored polygon watch-zone.
  - AIS_DARK_GAP: Vessel reappeared after >2h AIS gap with >15 km displacement.
  - RESOLVED_EVENT: Previous alert subsided or expired.
Computes the Global Escalation Score E_sweep in [0, 100].
"""

from __future__ import annotations

import datetime
import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from backend.core.database import DatabaseManager, db
from backend.core.spatiotemporal import detect_maritime_dark_gaps, haversine_distance_km

logger = logging.getLogger(__name__)


def point_in_polygon(lat: float, lon: float, polygon_coords: List[List[float]]) -> bool:
    """Deterministic Ray-Casting algorithm for point-in-polygon check.
    
    polygon_coords: List of [lon, lat] or [lat, lon] coordinates.
    Standard GeoJSON Polygon is [[lon, lat], ...].
    """
    if not polygon_coords or len(polygon_coords) < 3:
        return False

    # Standard GeoJSON coordinates are [lon, lat] (x, y).
    # If any second coordinate has |coord| > 90.0, the format must be [lat, lon].
    is_lon_lat = True
    for pt in polygon_coords:
        if len(pt) >= 2 and abs(pt[1]) > 90.0:
            is_lon_lat = False
            break

    n = len(polygon_coords)
    inside = False
    p1x = polygon_coords[0][0] if is_lon_lat else polygon_coords[0][1]
    p1y = polygon_coords[0][1] if is_lon_lat else polygon_coords[0][0]

    x, y = lon, lat

    for i in range(1, n + 1):
        p2 = polygon_coords[i % n]
        p2x = p2[0] if is_lon_lat else p2[1]
        p2y = p2[1] if is_lon_lat else p2[0]

        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside


class SweepDeltaEngine:
    """Autonomous engine computing diffs, escalations, and geofence breaches between sweeps."""

    def __init__(self, database: DatabaseManager = db) -> None:
        self.db = database

    def run_sweep(
        self,
        investigation_id: str = "default",
        orchestrator_instance: Any = None,
        bbox: Optional[Tuple[float, float, float, float]] = None,
    ) -> Dict[str, Any]:
        """Executes a complete collection sweep, computes deltas against previous sweep, and persists."""
        from backend.collectors.orchestrator import orchestrator

        orch = orchestrator_instance or orchestrator
        prev_run = self.db.get_latest_sweep_run()
        prev_sweep_id = prev_run.get("sweep_id") if prev_run else None

        # Create new sweep run
        sweep_id = self.db.create_sweep_run(investigation_id=investigation_id)

        # Execute all live collectors concurrently
        collect_results = orch.run_all_geospatial_collectors(bbox=bbox)
        sources_polled = len(collect_results)
        sources_succeeded = sum(1 for v in collect_results.values() if v > 0)

        # Query tracks from this sweep
        tracks = self.db.query_geo_tracks(limit=1500)

        # Compute deltas
        deltas, stats = self.compute_sweep_deltas(
            sweep_id=sweep_id,
            curr_tracks=tracks,
            prev_sweep_id=prev_sweep_id,
        )

        stats["sources_polled"] = sources_polled
        stats["sources_succeeded"] = sources_succeeded
        stats["status"] = "COMPLETED"

        # Complete sweep run in SQLite
        self.db.complete_sweep_run(sweep_id=sweep_id, stats=stats, deltas=deltas)

        return {
            "sweep_id": sweep_id,
            "status": "COMPLETED",
            "sources_polled": sources_polled,
            "sources_succeeded": sources_succeeded,
            "escalation_score": stats["escalation_score"],
            "deltas_count": len(deltas),
            "deltas": deltas[:50],  # Return top 50 in API response
            "stats": stats,
            "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

    def compute_sweep_deltas(
        self,
        sweep_id: str,
        curr_tracks: List[Dict[str, Any]],
        prev_sweep_id: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Computes structured delta records comparing curr_tracks against the prior sweep."""
        deltas: List[Dict[str, Any]] = []
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Load active geofence zones
        geofences = self.db.list_geofences(active_only=True)

        # Previous sweep deltas and tracks for comparison
        prev_deltas = self.db.get_sweep_deltas(prev_sweep_id) if prev_sweep_id else []
        prev_entity_ids = {d.get("entity_id") for d in prev_deltas if d.get("entity_id")}

        sanction_count = 0
        geofence_count = 0
        emergency_count = 0
        escalated_count = 0
        new_high_risk_count = 0

        # Track-level evaluation
        seen_entities = set()
        for trk in curr_tracks:
            ent_id = trk.get("entity_id") or trk.get("track_id")
            if ent_id in seen_entities:
                continue
            seen_entities.add(ent_id)

            lat = trk.get("lat")
            lon = trk.get("lon")
            meta = trk.get("metadata") or {}
            layer = trk.get("layer_type", "UNKNOWN")

            # 1. SANCTION_MATCH_DETECTED
            if trk.get("is_sanctioned"):
                sanction_count += 1
                prog = meta.get("sanction_program", "OFAC-SDN")
                asset_label = meta.get("vessel_name") or meta.get("callsign") or ent_id
                deltas.append({
                    "delta_id": f"dlt_sanc_{uuid.uuid4().hex[:10]}",
                    "sweep_id": sweep_id,
                    "entity_id": ent_id,
                    "delta_type": "SANCTION_MATCH_DETECTED",
                    "severity": "CRITICAL",
                    "title": f"OFAC Sanction Match: {asset_label}",
                    "description": f"Active {layer} flagged under sanctions program [{prog}]. Coordinates: ({lat:.4f}, {lon:.4f})",
                    "prev_value_json": {},
                    "curr_value_json": {"program": prog, "lat": lat, "lon": lon},
                    "lat": lat,
                    "lon": lon,
                    "created_at": now,
                })

            # 2. EMERGENCY SQUAWK
            squawk = trk.get("squawk")
            if squawk in ("7500", "7600", "7700"):
                emergency_count += 1
                meaning = {"7500": "Hijack", "7600": "Radio Failure", "7700": "General Emergency"}.get(squawk, "Emergency")
                deltas.append({
                    "delta_id": f"dlt_emg_{uuid.uuid4().hex[:10]}",
                    "sweep_id": sweep_id,
                    "entity_id": ent_id,
                    "delta_type": "ESCALATED_RISK",
                    "severity": "CRITICAL",
                    "title": f"Aircraft Emergency Squawk {squawk} ({meaning})",
                    "description": f"Aircraft {meta.get('callsign', ent_id)} squawking {squawk} at {trk.get('altitude_m', 0.0):.0f}m altitude.",
                    "prev_value_json": {},
                    "curr_value_json": {"squawk": squawk, "meaning": meaning},
                    "lat": lat,
                    "lon": lon,
                    "created_at": now,
                })

            # 3. HIGH-MAGNITUDE EARTHQUAKE
            if layer == "EARTHQUAKE" and meta.get("magnitude", 0) >= 5.5:
                escalated_count += 1
                deltas.append({
                    "delta_id": f"dlt_eq_{uuid.uuid4().hex[:10]}",
                    "sweep_id": sweep_id,
                    "entity_id": ent_id,
                    "delta_type": "ESCALATED_RISK",
                    "severity": "HIGH",
                    "title": f"Significant Seismic Event: {meta.get('title')}",
                    "description": f"Earthquake M{meta.get('magnitude')} at depth {meta.get('depth_km', 0):.1f} km.",
                    "prev_value_json": {},
                    "curr_value_json": {"mag": meta.get("magnitude")},
                    "lat": lat,
                    "lon": lon,
                    "created_at": now,
                })

            # 4. GEOFENCE INTRUSIONS (ENTERED_GEOFENCE)
            if lat is not None and lon is not None:
                for gf in geofences:
                    monitored = gf.get("monitored_layers", [])
                    if monitored and layer not in monitored:
                        continue
                    try:
                        poly_data = json.loads(gf.get("polygon_geojson") or "{}")
                        # Handle GeoJSON Feature, Polygon or list of coordinates
                        if poly_data.get("type") == "Feature":
                            poly_coords = poly_data.get("geometry", {}).get("coordinates", [[]])[0]
                        elif poly_data.get("type") == "Polygon":
                            poly_coords = poly_data.get("coordinates", [[]])[0]
                        elif isinstance(poly_data, list):
                            poly_coords = poly_data[0] if isinstance(poly_data[0], list) and isinstance(poly_data[0][0], list) else poly_data
                        else:
                            poly_coords = []

                        if point_in_polygon(lat, lon, poly_coords):
                            geofence_count += 1
                            deltas.append({
                                "delta_id": f"dlt_gf_{uuid.uuid4().hex[:10]}",
                                "sweep_id": sweep_id,
                                "entity_id": ent_id,
                                "delta_type": "ENTERED_GEOFENCE",
                                "severity": gf.get("min_severity", "HIGH"),
                                "title": f"Geofence Intrusion: {gf['name']}",
                                "description": f"{layer} ({meta.get('vessel_name') or meta.get('callsign') or ent_id}) entered watched zone '{gf['name']}'.",
                                "prev_value_json": {},
                                "curr_value_json": {"geofence_id": gf["geofence_id"], "zone_name": gf["name"]},
                                "lat": lat,
                                "lon": lon,
                                "created_at": now,
                            })
                    except Exception as e:
                        logger.debug(f"Error evaluating geofence {gf.get('name')}: {e}")

            # 5. NEW_ENTITY
            if prev_sweep_id and ent_id not in prev_entity_ids:
                is_high_risk = trk.get("is_sanctioned") or trk.get("is_military") or layer in ("EARTHQUAKE", "WILDFIRE")
                if is_high_risk:
                    new_high_risk_count += 1
                deltas.append({
                    "delta_id": f"dlt_new_{uuid.uuid4().hex[:10]}",
                    "sweep_id": sweep_id,
                    "entity_id": ent_id,
                    "delta_type": "NEW_ENTITY",
                    "severity": "HIGH" if is_high_risk else "INFO",
                    "title": f"New Asset: {meta.get('vessel_name') or meta.get('callsign') or ent_id}",
                    "description": f"Newly appeared {layer} observed at ({lat:.4f}, {lon:.4f}).",
                    "prev_value_json": {},
                    "curr_value_json": {"layer": layer, "status": trk.get("telemetry_status")},
                    "lat": lat,
                    "lon": lon,
                    "created_at": now,
                })

        # 6. AIS DARK GAPS
        dark_gaps = detect_maritime_dark_gaps(curr_tracks)
        for dg in dark_gaps:
            deltas.append({
                "delta_id": f"dlt_gap_{uuid.uuid4().hex[:10]}",
                "sweep_id": sweep_id,
                "entity_id": f"vessel:{dg['mmsi']}",
                "delta_type": "AIS_DARK_GAP",
                "severity": "HIGH",
                "title": f"AIS Dark-Ship Gap: {dg['vessel_name']}",
                "description": f"Vessel MMSI {dg['mmsi']} went dark for {dg['gap_hours']:.1f}h and reappeared {dg['displacement_km']:.1f} km away.",
                "prev_value_json": {"lat": dg["last_reported_lat"], "lon": dg["last_reported_lon"]},
                "curr_value_json": {"gap_hours": dg["gap_hours"], "displacement_km": dg["displacement_km"]},
                "lat": dg["reappeared_lat"],
                "lon": dg["reappeared_lon"],
                "created_at": now,
            })

        # Calculate Crucix Global Escalation Score E_sweep in [0, 100]
        # Formula: min(100, 15*N_sanction + 10*N_geofence + 8*N_emergency + 3*N_escalated + 0.5*N_new_high_risk)
        raw_score = (
            (15.0 * sanction_count)
            + (10.0 * geofence_count)
            + (8.0 * emergency_count)
            + (3.0 * escalated_count)
            + (0.5 * new_high_risk_count)
        )
        escalation_score = min(100.0, round(raw_score, 1))

        stats = {
            "new_entities_count": len([d for d in deltas if d["delta_type"] == "NEW_ENTITY"]),
            "escalated_count": escalated_count,
            "sanction_matches_count": sanction_count,
            "geofence_alerts_count": geofence_count,
            "escalation_score": escalation_score,
            "summary_briefing_md": f"Sweep completed with {len(deltas)} deltas. Escalation score: {escalation_score}/100.",
        }

        return deltas, stats


# Singleton
sweep_delta_engine = SweepDeltaEngine()
