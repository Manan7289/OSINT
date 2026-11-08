"""backend/collectors/natural_events_adapter.py - Natural Disasters & Severe Hazards.

Ingests USGS Earthquakes (2.5+ Day GeoJSON), NASA EONET v3 (Wildfires, Volcanoes, Storms),
and NOAA National Weather Service Active Alerts into EVENT entities and 4D geo_tracks.
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

logger = logging.getLogger(__name__)

BOOTSTRAP_EVENTS = Path(__file__).resolve().parent.parent.parent / "data" / "bootstrap" / "natural_events_bootstrap.json"
USGS_EARTHQUAKES_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson"
NASA_EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=50"
NOAA_ALERTS_URL = "https://api.weather.gov/alerts/active"


class NaturalEventsAdapter:
    """Natural hazards OSINT adapter ingesting seismic, wildfire, and weather alerts."""

    def __init__(self, database: DatabaseManager = db) -> None:
        self.db = database
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=120.0)

    def fetch_live_events(self, max_results: int = 200) -> List[Dict[str, Any]]:
        """Fetches active earthquakes, wildfires, and weather alerts from live APIs or fallback."""
        tracks: List[Dict[str, Any]] = []

        # 1. USGS Earthquakes
        if self.circuit_breaker.allow_request("usgs_quakes"):
            try:
                req = urllib.request.Request(
                    USGS_EARTHQUAKES_URL,
                    headers={"User-Agent": "LocalOSINT/3.0"}
                )
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        for feat in data.get("features", [])[:max_results]:
                            t = self._normalize_usgs_quake(feat)
                            if t:
                                tracks.append(t)
                        self.circuit_breaker.record_success("usgs_quakes")
            except Exception as e:
                logger.warning(f"USGS Earthquakes feed unreachable: {e}")
                self.circuit_breaker.record_failure("usgs_quakes")

        # 2. NASA EONET Wildfires & Natural Events
        if self.circuit_breaker.allow_request("nasa_eonet"):
            try:
                req = urllib.request.Request(
                    NASA_EONET_URL,
                    headers={"User-Agent": "LocalOSINT/3.0"}
                )
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        for ev in data.get("events", [])[:50]:
                            t = self._normalize_eonet_event(ev)
                            if t:
                                tracks.append(t)
                        self.circuit_breaker.record_success("nasa_eonet")
            except Exception as e:
                logger.warning(f"NASA EONET feed unreachable: {e}")
                self.circuit_breaker.record_failure("nasa_eonet")

        # 3. Fallback to bootstrap dataset if live feeds failed or empty
        if not tracks and BOOTSTRAP_EVENTS.exists():
            try:
                with open(BOOTSTRAP_EVENTS, "r", encoding="utf-8") as f:
                    bootstrap_data = json.load(f)
                    for b in bootstrap_data:
                        t = self._normalize_bootstrap_event(b)
                        if t:
                            tracks.append(t)
            except Exception as e:
                logger.error(f"Error loading events bootstrap sample: {e}")

        # Persist tracks into SQLite geo_tracks
        if tracks:
            self.db.insert_geo_tracks_batch(tracks)

        return tracks

    def _normalize_usgs_quake(self, feat: dict) -> Optional[Dict[str, Any]]:
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            return None
        lon, lat = coords[0], coords[1]
        depth_km = coords[2] if len(coords) > 2 else 0.0

        props = feat.get("properties", {})
        mag = float(props.get("mag") or 0.0)
        title = props.get("title", f"M {mag} Earthquake")
        time_epoch_ms = props.get("time") or 0
        observed_at = datetime.datetime.fromtimestamp(
            time_epoch_ms / 1000.0, tz=datetime.timezone.utc
        ).isoformat() if time_epoch_ms else datetime.datetime.now(datetime.timezone.utc).isoformat()

        severity = "CRITICAL" if mag >= 6.5 else ("HIGH" if mag >= 5.0 else ("MEDIUM" if mag >= 4.0 else "LOW"))
        event_id = feat.get("id", f"eq_{int(lon)}_{int(lat)}")

        return {
            "track_id": f"trk_eq_{event_id}",
            "entity_id": f"event:earthquake:{event_id}",
            "layer_type": "EARTHQUAKE",
            "lat": float(lat),
            "lon": float(lon),
            "altitude_m": -depth_km * 1000.0,
            "velocity_mps": 0.0,
            "heading_deg": 0.0,
            "telemetry_status": "LIVE",
            "is_sanctioned": 0,
            "is_military": 0,
            "squawk": None,
            "metadata_json": {
                "title": title,
                "magnitude": mag,
                "depth_km": depth_km,
                "severity": severity,
                "url": props.get("url", ""),
            },
            "observed_at": observed_at,
        }

    def _normalize_eonet_event(self, ev: dict) -> Optional[Dict[str, Any]]:
        geometry = ev.get("geometry", [])
        if not geometry:
            return None
        latest_geom = geometry[-1]
        coords = latest_geom.get("coordinates", [])
        if len(coords) < 2:
            return None
        lon, lat = coords[0], coords[1]

        ev_id = ev.get("id", "")
        title = ev.get("title", "Natural Event")
        categories = ev.get("categories", [{}])
        cat_title = categories[0].get("title", "Hazard") if categories else "Hazard"
        layer_type = "WILDFIRE" if "fire" in cat_title.lower() else "WEATHER"

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return {
            "track_id": f"trk_eonet_{ev_id}",
            "entity_id": f"event:eonet:{ev_id}",
            "layer_type": layer_type,
            "lat": float(lat),
            "lon": float(lon),
            "altitude_m": 0.0,
            "velocity_mps": 0.0,
            "heading_deg": 0.0,
            "telemetry_status": "LIVE",
            "is_sanctioned": 0,
            "is_military": 0,
            "squawk": None,
            "metadata_json": {
                "title": title,
                "category": cat_title,
                "severity": "MEDIUM",
            },
            "observed_at": now,
        }

    def _normalize_bootstrap_event(self, item: dict) -> Optional[Dict[str, Any]]:
        event_id = item.get("event_id", "")
        return {
            "track_id": f"boot_ev_{event_id}",
            "entity_id": f"event:{event_id}",
            "layer_type": item.get("event_type", "EVENT"),
            "lat": float(item.get("lat", 0.0)),
            "lon": float(item.get("lon", 0.0)),
            "altitude_m": 0.0,
            "velocity_mps": 0.0,
            "heading_deg": 0.0,
            "telemetry_status": "OFFLINE_BOOTSTRAP",
            "is_sanctioned": 0,
            "is_military": 0,
            "squawk": None,
            "metadata_json": {
                "title": item.get("title", ""),
                "magnitude": item.get("magnitude"),
                "depth_km": item.get("depth_km"),
                "severity": item.get("severity", "MEDIUM"),
                "source_url": item.get("source_url", ""),
            },
            "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }


# Singleton
natural_events_adapter = NaturalEventsAdapter()
