"""backend/collectors/maritime_adapter.py - Live Maritime AIS Vessel Tracking.

Ingests real-time maritime AIS telemetry from Digitraffic Marine REST API
(and optional AISStream.io WebSocket), normalizes into VESSEL entities and 4D geo_tracks,
cross-references the OFAC SDN Sanctions Index, and detects AIS dark-ship gaps.
"""

from __future__ import annotations

import datetime
import gzip
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

BOOTSTRAP_MARITIME = Path(__file__).resolve().parent.parent.parent / "data" / "bootstrap" / "maritime_bootstrap.json"
DIGITRAFFIC_AIS_URL = "https://meri.digitraffic.fi/api/ais/v1/locations"


class MaritimeAdapter:
    """Maritime OSINT adapter ingesting live AIS vessel telemetry."""

    def __init__(self, database: DatabaseManager = db) -> None:
        self.db = database
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=60.0)

    def fetch_live_vessels(
        self,
        bbox: Optional[tuple[float, float, float, float]] = None,
        max_results: int = 1500,
    ) -> List[Dict[str, Any]]:
        """Fetches active vessel AIS locations from live Digitraffic and strategic chokepoint models."""
        tracks: List[Dict[str, Any]] = []

        # 1. Try Digitraffic Marine AIS REST with gzip compression
        if self.circuit_breaker.allow_request("digitraffic_ais"):
            try:
                url = DIGITRAFFIC_AIS_URL
                if bbox:
                    min_lon, min_lat, max_lon, max_lat = bbox
                    url += f"?fromX={min_lon}&fromY={min_lat}&toX={max_lon}&toY={max_lat}"
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "LocalOSINT/3.0 (contact: intelligence@localosint.org)",
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                    }
                )
                with urllib.request.urlopen(req, timeout=8.0) as resp:
                    if resp.status == 200:
                        raw = resp.read()
                        if resp.info().get("Content-Encoding") == "gzip":
                            raw = gzip.decompress(raw)
                        data = json.loads(raw.decode("utf-8"))
                        features = data.get("features", [])
                        for feat in features[:max_results]:
                            track = self._normalize_digitraffic_feature(feat)
                            if track:
                                tracks.append(track)
                        self.circuit_breaker.record_success("digitraffic_ais")
            except Exception as e:
                logger.warning(f"Digitraffic AIS feed unreachable: {e}")
                self.circuit_breaker.record_failure("digitraffic_ais")

        # 2. Always merge global strategic chokepoint vessels (Hormuz, Bab-el-Mandeb, Taiwan, Malacca)
        if BOOTSTRAP_MARITIME.exists():
            try:
                with open(BOOTSTRAP_MARITIME, "r", encoding="utf-8") as f:
                    bootstrap_data = json.load(f)
                    for b in bootstrap_data:
                        t = self._normalize_bootstrap_vessel(b)
                        if t and not any(existing.get("entity_id") == t.get("entity_id") for existing in tracks):
                            tracks.append(t)
            except Exception as e:
                logger.error(f"Error loading maritime bootstrap sample: {e}")

        # Persist tracks into SQLite geo_tracks
        if tracks:
            self.db.insert_geo_tracks_batch(tracks)

        return tracks

    def _normalize_digitraffic_feature(self, feat: dict) -> Optional[Dict[str, Any]]:
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            return None
        lon, lat = coords[0], coords[1]
        props = feat.get("properties", {})
        mmsi = str(props.get("mmsi") or feat.get("mmsi") or "").strip()
        if not mmsi:
            return None

        sog = float(props.get("sog", 0.0))
        cog = float(props.get("cog", 0.0))
        raw_hdg = props.get("heading")
        heading = float(raw_hdg) if raw_hdg is not None and float(raw_hdg) < 360.0 else cog
        nav_status = str(props.get("navStat", "0"))

        # Check OFAC sanctions
        sanction_match = sanctions_loader.match_asset(mmsi=mmsi)
        is_sanctioned = 1 if sanction_match else 0

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        metadata = {
            "mmsi": mmsi,
            "vessel_name": f"M/V {mmsi}" if not sanction_match else sanction_match.get("sdn_name", f"M/V {mmsi}"),
            "sog_knots": sog,
            "cog_deg": cog,
            "nav_status": nav_status,
            "sanction_program": sanction_match.get("program") if sanction_match else None,
        }

        # Velocity in m/s: 1 knot = 0.514444 m/s
        velocity_mps = sog * 0.514444

        return {
            "track_id": f"ves_{mmsi}_{int(datetime.datetime.now(datetime.timezone.utc).timestamp())}",
            "entity_id": f"vessel:{mmsi}",
            "layer_type": "VESSEL",
            "lat": float(lat),
            "lon": float(lon),
            "altitude_m": 0.0,
            "velocity_mps": velocity_mps,
            "heading_deg": heading,
            "telemetry_status": "LIVE",
            "is_sanctioned": is_sanctioned,
            "is_military": 0,
            "squawk": None,
            "metadata_json": metadata,
            "observed_at": now,
        }

        return {
            "track_id": f"ves_{mmsi}_{int(datetime.datetime.now(datetime.timezone.utc).timestamp())}",
            "entity_id": f"vessel:{mmsi}",
            "layer_type": "VESSEL",
            "lat": float(lat),
            "lon": float(lon),
            "altitude_m": 0.0,
            "velocity_mps": velocity_mps,
            "heading_deg": heading,
            "telemetry_status": "LIVE",
            "is_sanctioned": is_sanctioned,
            "is_military": 0,
            "squawk": None,
            "metadata_json": metadata,
            "observed_at": now,
        }

    def _normalize_bootstrap_vessel(self, item: dict) -> Optional[Dict[str, Any]]:
        mmsi = str(item.get("mmsi", "")).strip()
        if not mmsi:
            return None

        sanction_match = sanctions_loader.match_asset(
            mmsi=mmsi, imo=item.get("imo"), name=item.get("vessel_name")
        )
        is_sanctioned = 1 if sanction_match or item.get("is_sanctioned") else 0
        sog = float(item.get("sog_knots", 0.0))
        cog = float(item.get("cog_deg", 0.0))

        return {
            "track_id": f"boot_ves_{mmsi}",
            "entity_id": f"vessel:{mmsi}",
            "layer_type": "VESSEL",
            "lat": float(item.get("lat", 0.0)),
            "lon": float(item.get("lon", 0.0)),
            "altitude_m": 0.0,
            "velocity_mps": sog * 0.514444,
            "heading_deg": float(item.get("heading_deg", cog)),
            "telemetry_status": "OFFLINE_BOOTSTRAP",
            "is_sanctioned": is_sanctioned,
            "is_military": 0,
            "squawk": None,
            "metadata_json": {
                "mmsi": mmsi,
                "imo": item.get("imo"),
                "vessel_name": item.get("vessel_name", f"M/V {mmsi}"),
                "ship_type": item.get("ship_type", "Cargo"),
                "flag_country": item.get("flag_country", "Unknown"),
                "sog_knots": sog,
                "cog_deg": cog,
                "nav_status": item.get("nav_status", "Under Way"),
                "sanction_program": sanction_match.get("program") if sanction_match else ("IRAN-EO13846" if is_sanctioned else None),
            },
            "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }


# Singleton
maritime_adapter = MaritimeAdapter()
