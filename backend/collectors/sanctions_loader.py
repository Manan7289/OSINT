"""backend/collectors/sanctions_loader.py - US Treasury OFAC SDN Sanctions Loader & Indexer.

Argos Atlas-style automatic cross-referencing against OFAC SDN sanctioned vessels and aircraft.
Supports live upstream CSV download with conditional caching and offline bootstrap fallback.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error

from backend.core.database import DatabaseManager, db
from backend.core.security import CircuitBreaker

logger = logging.getLogger(__name__)

BOOTSTRAP_SDN_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "bootstrap" / "ofac_sdn_sample.json"
LIVE_OFAC_SDN_CSV = "https://www.treasury.gov/ofac/downloads/sdn.csv"


class SanctionsLoader:
    """Loads, parses, and indexes OFAC SDN sanctioned entities, vessels, and aircraft."""

    def __init__(self, database: DatabaseManager = db) -> None:
        self.db = database
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=120.0)
        self._memory_index: Dict[str, Dict[str, Any]] = {}
        self.load_sanctions()

    def count(self) -> int:
        """Returns the number of indexed sanction keys."""
        return len(self._memory_index)

    def load_sanctions(self, force_refresh: bool = False) -> int:
        """Loads sanctions records from SQLite, live upstream CSV, or bootstrap sample."""
        records: List[Dict[str, Any]] = []

        # If already populated in database and not forced, build memory cache
        if not force_refresh:
            cached = self._load_from_db()
            if cached > 0:
                return cached

        # Attempt live fetch if circuit breaker allows
        if self.circuit_breaker.allow_request("ofac_sdn"):
            try:
                req = urllib.request.Request(
                    LIVE_OFAC_SDN_CSV,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LocalOSINT/3.0"}
                )
                with urllib.request.urlopen(req, timeout=8.0) as resp:
                    if resp.status == 200:
                        content = resp.read().decode("utf-8", errors="ignore")
                        records = self._parse_ofac_csv(content)
                        self.circuit_breaker.record_success("ofac_sdn")
            except Exception as e:
                logger.warning(f"Could not fetch live OFAC SDN CSV: {e}; falling back to bootstrap dataset")
                self.circuit_breaker.record_failure("ofac_sdn")

        # Fallback to local bootstrap sample
        if not records and BOOTSTRAP_SDN_FILE.exists():
            try:
                with open(BOOTSTRAP_SDN_FILE, "r", encoding="utf-8") as f:
                    records = json.load(f)
            except Exception as e:
                logger.error(f"Error reading OFAC bootstrap sample: {e}")

        # Persist to database & update in-memory lookup
        if records:
            inserted = self.db.upsert_sanctions_batch(records)
            self._build_memory_cache(records)
            logger.info(f"Loaded {len(records)} sanctions records ({inserted} indexed).")
            return len(records)

        return 0

    def _load_from_db(self) -> int:
        records = []
        with self.db.get_connection() as conn:
            cur = conn.execute("SELECT * FROM sanctions_index LIMIT 50000;")
            for row in cur.fetchall():
                records.append(dict(row))
        if records:
            self._build_memory_cache(records)
            return len(records)
        return 0

    def _parse_ofac_csv(self, csv_text: str) -> List[Dict[str, Any]]:
        """Parses the OFAC SDN CSV format into structured vessel and aircraft records."""
        records = []
        reader = csv.reader(io.StringIO(csv_text))
        for row in reader:
            if len(row) < 12:
                continue
            ent_num = row[0].strip()
            sdn_name = row[1].strip()
            sdn_type = row[2].strip().upper()
            program = row[3].strip()
            remarks = row[11].strip() if len(row) > 11 else ""

            # Extract MMSI, IMO, ICAO24, Tail from remarks
            mmsi = None
            imo = None
            icao24 = None
            tail = None
            flag = None

            # Look for vessel identifiers in remarks
            # e.g., "Vessel Registration Identification IMO 9167289; MMSI 422039000; flag Iran"
            if "IMO " in remarks:
                parts = remarks.split("IMO ")
                if len(parts) > 1:
                    imo = parts[1].split(";")[0].split()[0].strip()
            if "MMSI " in remarks:
                parts = remarks.split("MMSI ")
                if len(parts) > 1:
                    mmsi = parts[1].split(";")[0].split()[0].strip()
            if "aircraft model" in remarks.lower() or "tail" in remarks.lower():
                sdn_type = "AIRCRAFT"

            rec = {
                "sanction_id": f"sdn_{ent_num}",
                "sdn_name": sdn_name,
                "sdn_type": sdn_type if sdn_type in ("VESSEL", "AIRCRAFT") else "ENTITY",
                "program": program,
                "mmsi": mmsi,
                "imo": imo,
                "icao24": icao24,
                "tail_number": tail,
                "flag_country": flag,
                "remarks": remarks[:500],
            }
            records.append(rec)
        return records

    def _build_memory_cache(self, records: List[Dict[str, Any]]) -> None:
        self._memory_index.clear()
        for r in records:
            if r.get("mmsi"):
                self._memory_index[f"mmsi:{str(r['mmsi']).strip()}"] = r
            if r.get("imo"):
                self._memory_index[f"imo:{str(r['imo']).strip()}"] = r
            if r.get("icao24"):
                self._memory_index[f"icao:{str(r['icao24']).strip().lower()}"] = r
            if r.get("tail_number"):
                self._memory_index[f"tail:{str(r['tail_number']).strip().upper()}"] = r
            if r.get("sdn_name"):
                self._memory_index[f"name:{str(r['sdn_name']).strip().lower()}"] = r

    def match_asset(
        self,
        mmsi: Optional[str] = None,
        imo: Optional[str] = None,
        icao24: Optional[str] = None,
        tail_number: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fast O(1) in-memory lookup followed by database fallback."""
        if mmsi and f"mmsi:{str(mmsi).strip()}" in self._memory_index:
            return self._memory_index[f"mmsi:{str(mmsi).strip()}"]
        if imo and f"imo:{str(imo).strip()}" in self._memory_index:
            return self._memory_index[f"imo:{str(imo).strip()}"]
        if icao24 and f"icao:{str(icao24).strip().lower()}" in self._memory_index:
            return self._memory_index[f"icao:{str(icao24).strip().lower()}"]
        if tail_number and f"tail:{str(tail_number).strip().upper()}" in self._memory_index:
            return self._memory_index[f"tail:{str(tail_number).strip().upper()}"]
        if name and f"name:{str(name).strip().lower()}" in self._memory_index:
            return self._memory_index[f"name:{str(name).strip().lower()}"]

        return self.db.match_sanction(
            mmsi=mmsi, imo=imo, icao24=icao24, tail_number=tail_number, name=name
        )


# Singleton
sanctions_loader = SanctionsLoader()
