"""backend/core/ontology.py - FollowTheMoney Schemas, Canonicalizers, RIOT-Lite Shared Infra, and Blocking Keys.

M02: Bitemporal SQLite WAL/FTS5/R*Tree & FollowTheMoney Storage Engine.
"""

from __future__ import annotations

from enum import Enum
import ipaddress
import re
import unicodedata
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field

try:
    import idna
except ImportError:
    idna = None


class EntityType(str, Enum):
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    DOMAIN = "DOMAIN"
    IP_ADDRESS = "IP_ADDRESS"
    EMAIL = "EMAIL"
    USERNAME = "USERNAME"
    LOCATION = "LOCATION"
    EVENT = "EVENT"
    VULNERABILITY = "VULNERABILITY"
    AIRCRAFT = "AIRCRAFT"
    VESSEL = "VESSEL"
    SATELLITE = "SATELLITE"
    CAMERA = "CAMERA"
    VISUAL_ASSET = "VISUAL_ASSET"


class EdgeType(str, Enum):
    RESOLVES_TO = "RESOLVES_TO"
    HOSTED_ON = "HOSTED_ON"
    ISSUED_TO = "ISSUED_TO"
    AFFECTS = "AFFECTS"
    EXPLOITED_BY = "EXPLOITED_BY"
    LOCATED_AT = "LOCATED_AT"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    COMMUNICATES_WITH = "COMMUNICATES_WITH"
    OWNS = "OWNS"
    MENTIONED_IN = "MENTIONED_IN"
    DERIVED_FROM = "DERIVED_FROM"
    MERGED_INTO = "MERGED_INTO"
    SANCTIONED_UNDER = "SANCTIONED_UNDER"
    PROXIMATE_TO_EVENT = "PROXIMATE_TO_EVENT"
    POTENTIAL_STS_TRANSFER = "POTENTIAL_STS_TRANSFER"
    ENTERED_GEOFENCE = "ENTERED_GEOFENCE"
    VISUALLY_SIMILAR_TO = "VISUALLY_SIMILAR_TO"
    CAPTURED_NEAR = "CAPTURED_NEAR"


class TelemetryStatus(str, Enum):
    LIVE = "LIVE"
    DELAYED = "DELAYED"
    ORBITAL_PROPAGATED = "ORBITAL_PROPAGATED"
    HISTORICAL = "HISTORICAL"
    OFFLINE_BOOTSTRAP = "OFFLINE_BOOTSTRAP"


class GeoTrackPoint(BaseModel):
    track_id: str
    entity_id: Optional[str] = None
    layer_type: str
    lat: float
    lon: float
    altitude_m: float = 0.0
    velocity_mps: float = 0.0
    heading_deg: float = 0.0
    telemetry_status: TelemetryStatus = TelemetryStatus.LIVE
    is_sanctioned: bool = False
    is_military: bool = False
    squawk: Optional[str] = None
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    observed_at: str


class SweepDelta(BaseModel):
    delta_id: str
    sweep_id: str
    entity_id: Optional[str] = None
    delta_type: str
    severity: str
    title: str
    description: str
    prev_value_json: Dict[str, Any] = Field(default_factory=dict)
    curr_value_json: Dict[str, Any] = Field(default_factory=dict)
    lat: Optional[float] = None
    lon: Optional[float] = None
    created_at: str


class SweepRun(BaseModel):
    sweep_id: str
    investigation_id: str = "default"
    started_at: str
    completed_at: Optional[str] = None
    status: str = "RUNNING"
    sources_polled: int = 0
    sources_succeeded: int = 0
    new_entities_count: int = 0
    escalated_count: int = 0
    sanction_matches_count: int = 0
    geofence_alerts_count: int = 0
    escalation_score: float = 0.0
    summary_briefing_md: str = ""


class SanctionRecord(BaseModel):
    sanction_id: str
    sdn_name: str
    sdn_type: str
    program: str
    mmsi: Optional[str] = None
    imo: Optional[str] = None
    icao24: Optional[str] = None
    tail_number: Optional[str] = None
    flag_country: Optional[str] = None
    remarks: Optional[str] = None
    updated_at: str


