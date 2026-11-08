"""backend/collectors/camera_adapter.py - Public Traffic & Weather Camera Aggregator.

Argos Atlas and God's Eye View-style public camera intelligence.
Aggregates official DOT (Caltrans, TxDOT, 511) live CCTV endpoints, municipal cams,
and verified international port surveillance nodes into CAMERA entities and geo_tracks.
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

BOOTSTRAP_CAMERAS = Path(__file__).resolve().parent.parent.parent / "data" / "bootstrap" / "public_cameras.json"
CALTRANS_D7_URL = "https://cwwp2.dot.ca.gov/data/d7/cctv/cctvStatusD07.json"


class CameraAdapter:
    """Public infrastructure camera aggregator."""

    def __init__(self, database: DatabaseManager = db) -> None:
        self.db = database
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=300.0)

    def fetch_cameras(
        self,
        bbox: Optional[tuple[float, float, float, float]] = None,
        max_results: int = 150,
    ) -> List[Dict[str, Any]]:
        """Fetches public cameras from DOT APIs and bootstrap registry."""
        tracks: List[Dict[str, Any]] = []

        # 1. Try Caltrans D7 JSON if circuit allows
        if self.circuit_breaker.allow_request("caltrans_cctv"):
            try:
                req = urllib.request.Request(
                    CALTRANS_D7_URL,
                    headers={"User-Agent": "LocalOSINT/3.0"}
                )
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        records = data.get("data", [])
                        for rec in records[:max_results]:
                            cctv = rec.get("cctv", {})
                            t = self._normalize_caltrans_cam(cctv)
                            if t:
                                tracks.append(t)
                        self.circuit_breaker.record_success("caltrans_cctv")
            except Exception as e:
                logger.warning(f"Caltrans CCTV feed unreachable: {e}")
                self.circuit_breaker.record_failure("caltrans_cctv")

        # 2. Add verified curated global port & municipal cameras from bootstrap
        if BOOTSTRAP_CAMERAS.exists():
            try:
                with open(BOOTSTRAP_CAMERAS, "r", encoding="utf-8") as f:
                    bootstrap_cams = json.load(f)
                    for b in bootstrap_cams:
                        t = self._normalize_bootstrap_cam(b)
                        if t:
                            tracks.append(t)
            except Exception as e:
                logger.error(f"Error loading public cameras bootstrap sample: {e}")

        # Persist tracks into SQLite geo_tracks
        if tracks:
            self.db.insert_geo_tracks_batch(tracks)

        return tracks

    def _normalize_caltrans_cam(self, cctv: dict) -> Optional[Dict[str, Any]]:
        loc = cctv.get("location", {})
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        if lat is None or lon is None:
            return None

        cam_id = f"cam_caltrans_{cctv.get('index', '0')}"
        road = loc.get("locationName", "Highway")
        image_url = cctv.get("imageData", {}).get("static", {}).get("currentImageURL")
        stream_url = cctv.get("imageData", {}).get("streamingVideoURL")

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return {
            "track_id": f"trk_{cam_id}",
            "entity_id": f"camera:{cam_id}",
            "layer_type": "CAMERA",
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
                "operator": "Caltrans District 7",
                "road_or_area": road,
                "snapshot_url": image_url,
                "stream_url": stream_url,
            },
            "observed_at": now,
        }

    def _normalize_bootstrap_cam(self, item: dict) -> Optional[Dict[str, Any]]:
        cam_id = item.get("camera_id")
        if not cam_id:
            return None

        return {
            "track_id": f"boot_{cam_id}",
            "entity_id": f"camera:{cam_id}",
            "layer_type": "CAMERA",
            "lat": float(item.get("lat", 0.0)),
            "lon": float(item.get("lon", 0.0)),
            "altitude_m": 0.0,
            "velocity_mps": 0.0,
            "heading_deg": float(item.get("heading_deg", 0.0)),
            "telemetry_status": item.get("telemetry_status", "LIVE"),
            "is_sanctioned": 0,
            "is_military": 0,
            "squawk": None,
            "metadata_json": {
                "operator": item.get("operator", "Public DOT"),
                "road_or_area": item.get("road_or_area", "Public Infrastructure"),
                "snapshot_url": item.get("snapshot_url"),
                "stream_url": item.get("stream_url"),
            },
            "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }


# Singleton
camera_adapter = CameraAdapter()
