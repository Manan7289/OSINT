"""backend/collectors/satellite_adapter.py - Orbital Mechanics & SGP4 Satellite Tracking.

Ingests CelesTrak GP/TLE Two-Line Element sets and propagates real-time WGS84
coordinates, ground nadir sub-satellite points, sensor footprint horizon radiuses,
and 90-minute future orbital tracks via SGP4 (sgp4.api.Satrec).
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error

from backend.core.database import DatabaseManager, db
from backend.core.security import CircuitBreaker
from backend.core.spatiotemporal import propagate_satellite_tle

logger = logging.getLogger(__name__)

BOOTSTRAP_SATELLITES = Path(__file__).resolve().parent.parent.parent / "data" / "bootstrap" / "satellites_bootstrap.json"
CELESTRAK_GP_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=json"


class SatelliteAdapter:
    """Satellite OSINT adapter propagating real-time orbits via SGP4."""

    def __init__(self, database: DatabaseManager = db) -> None:
        self.db = database
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=300.0)
        self._cached_tle_records: List[Dict[str, Any]] = []

    def fetch_live_satellites(
        self,
        target_dt_utc: Optional[datetime.datetime] = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Propagates satellites to the given UTC timestamp (defaults to current time)."""
        dt = target_dt_utc or datetime.datetime.now(datetime.timezone.utc)
        raw_satellites: List[Dict[str, Any]] = []

        # 1. Use memory cache if populated
        if self._cached_tle_records:
            raw_satellites = self._cached_tle_records

        # 2. Try CelesTrak if circuit allows and no memory cache
        if not raw_satellites and self.circuit_breaker.allow_request("celestrak"):
            try:
                req = urllib.request.Request(
                    CELESTRAK_GP_URL,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LocalOSINT/3.0"}
                )
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        for item in data[:max_results]:
                            norad_id = str(item.get("NORAD_CAT_ID", ""))
                            sat_name = str(item.get("OBJECT_NAME", f"SAT-{norad_id}"))
                            line1 = item.get("TLE_LINE1")
                            line2 = item.get("TLE_LINE2")
                            if line1 and line2:
                                raw_satellites.append({
                                    "norad_id": norad_id,
                                    "sat_name": sat_name,
                                    "orbit_regime": item.get("ORBIT_REGIME", "LEO"),
                                    "line1": line1,
                                    "line2": line2,
                                })
                        if raw_satellites:
                            self._cached_tle_records = raw_satellites
                            self.circuit_breaker.record_success("celestrak")
            except Exception as e:
                logger.warning(f"CelesTrak feed unreachable: {e}")
                self.circuit_breaker.record_failure("celestrak")

        # 3. Fallback to bootstrap dataset
        if not raw_satellites and BOOTSTRAP_SATELLITES.exists():
            try:
                with open(BOOTSTRAP_SATELLITES, "r", encoding="utf-8") as f:
                    raw_satellites = json.load(f)
                    self._cached_tle_records = raw_satellites
            except Exception as e:
                logger.error(f"Error loading satellite bootstrap sample: {e}")

        # 4. Propagate each satellite via SGP4
        tracks: List[Dict[str, Any]] = []
        for sat in raw_satellites[:max_results]:
            norad_id = sat.get("norad_id")
            line1 = sat.get("line1")
            line2 = sat.get("line2")
            if not norad_id or not line1 or not line2:
                continue

            try:
                prop = propagate_satellite_tle(line1, line2, target_dt_utc=dt)
                track = {
                    "track_id": f"sat_{norad_id}_{int(dt.timestamp())}",
                    "entity_id": f"satellite:{norad_id}",
                    "layer_type": "SATELLITE",
                    "lat": prop["lat"],
                    "lon": prop["lon"],
                    "altitude_m": prop["alt_km"] * 1000.0,
                    "velocity_mps": prop["velocity_kms"] * 1000.0,
                    "heading_deg": 0.0,
                    "telemetry_status": "ORBITAL_PROPAGATED",
                    "is_sanctioned": 0,
                    "is_military": 1 if "NRO" in sat.get("sat_name", "") or "USA-" in sat.get("sat_name", "") else 0,
                    "squawk": None,
                    "metadata_json": {
                        "norad_id": norad_id,
                        "sat_name": sat.get("sat_name", f"SAT-{norad_id}"),
                        "orbit_regime": sat.get("orbit_regime", "LEO"),
                        "footprint_radius_km": prop["footprint_radius_km"],
                        "ground_track_90m": prop["ground_track_90m"],
                    },
                    "observed_at": dt.isoformat(),
                }
                tracks.append(track)
            except Exception as e:
                logger.debug(f"Failed to propagate satellite {norad_id}: {e}")

        # Persist tracks into SQLite geo_tracks
        if tracks:
            self.db.insert_geo_tracks_batch(tracks)

        return tracks


# Singleton
satellite_adapter = SatelliteAdapter()