class GeofenceZone(BaseModel):
    geofence_id: str
    name: str
    polygon_geojson: str
    monitored_layers_json: List[str] = Field(default_factory=lambda: ["AIRCRAFT", "VESSEL", "EARTHQUAKE", "CONFLICT"])
    min_severity: str = "MEDIUM"
    notify_channels_json: List[str] = Field(default_factory=lambda: ["SSE"])
    is_active: bool = True
    created_at: str


class VisualAsset(BaseModel):
    asset_id: str
    investigation_id: str = "default"
    entity_id: Optional[str] = None
    filename: str
    sha256_hash: str
    phash_64: str
    dhash_64: str
    ahash_64: str
    width: int
    height: int
    laplacian_sharpness: float
    quality_grade: str
    faces_detected: int = 0
    bystanders_blurred: bool = True
    exif_json: Dict[str, Any] = Field(default_factory=dict)
    c2pa_json: Dict[str, Any] = Field(default_factory=dict)
    lat: Optional[float] = None
    lon: Optional[float] = None
    redacted_image_b64: Optional[str] = None
    created_at: str


class ConsentedFaceEntry(BaseModel):
    gallery_id: str
    subject_name: str
    consent_purpose: str
    consent_attestation: bool = True
    embedding_blob: bytes
    image_sha256: str
    laplacian_sharpness: float
    enrolled_at: str
    expires_at: str


class VisualAnalysisReport(BaseModel):
    asset_id: str
    filename: str
    sha256: str
    phash: str
    dhash: str
    ahash: str
    dimensions: Tuple[int, int]
    laplacian_sharpness: float
    quality_grade: str
    verification_allowed: bool
    faces_count: int
    bystanders_blurred: bool
    redacted_image_base64: Optional[str] = None
    exif_metadata: Dict[str, Any] = Field(default_factory=dict)
    c2pa_metadata: Dict[str, Any] = Field(default_factory=dict)
    coordinates: Optional[Tuple[float, float]] = None
    similar_assets: List[Dict[str, Any]] = Field(default_factory=list)


# Valid FollowTheMoney (FtM) Entity Schemas
FTM_SCHEMAS = {
    "Domain",
    "Subdomain",
    "IPv4Address",
    "IPv6Address",
    "AutonomousSystem",
    "Company",
    "Organization",
    "Person",
    "Email",
    "Vulnerability",
    "Service",
    "X509Certificate",
    "CryptoWallet",
    "Location",
    "Document",
    "NewsArticle",
    "GitHubProfile",
    "Aircraft",
    "Vessel",
    "Satellite",
    "Camera",
    "VisualAsset",
}

# RIOT-Lite: Common Shared Infrastructure that should not collapse the graph
RIOT_LITE_SHARED_ASNS = {
    "AS13335",  # Cloudflare
    "AS15169",  # Google
    "AS16509",  # Amazon AWS
    "AS8075",   # Microsoft Azure
    "AS20940",  # Akamai
    "AS54113",  # Fastly
    "AS14061",  # DigitalOcean
    "AS24940",  # Hetzner
    "AS16276",  # OVH
    "AS36351",  # SoftLayer / IBM
}

RIOT_LITE_SHARED_DOMAINS = {
    "cloudflare.com",
    "amazonaws.com",
    "azure.com",
    "google.com",
    "github.io",
    "pages.dev",
    "herokuapp.com",
    "cloudfront.net",
    "fastly.net",
    "akamai.net",
    "cdn77.org",
    "wixsite.com",
    "wordpress.com",
}

RIOT_LITE_SHARED_IPS = {
    "1.1.1.1",
    "1.0.0.1",
    "8.8.8.8",
    "8.8.4.4",
    "9.9.9.9",
    "149.112.112.112",
    "208.67.222.222",
    "208.67.220.220",
}

CORPORATE_LEGAL_SUFFIXES = [
    r"\binc(?:\.|\b)",
    r"\bincorporated\b",
    r"\bllc(?:\.|\b)",
    r"\bltd(?:\.|\b)",
    r"\blimited\b",
    r"\bgmbh\b",
    r"\bs\.?a(?:\.|\b)",
    r"\bplc(?:\.|\b)",
    r"\bco(?:\.|\b)",
    r"\bcompany\b",
    r"\bs\.?r\.?o(?:\.|\b)",
    r"\bb\.?v(?:\.|\b)",
    r"\bpvt(?:\.|\b)",
]
CORPORATE_SUFFIX_REGEX = re.compile(
    r"\s*(?:" + "|".join(CORPORATE_LEGAL_SUFFIXES) + r")\s*$", re.IGNORECASE
)


