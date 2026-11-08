"""backend/nlp/extractor.py - Defanging, Regex/Aho-Corasick IOC Extraction, Shannon Entropy, SimHash-64 & Tier-2 NER.

M04: Two-Tier Hybrid NLP Extractor (Defang/Regex + ONNX GLiNER) & File Forensics.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Set, Tuple

# Precompiled Regex Patterns for High-Performance Extraction
PATTERNS = {
    "IPv4Address": re.compile(
        r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
    ),
    "Email": re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}\b"
    ),
    "Vulnerability": re.compile(
        r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE
    ),
    "AutonomousSystem": re.compile(
        r"\bAS\d{1,6}\b", re.IGNORECASE
    ),
    "CryptoWallet_BTC": re.compile(
        r"\b(?:[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[ac-hj-np-z02-9]{11,71})\b"
    ),
    "CryptoWallet_ETH": re.compile(
        r"\b0x[a-fA-F0-9]{40}\b"
    ),
    "MD5": re.compile(
        r"\b[a-fA-F0-9]{32}\b"
    ),
    "SHA1": re.compile(
        r"\b[a-fA-F0-9]{40}\b"
    ),
    "SHA256": re.compile(
        r"\b[a-fA-F0-9]{64}\b"
    ),
    "URL": re.compile(
        r"https?://[^\s<>'\"{}|\\^`]+", re.IGNORECASE
    ),
    "Domain": re.compile(
        r"\b(?!(?:https?|ftp)://)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}\b",
        re.IGNORECASE,
    ),
}

# Common TLDs to filter false positive domains
COMMON_TLDS = {
    "com", "org", "net", "io", "gov", "edu", "mil", "co", "uk", "de", "ru", "cn", "info",
    "biz", "me", "cc", "tv", "xyz", "cloud", "ai", "app", "dev", "top", "online", "site",
}


def refang(text: str) -> str:
    """Normalizes defanged indicators into valid network indicators.
    
    Examples:
      - hxxp:// -> http://
      - hxxps:// -> https://
      - 185.220.101[.]34 -> 185.220.101.34
      - c2[.]example(.)com -> c2.example.com
      - admin[@]domain[.]com -> admin@domain.com
      - 8080[:]tcp -> 8080:tcp
    """
    if not text:
        return ""

    out = text
    # Protocols
    out = re.sub(r"\bh[xX]{2}ps?://", lambda m: "https://" if "s" in m.group(0).lower() else "http://", out)
    # Defanged dots
    out = re.sub(r"\[\.\]|\(\.\)|\{\.\}", ".", out)
    # Defanged at
    out = re.sub(r"\[@\]|\(@\)|\{@\}", "@", out)
    # Defanged colons
    out = re.sub(r"\[:\]|\(:\)|\{:\}", ":", out)
    # Stray backslashes
    out = out.replace(r"\.", ".")
    return out


def defang(text: str) -> str:
    """Defangs indicators for safe sharing/storage in markdown or logs."""
    if not text:
        return ""
    out = text.replace("http://", "hxxp://").replace("https://", "hxxps://")
    out = out.replace(".", "[.]").replace("@", "[@]")
    return out


def shannon_entropy(token: str) -> float:
    """Calculates Shannon entropy in bits per character.
    
    Formula: H(s) = - sum( p(c) * log2(p(c)) )
    """
    if not token:
        return 0.0
    length = len(token)
    counts = Counter(token)
    entropy = 0.0
    for count in counts.values():
        p = count / length
        entropy -= p * math.log2(p)
    return round(entropy, 4)


def is_dga_domain(domain: str, threshold: float = 3.8) -> Tuple[bool, float]:
    """Detects Domain Generation Algorithm (DGA) hostnames using Shannon entropy.
    
    Returns:
        (is_dga: bool, entropy_score: float)
    """
    clean = domain.lower().strip()
    parts = clean.split(".")
    # Examine apex/SLD name (e.g. 'xk9872jsdfh' in 'xk9872jsdfh.com')
    token = parts[-2] if len(parts) >= 2 else parts[0]
    # Remove hyphens or digits if analyzing character entropy
    score = shannon_entropy(token)
    # Short tokens (<7 chars) produce high entropy naturally; require length >= 8
    is_dga = score >= threshold and len(token) >= 8
    return is_dga, score


def compute_simhash_64(text: str) -> str:
    """Generates a 64-bit SimHash hex string for near-duplicate text detection."""
    if not text or not text.strip():
        return "0000000000000000"

    import hashlib
    # Split into words and word-level bigrams for robust semantic SimHash
    words = re.findall(r"\w+", text.lower())
    if not words:
        return "0000000000000000"

    features = words + [f"{words[i]}_{words[i+1]}" for i in range(len(words) - 1)]
    v = [0] * 64

    for feat in features:
        h = int(hashlib.md5(feat.encode("utf-8")).hexdigest()[:16], 16)
        for i in range(64):
            bit = (h >> i) & 1
            if bit == 1:
                v[i] += 1
            else:
                v[i] -= 1

    fingerprint = 0
    for i in range(64):
        if v[i] > 0:
            fingerprint |= 1 << i

    return f"{fingerprint:016x}"


class HybridExtractor:
    """Two-tier extractor: Tier-1 Regex/Defang + Tier-2 Rule-based/GLiNER NLP."""

    def __init__(self) -> None:
        pass

    def extract_all(self, raw_text: str) -> Dict[str, Any]:
        """Runs full extraction over raw text, defanging first.
        
        Returns:
            Dict of schema -> list of unique canonical values, plus metadata.
        """
        refanged = refang(raw_text)
        results: Dict[str, Set[str]] = {
            "IPv4Address": set(),
            "Email": set(),
            "Vulnerability": set(),
            "AutonomousSystem": set(),
            "CryptoWallet": set(),
            "MD5": set(),
            "SHA1": set(),
            "SHA256": set(),
            "URL": set(),
            "Domain": set(),
            "DGA_Domains": set(),
        }

        # 1. Regex Extractions
        for ip in PATTERNS["IPv4Address"].findall(refanged):
            results["IPv4Address"].add(ip)

        for email in PATTERNS["Email"].findall(refanged):
            results["Email"].add(email.lower())

        for cve in PATTERNS["Vulnerability"].findall(refanged):
            results["Vulnerability"].add(cve.upper())

        for asn in PATTERNS["AutonomousSystem"].findall(refanged):
            results["AutonomousSystem"].add(asn.upper())

        for btc in PATTERNS["CryptoWallet_BTC"].findall(refanged):
            results["CryptoWallet"].add(btc)

        for eth in PATTERNS["CryptoWallet_ETH"].findall(refanged):
            results["CryptoWallet"].add(eth)

        for h in PATTERNS["SHA256"].findall(refanged):
            results["SHA256"].add(h.lower())

        for h in PATTERNS["SHA1"].findall(refanged):
            # Exclude if subset of sha256 match
            if not any(h.lower() in full for full in results["SHA256"]):
                results["SHA1"].add(h.lower())

        for h in PATTERNS["MD5"].findall(refanged):
            if not any(h.lower() in full for full in results["SHA256"]) and not any(h.lower() in full for full in results["SHA1"]):
                results["MD5"].add(h.lower())

        for url in PATTERNS["URL"].findall(refanged):
            results["URL"].add(url)

        # Domains (filtered against emails, URLs, and valid TLDs)
        for dom in PATTERNS["Domain"].findall(refanged):
            clean_dom = dom.lower().rstrip(".")
            tld = clean_dom.split(".")[-1]
            if tld in COMMON_TLDS or len(tld) == 2:
                results["Domain"].add(clean_dom)
                # Check DGA entropy
                dga_flag, score = is_dga_domain(clean_dom)
                if dga_flag:
                    results["DGA_Domains"].add(clean_dom)

        # Convert sets to sorted lists
        serialized = {k: sorted(list(v)) for k, v in results.items()}
        serialized["simhash_64"] = compute_simhash_64(refanged)
        return serialized


# Singleton
extractor = HybridExtractor()
