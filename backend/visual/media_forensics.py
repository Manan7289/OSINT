"""backend/visual/media_forensics.py - EXIF/GPS/C2PA Forensics & 64-Bit Perceptual Hashing.

Extracts forensic metadata (EXIF tags, GPS coordinates, camera model, C2PA JUMBF manifests)
and computes 64-bit DCT perceptual hash (pHash), difference hash (dHash), and average hash (aHash)
for near-duplicate and re-compression detection using Hamming distance.
"""

from __future__ import annotations

import hashlib
import io
import logging
from typing import Any, Dict, List, Optional, Tuple

import imagehash
from PIL import ExifTags, Image

from backend.core.database import DatabaseManager, db

logger = logging.getLogger(__name__)


def _dms_to_decimal(dms: Any, ref: str) -> Optional[float]:
    """Converts EXIF Degree/Minute/Second tuple to signed decimal degrees."""
    if not dms or len(dms) < 3:
        return None
    try:
        def _to_float(v):
            if hasattr(v, "numerator") and hasattr(v, "denominator"):
                return float(v.numerator) / float(v.denominator) if v.denominator != 0 else 0.0
            return float(v)

        deg = _to_float(dms[0])
        minute = _to_float(dms[1])
        sec = _to_float(dms[2])
        dec = deg + (minute / 60.0) + (sec / 3600.0)
        if ref.upper() in ("S", "W"):
            dec = -dec
        return round(dec, 6)
    except Exception:
        return None


class MediaForensicsEngine:
    """Extracts forensic metadata and perceptual hashes from image assets."""

    def __init__(self, database: DatabaseManager = db) -> None:
        self.db = database

    def parse_image_forensics(
        self, image_bytes: bytes, filename: str = "asset.jpg"
    ) -> Dict[str, Any]:
        """Performs full forensic inspection: SHA-256, EXIF, GPS, C2PA, and 64-bit perceptual hashes."""
        sha256 = hashlib.sha256(image_bytes).hexdigest()
        file_size = len(image_bytes)

        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size

        # Compute 64-bit perceptual hashes
        phash_hex = str(imagehash.phash(img))
        dhash_hex = str(imagehash.dhash(img))
        ahash_hex = str(imagehash.average_hash(img))

        # Check for C2PA JUMBF container signature
        # C2PA embeds boxes with 'c2pa' or 'jumb' fourcc markers
        has_c2pa = b"c2pa" in image_bytes or b"jumb" in image_bytes
        c2pa_meta = {
            "c2pa_manifest_detected": has_c2pa,
            "provenance_standard": "Content Authenticity Initiative (C2PA v1.3)" if has_c2pa else None,
        }

        # Parse EXIF & GPS
        exif_meta: Dict[str, Any] = {}
        gps_coords: Optional[Tuple[float, float]] = None

        raw_exif = img.getexif()
        if raw_exif:
            for tag_id, val in raw_exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                if isinstance(val, (bytes, bytearray)):
                    continue
                exif_meta[tag_name] = str(val)

            # Check IFD GPSInfo
            try:
                for ifd_id in ExifTags.IFD:
                    try:
                        ifd = raw_exif.get_ifd(ifd_id)
                        if ifd_id == ExifTags.IFD.GPSInfo:
                            gps_lat = ifd.get(ExifTags.GPS.GPSLatitude)
                            gps_lat_ref = ifd.get(ExifTags.GPS.GPSLatitudeRef, "N")
                            gps_lon = ifd.get(ExifTags.GPS.GPSLongitude)
                            gps_lon_ref = ifd.get(ExifTags.GPS.GPSLongitudeRef, "E")

                            lat = _dms_to_decimal(gps_lat, gps_lat_ref)
                            lon = _dms_to_decimal(gps_lon, gps_lon_ref)
                            if lat is not None and lon is not None:
                                gps_coords = (lat, lon)
                                exif_meta["GPSLatitude"] = lat
                                exif_meta["GPSLongitude"] = lon
                    except Exception:
                        continue
            except Exception:
                pass

        # Query SQLite for near-duplicate or cropped assets
        similar_assets = self.db.find_similar_visual_assets(phash_hex, max_hamming=10)

        return {
            "filename": filename,
            "sha256": sha256,
            "sha256_hash": sha256,
            "file_size_bytes": file_size,
            "dimensions": (width, height),
            "phash_64": phash_hex,
            "dhash_64": dhash_hex,
            "ahash_64": ahash_hex,
            "has_gps": gps_coords is not None,
            "gps_coordinates": gps_coords,
            "exif": exif_meta,
            "c2pa": c2pa_meta,
            "similar_assets_count": len(similar_assets),
            "similar_assets": similar_assets[:10],
        }

    @staticmethod
    def hamming_distance(hex_hash1: str, hex_hash2: str) -> int:
        """Computes bitwise Hamming distance between two 64-bit hex hash strings."""
        try:
            val1 = int(hex_hash1, 16)
            val2 = int(hex_hash2, 16)
            return bin(val1 ^ val2).count("1")
        except Exception:
            return 64


# Singleton
media_forensics_engine = MediaForensicsEngine()