def canonicalize_entity(ftm_schema: str, raw_value: str) -> Tuple[str, str, bool]:
    """Canonicalizes raw value according to FollowTheMoney schema rules.
    
    Returns:
        (canonical_value: str, display_label: str, is_shared_infra: bool)
    """
    if ftm_schema not in FTM_SCHEMAS:
        ftm_schema = "Domain"  # fallback safe default

    val = raw_value.strip()
    is_shared = False

    if ftm_schema in ("Domain", "Subdomain"):
        val = val.lower().rstrip(".")
        if val.startswith("http://") or val.startswith("https://"):
            from urllib.parse import urlparse
            parsed = urlparse(val)
            val = (parsed.hostname or val).lower().rstrip(".")
        if idna:
            try:
                # normalize IDNA
                val = idna.encode(val).decode("ascii")
            except Exception:
                pass
        display = val
        if val in RIOT_LITE_SHARED_DOMAINS or any(val.endswith("." + d) for d in RIOT_LITE_SHARED_DOMAINS):
            is_shared = True

    elif ftm_schema in ("IPv4Address", "IPv6Address"):
        try:
            ip = ipaddress.ip_address(val)
            val = str(ip)
            display = val
            if val in RIOT_LITE_SHARED_IPS:
                is_shared = True
        except ValueError:
            display = val

    elif ftm_schema == "AutonomousSystem":
        digits = re.sub(r"[^\d]", "", val)
        val = f"AS{digits}" if digits else val.upper()
        display = val
        if val in RIOT_LITE_SHARED_ASNS:
            is_shared = True

    elif ftm_schema == "Vulnerability":
        val = val.upper().strip()
        if not val.startswith("CVE-") and re.match(r"^\d{4}-\d+$", val):
            val = f"CVE-{val}"
        display = val

    elif ftm_schema == "Email":
        val = val.lower().strip()
        display = val

    elif ftm_schema in ("Company", "Organization"):
        norm = unicodedata.normalize("NFKD", val).encode("ascii", "ignore").decode("utf-8")
        norm = norm.lower().strip()
        norm = re.sub(r"[\.,'\"\-_\(\)]", " ", norm)
        norm = CORPORATE_SUFFIX_REGEX.sub("", norm).strip()
        norm = re.sub(r"\s+", " ", norm)
        display = val.strip()
        val = norm or val.lower().strip()

    elif ftm_schema == "Person":
        norm = unicodedata.normalize("NFKD", val).encode("ascii", "ignore").decode("utf-8")
        norm = re.sub(r"\s+", " ", norm).strip().title()
        display = norm or val.strip()
        val = norm.lower() if norm else val.lower().strip()

    elif ftm_schema == "X509Certificate":
        clean = re.sub(r"[^A-Fa-f0-9]", "", val).upper()
        val = clean
        display = f"SHA256:{clean[:16]}..." if len(clean) >= 16 else clean

    elif ftm_schema == "CryptoWallet":
        val = val.strip()
        display = val

    elif ftm_schema == "Aircraft":
        clean = re.sub(r"[^A-Za-z0-9]", "", val)
        val = clean.lower()
        display = f"ICAO24:{clean.upper()}"

    elif ftm_schema == "Vessel":
        digits = re.sub(r"[^\d]", "", val)
        val = digits if digits else val.strip().lower()
        display = f"MMSI:{digits}" if digits else val.upper()

    elif ftm_schema == "Satellite":
        clean = re.sub(r"[^A-Za-z0-9_-]", "", val)
        val = clean.upper()
        display = f"NORAD:{val}"

    elif ftm_schema == "Camera":
        val = val.strip()
        display = f"CAM:{val}"

    elif ftm_schema == "VisualAsset":
        clean = re.sub(r"[^A-Fa-f0-9]", "", val).lower()
        val = clean
        display = f"IMG:{clean[:12]}"

    else:
        display = val
        val = val.lower().strip()

    return val, display, is_shared


