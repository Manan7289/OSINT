"""backend/collectors/aviation_adapter.py - Live Commercial & Military Aviation Tracking.

Ingests real-time flight vectors from OpenSky Network and ADSB.lol (/v2/mil),
normalizes into AIRCRAFT entities and 4D geo_tracks, detects emergency squawks
(7500, 7600, 7700), identifies low-NACp GPS interference zones, and cross-references
the US Treasury OFAC SDN Sanctions Index.
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error

from backend.collectors.sanctions_loader import sanctions_loader
from backend.core.database import DatabaseManager, db
from backend.core.security import CircuitBreaker

logger = logging.getLogger(__name__)

BOOTSTRAP_AVIATION = Path(__file__).resolve().parent.parent.parent / "data" / "bootstrap" / "aviation_bootstrap.json"
OPENSKY_URL = "https://opensky-network.org/api/states/all"
ADSBLOL_MIL_URL = "https://api.adsb.lol/v2/mil"


class AviationAdapter:
    """Aviation OSINT adapter ingesting commercial and military flight telemetry."""

    def __init__(self, database: DatabaseManager = db) -> None:
        self.db = database
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=60.0)

    def fetch_live_flights(
        self,
        bbox: Optional[tuple[float, float, float, float]] = None,
        include_mil: bool = True,
        max_results: int = 500,
    ) -> List[Dict[str, Any]]:
        """Fetches active flights from live APIs (or fallback bootstrap) and cross-references sanctions."""
        tracks: List[Dict[str, Any]] = []

        # 1. Try ADSB.lol military flights first
        if include_mil and self.circuit_breaker.allow_request("adsb_lol_mil"):
            try:
                req = urllib.request.Request(
                    ADSBLOL_MIL_URL,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LocalOSINT/3.0"}
                )
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        ac_list = data.get("ac", [])
                        for ac in ac_list[:max_results]:
                            track = self._normalize_adsblol_flight(ac)
                            if track:
                                tracks.append(track)
                        self.circuit_breaker.record_success("adsb_lol_mil")
            except Exception as e:
                logger.warning(f"ADSB.lol military feed unreachable: {e}")
                self.circuit_breaker.record_failure("adsb_lol_mil")

        # 2. Try OpenSky Network for general aviation
        if len(tracks) < max_results and self.circuit_breaker.allow_request("opensky"):
            try:
                url = OPENSKY_URL
                if bbox:
                    min_lon, min_lat, max_lon, max_lat = bbox
                    url += f"?lamin={min_lat}&lomin={min_lon}&lamax={max_lat}&lomax={max_lon}"
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LocalOSINT/3.0"}
                )
                with urllib.request.urlopen(req, timeout=6.0) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        states = data.get("states", []) or []
                        for s in states[:max_results - len(tracks)]:
                            track = self._normalize_opensky_state(s)
                            if track:
                                tracks.append(track)
                        self.circuit_breaker.record_success("opensky")
            except Exception as e:
                logger.warning(f"OpenSky Network feed unreachable: {e}")
                self.circuit_breaker.record_failure("opensky")

        # 3. Fallback to bootstrap dataset if live feeds failed or returned zero
        if not tracks and BOOTSTRAP_AVIATION.exists():
            try:
                with open(BOOTSTRAP_AVIATION, "r", encoding="utf-8") as f:
                    bootstrap_data = json.load(f)
                    for b in bootstrap_data:
                        t = self._normalize_bootstrap_flight(b)
                        if t:
                            tracks.append(t)
            except Exception as e:
                logger.error(f"Error loading aviation bootstrap sample: {e}")

        # Persist tracks into SQLite geo_tracks
        if tracks:
            self.db.insert_geo_tracks_batch(tracks)

        return tracks

    def _normalize_opensky_state(self, state: list) -> Optional[Dict[str, Any]]:
        """OpenSky state vector schema:
        [0] icao24, [1] callsign, [2] origin_country, [3] time_position,
        [4] last_contact, [5] longitude, [6] latitude, [7] baro_altitude,
        [8] on_ground, [9] velocity, [10] true_track, [11] vertical_rate,
        [12] sensors, [13] geo_altitude, [14] squawk, [15] spi, [16] position_source
        """
        if len(state) < 15:
            return None
        icao24 = str(state[0]).strip().lower()
        if not icao24:
            return None

        lon = state[5]
        lat = state[6]
        if lon is None or lat is None:
            return None

        callsign = str(state[1]).strip() if state[1] else ""
        squawk = str(state[14]).strip() if state[14] else None
        baro_alt = float(state[7]) if state[7] is not None else 0.0
        velocity = float(state[9]) if state[9] is not None else 0.0
        heading = float(state[10]) if state[10] is not None else 0.0

        # Check OFAC sanctions
        sanction_match = sanctions_loader.match_asset(icao24=icao24, tail_number=callsign)
        is_sanctioned = 1 if sanction_match else 0

        # Squawk emergency detection
        is_emergency = squawk in ("7500", "7600", "7700")

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        metadata = {
            "origin_country": state[2] or "",
            "callsign": callsign,
            "on_ground": bool(state[8]),
            "is_emergency": is_emergency,
            "sanction_program": sanction_match.get("program") if sanction_match else None,
            "nac_p": 10,
        }

        return {
            "track_id": f"air_{icao24}_{int(datetime.datetime.now(datetime.timezone.utc).timestamp())}",
            "entity_id": f"aircraft:{icao24}",
            "layer_type": "AIRCRAFT",
            "lat": float(lat),
            "lon": float(lon),
            "altitude_m": baro_alt,
            "velocity_mps": velocity,
            "heading_deg": heading,
            "telemetry_status": "LIVE",
            "is_sanctioned": is_sanctioned,
            "is_military": 0,
            "squawk": squawk,
            "metadata_json": metadata,
            "observed_at": now,
        }

    def _normalize_adsblol_flight(self, ac: dict) -> Optional[Dict[str, Any]]:
        icao24 = str(ac.get("hex", "")).strip().lower()
        if not icao24:
            return None

        lat = ac.get("lat")
        lon = ac.get("lon")
        if lat is None or lon is None:
            return None

        callsign = str(ac.get("flight", "")).strip()
        squawk = str(ac.get("squawk", "")).strip() or None
        alt_baro = ac.get("alt_baro")
        altitude_m = (float(alt_baro) * 0.3048) if isinstance(alt_baro, (int, float)) else 0.0
        gs = ac.get("gs")
        velocity_mps = (float(gs) * 0.514444) if isinstance(gs, (int, float)) else 0.0
        track = float(ac.get("track", 0.0))
        nac_p = ac.get("nac_p", 10)

        sanction_match = sanctions_loader.match_asset(icao24=icao24, tail_number=callsign)
        is_sanctioned = 1 if sanction_match else 0
        is_emergency = squawk in ("7500", "7600", "7700")

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        metadata = {
            "callsign": callsign,
            "t": ac.get("t", ""),
            "is_military": True,
            "is_emergency": is_emergency,
            "nac_p": nac_p,
            "gps_interference": nac_p <= 4 if isinstance(nac_p, int) else False,
            "sanction_program": sanction_match.get("program") if sanction_match else None,
        }

        return {
            "track_id": f"mil_{icao24}_{int(datetime.datetime.now(datetime.timezone.utc).timestamp())}",
            "entity_id": f"aircraft:{icao24}",
            "layer_type": "AIRCRAFT",
            "lat": float(lat),
            "lon": float(lon),
            "altitude_m": altitude_m,
            "velocity_mps": velocity_mps,
            "heading_deg": track,
            "telemetry_status": "LIVE",
            "is_sanctioned": is_sanctioned,
            "is_military": 1,
            "squawk": squawk,
            "metadata_json": metadata,
            "observed_at": now,
        }

    def _normalize_bootstrap_flight(self, item: dict) -> Optional[Dict[str, Any]]:
        icao24 = str(item.get("icao24", "")).strip().lower()
        if not icao24:
            return None

        sanction_match = sanctions_loader.match_asset(icao24=icao24, tail_number=item.get("callsign"))
        is_sanctioned = 1 if sanction_match or item.get("is_sanctioned") else 0
        squawk = item.get("squawk")

        return {
            "track_id": f"boot_air_{icao24}",
            "entity_id": f"aircraft:{icao24}",
            "layer_type": "AIRCRAFT",
            "lat": float(item.get("lat", 0.0)),
            "lon": float(item.get("lon", 0.0)),
            "altitude_m": float(item.get("baro_altitude_m", 0.0)),
            "velocity_mps": float(item.get("velocity_mps", 0.0)),
            "heading_deg": float(item.get("true_track_deg", 0.0)),
            "telemetry_status": "OFFLINE_BOOTSTRAP",
            "is_sanctioned": is_sanctioned,
            "is_military": 1 if item.get("is_military") else 0,
            "squawk": squawk,
            "metadata_json": {
                "callsign": item.get("callsign", ""),
                "origin_country": item.get("origin_country", ""),
                "nac_p": item.get("nac_p", 10),
                "is_emergency": squawk in ("7500", "7600", "7700"),
                "sanction_program": sanction_match.get("program") if sanction_match else None,
            },
            "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }


# Singleton
aviation_adapter = AviationAdapter()
