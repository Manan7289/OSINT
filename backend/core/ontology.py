"""backend/core/ontology.py - FollowTheMoney Schemas, Canonicalizers, RIOT-Lite Shared Infra, and Blocking Keys.

M02: Bitemporal SQLite WAL/FTS5/R*Tree & FollowTheMoney Storage Engine.
"""

from __future__ import annotations

import ipaddress
import re
import unicodedata
from typing import List, Set, Tuple

try:
    import idna
except ImportError:
    idna = None

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
    r"\bcorp(?:\.|\b)",
    r"\bcorporation\b",
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