def soundex(token: str) -> str:
    """Computes American Soundex code for phonetic blocking."""
    if not token:
        return "0000"
    token = unicodedata.normalize("NFKD", token).encode("ascii", "ignore").decode("utf-8").upper()
    token = re.sub(r"[^A-Z]", "", token)
    if not token:
        return "0000"

    first_char = token[0]
    mapping = {
        "B": "1", "F": "1", "P": "1", "V": "1",
        "C": "2", "G": "2", "J": "2", "K": "2", "Q": "2", "S": "2", "X": "2", "Z": "2",
        "D": "3", "T": "3",
        "L": "4",
        "M": "5", "N": "5",
        "R": "6",
    }
    encoded = [first_char]
    prev_code = mapping.get(first_char, "")

    for char in token[1:]:
        code = mapping.get(char, "")
        if code and code != prev_code:
            encoded.append(code)
            prev_code = code
        elif char in "AEIOUYWH":
            prev_code = ""

    result = "".join(encoded)
    return (result + "0000")[:4]


def generate_blocking_keys(ftm_schema: str, canonical_val: str) -> List[Tuple[str, str]]:
    """Generates 3-pass blocking keys for candidate pair generation:
    1. PHONETIC_SORT (Soundex or sorted token)
    2. APEX_PREFIX (Domain apex, IP subnet, or identifier prefix)
    3. MINHASH_LSH (3-gram min-shingles)
    
    Returns:
        List of (pass_type, blocking_key)
    """
    keys: List[Tuple[str, str]] = []
    if not canonical_val:
        return keys

    # Pass 1: PHONETIC_SORT
    if ftm_schema in ("Company", "Organization", "Person"):
        tokens = [t for t in re.split(r"\s+", canonical_val) if t]
        if tokens:
            snd = soundex(tokens[0])
            keys.append(("PHONETIC_SORT", f"{ftm_schema}_{snd}"))
    else:
        prefix = canonical_val[:6]
        keys.append(("PHONETIC_SORT", f"{ftm_schema}_{prefix}"))

    # Pass 2: APEX_PREFIX
    if ftm_schema in ("Domain", "Subdomain"):
        parts = canonical_val.split(".")
        apex = parts[-2] if len(parts) >= 2 else parts[0]
        keys.append(("APEX_PREFIX", f"APEX_{apex}"))
    elif ftm_schema == "IPv4Address":
        parts = canonical_val.split(".")
        subnet = ".".join(parts[:3]) if len(parts) == 4 else canonical_val
        keys.append(("APEX_PREFIX", f"SUBNET_{subnet}"))
    elif ftm_schema == "Vulnerability":
        # CVE-YYYY
        parts = canonical_val.split("-")
        yr = parts[1] if len(parts) >= 2 else "YEAR"
        keys.append(("APEX_PREFIX", f"CVE_{yr}"))
    else:
        prefix = canonical_val[:4]
        keys.append(("APEX_PREFIX", f"PRE_{prefix}"))

    # Pass 3: MINHASH_LSH (3-gram character shingles)
    s = f"^{canonical_val}$"
    shingles = [s[i : i + 3] for i in range(len(s) - 2)]
    if shingles:
        import hashlib
        # Pick top 2 minimal hash shingles as LSH buckets
        hashed_shingles = sorted([hashlib.md5(sh.encode("utf-8")).hexdigest()[:6] for sh in shingles])
        for min_h in hashed_shingles[:2]:
            keys.append(("MINHASH_LSH", f"LSH_{ftm_schema}_{min_h}"))

    return keys


def encode_geohash(lat: float, lon: float, precision: int = 8) -> str:
    """Encodes latitude and longitude into Geohash-8 bit-interleaved string."""
    base32 = "0123456789bcdefghjkmnpqrstuvwxyz"
    lat_interval = [-90.0, 90.0]
    lon_interval = [-180.0, 180.0]
    geohash: List[str] = []
    bits = [16, 8, 4, 2, 1]
    bit = 0
    ch = 0
    even = True

    while len(geohash) < precision:
        if even:
            mid = (lon_interval[0] + lon_interval[1]) / 2.0
            if lon >= mid:
                ch |= bits[bit]
                lon_interval[0] = mid
            else:
                lon_interval[1] = mid
        else:
            mid = (lat_interval[0] + lat_interval[1]) / 2.0
            if lat >= mid:
                ch |= bits[bit]
                lat_interval[0] = mid
            else:
                lat_interval[1] = mid

        even = not even
        if bit < 4:
            bit += 1
        else:
            geohash.append(base32[ch])
            bit = 0
            ch = 0

    return "".join(geohash)
