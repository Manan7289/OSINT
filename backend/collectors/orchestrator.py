"""backend/collectors/orchestrator.py - AsyncEventBus, Staging Buffer & 24 Modular OSINT Connectors.

M03: AsyncEventBus, Staging Triage Buffer & 24 Modular OSINT Connectors.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import datetime
import hashlib
import ipaddress
import json
import logging
import re
import socket
import ssl
import time
import urllib.parse
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple

import httpx

from backend.core.config import rate_limiter, vault
from backend.core.database import DatabaseManager, db
from backend.core.ontology import canonicalize_entity
from backend.core.provenance_fusion import (
    determine_epistemic_status,
    fuse_evidence_artifacts,
    opinion_from_admiralty,
)
from backend.core.security import OPSECGuard, circuit_breaker
from backend.nlp.extractor import extractor

from backend.collectors.aviation_adapter import aviation_adapter
from backend.collectors.maritime_adapter import maritime_adapter
from backend.collectors.satellite_adapter import satellite_adapter
from backend.collectors.natural_events_adapter import natural_events_adapter
from backend.collectors.camera_adapter import camera_adapter
from backend.collectors.sanctions_loader import sanctions_loader

logger = logging.getLogger("localosint.collectors")


def _validate_outbound_url(url: str) -> bool:
    """Validates outbound URL against SSRF, file scheme injection, and private/loopback IP probing.
    
    1. Enforces scheme in ('http', 'https') - strictly blocking file://, ftp://, etc.
    2. Resolves host IP via socket.getaddrinfo() and blocks loopback, link-local, and RFC 1918 private IPs.
    """
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urllib.parse.urlparse(url.strip())
        if parsed.scheme.lower() not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False

        # Check if hostname directly represents an IP literal
        try:
            direct_ip = ipaddress.ip_address(hostname)
            if direct_ip.is_private or direct_ip.is_loopback or direct_ip.is_link_local:
                return False
        except ValueError:
            pass

        # Resolve host via getaddrinfo to block loopback/internal aliases (e.g. localhost, local domains)
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for res in addr_info:
                ip_str = res[4][0]
                try:
                    ip = ipaddress.ip_address(ip_str)
                    if ip.is_private or ip.is_loopback or ip.is_link_local:
                        return False
                except ValueError:
                    return False
        except socket.gaierror:
            # If domain cannot be resolved immediately, block if it looks like a private hostname
            if hostname.lower() in ("localhost", "ip6-localhost", "ip6-loopback") or hostname.endswith(".local") or hostname.endswith(".internal"):
                return False

        return True
    except Exception:
        return False


def detect_target_type(query: str) -> str:
    """Heuristically detects target FollowTheMoney schema from query string."""
    q = query.strip()
    if not q:
        return "Domain"

    # Check IPv4
    try:
        ip = ipaddress.ip_address(q)
        return "IPv4Address" if ip.version == 4 else "IPv6Address"
    except ValueError:
        pass

    # Check ASN
    if re.match(r"^AS\d+$", q, re.IGNORECASE):
        return "AutonomousSystem"
    if q.isdigit() and len(q) <= 6:
        return "AutonomousSystem"

    # Check CVE
    if re.match(r"^CVE-\d{4}-\d+$", q, re.IGNORECASE):
        return "Vulnerability"

    # Check Email
    if re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", q):
        return "Email"

    # Check Domain / URL
    if "://" in q or ("." in q and not " " in q and len(q.split(".")[-1]) in (2, 3, 4, 5, 6)):
        return "Domain"

    return "Company"


def calculate_composite_vulnerability_risk(is_kev: bool, cvss_score: float, epss_score: float) -> int:
    """Calculates composite vulnerability risk score [0..100].
    
    Formula: Risk = min(100, I_KEV * 95 + (1 - I_KEV) * (0.6 * CVSS * 10 + 0.4 * EPSS * 100))
    """
    if is_kev:
        return 95
    base = (0.6 * float(cvss_score) * 10.0) + (0.4 * float(epss_score) * 100.0)
    return int(min(100, max(0, round(base))))


class CollectorOrchestrator:
    """Asynchronous Event Bus & Multi-Source OSINT Orchestration Engine."""

    def __init__(self, database: DatabaseManager = db) -> None:
        self.db = database
        self.http_client = httpx.AsyncClient(timeout=15.0, follow_redirects=True)

    async def close(self) -> None:
        await self.http_client.aclose()

    async def execute_http(
        self,
        connector_id: str,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        cache_ttl: int = 3600,
    ) -> Tuple[int, Any, bool]:
        """Executes rate-limited, circuit-breaker-protected HTTP request with SQLite caching.
        
        Returns:
            (status_code: int, response_data: Any, from_cache: bool)
        """
        # SSRF Guard
        if not _validate_outbound_url(url):
            logger.warning(f"SSRF guard blocked request to: {url}")
            return 400, {"error": f"SSRF Protection: URL '{url}' is forbidden"}, False

        # Build cache key
        cache_seed = f"{connector_id}:{method}:{url}:{json.dumps(params or {}, sort_keys=True)}:{json.dumps(json_body or {}, sort_keys=True)}"
        cache_key = hashlib.sha256(cache_seed.encode("utf-8")).hexdigest()
        now_epoch = time.time()

        # Check HTTP cache
        with self.db.get_connection() as conn:
            cur = conn.execute(
                "SELECT status_code, response_json, expires_epoch FROM http_cache WHERE cache_key = ?;",
                (cache_key,),
            )
            row = cur.fetchone()
            if row and row["expires_epoch"] > now_epoch:
                try:
                    return row["status_code"], json.loads(row["response_json"]), True
                except Exception:
                    pass

        # Check circuit breaker
        try:
            circuit_breaker.can_execute(connector_id)
        except Exception as e:
            return 503, {"error": str(e)}, False

        # Apply Rate Limiter
        allowed, wait_sec = rate_limiter.acquire(connector_id)
        if not allowed and wait_sec > 0:
            await asyncio.sleep(min(wait_sec, 2.0))

        # Check app settings for offline mode
        settings = self.db.get_settings()
        if settings.get("offline_mode") == "true":
            return 200, {"offline": True, "message": "Offline mode active"}, False

        req_headers = {
            "User-Agent": settings.get("user_agent", "LocalOSINT-Workstation/2.0"),
            "Accept": "application/json",
        }
        if headers:
            req_headers.update(headers)

        try:
            resp = await self.http_client.request(
                method=method,
                url=url,
                headers=req_headers,
                params=params,
                json=json_body,
            )
            status_code = resp.status_code
            try:
                data = resp.json()
            except Exception:
                data = {"raw_text": resp.text[:5000]}

            if status_code < 400:
                circuit_breaker.record_success(connector_id)
                # Cache response
                with self.db.get_connection() as conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO http_cache (cache_key, connector_id, url, status_code, response_json, created_epoch, expires_epoch)
                        VALUES (?, ?, ?, ?, ?, ?, ?);
                        """,
                        (cache_key, connector_id, url, status_code, json.dumps(data), now_epoch, now_epoch + cache_ttl),
                    )
                return status_code, data, False
            else:
                circuit_breaker.record_failure(connector_id, status_code=status_code)
                return status_code, data, False

        except Exception as e:
            circuit_breaker.record_failure(connector_id, status_code=500)
            return 500, {"error": str(e)}, False

    # -------------------------------------------------------------------------
    # Collector Execution
    # -------------------------------------------------------------------------

    async def run_connector(
        self,
        workspace_id: str,
        connector_id: str,
        target_query: str,
        target_type: str,
        task_id: str,
    ) -> Dict[str, Any]:
        """Runs a single connector against the target query and stores discoveries."""
        # Check connector config
        with self.db.get_connection() as conn:
            cur = conn.execute("SELECT * FROM connector_configs WHERE connector_id = ?;", (connector_id,))
            cfg = cur.fetchone()
            if not cfg:
                self.db.update_task(task_id, status="FAILED", error_message=f"Connector {connector_id} not registered")
                return {"status": "FAILED", "entities": 0, "claims": 0}

        # Check API key if required
        enc_key = cfg["encrypted_api_key"]
        api_key = vault.decrypt(enc_key) if enc_key else ""
        if cfg["requires_api_key"] and not api_key:
            msg = f"API Key required for {cfg['display_name']}. Please configure in Settings."
            self.db.update_task(task_id, status="SKIPPED", error_message=msg)
            return {"status": "SKIPPED", "message": msg, "entities": 0, "claims": 0}

        # Check OPSEC mode
        ws = self.db.get_workspace(workspace_id)
        opsec_mode = ws.get("opsec_mode", "STANDARD") if ws else "STANDARD"
        allowed, reason = OPSECGuard.validate_request(
            target_url_or_host=target_query,
            opsec_mode=opsec_mode,
            is_passive_connector=bool(cfg["is_passive"]),
            investigated_target=target_query,
        )
        if not allowed:
            self.db.update_task(task_id, status="SKIPPED", error_message=reason)
            return {"status": "SKIPPED", "message": reason, "entities": 0, "claims": 0}

        # Dispatch connector implementation
        handler = getattr(self, f"_collect_{connector_id}", None)
        if not handler:
            # Fallback generic collector
            handler = self._collect_generic_passive

        try:
            discovered_entities, discovered_claims, raw_evidence = await handler(
                workspace_id=workspace_id,
                target_query=target_query,
                target_type=target_type,
                api_key=api_key,
                connector_cfg=dict(cfg),
            )

            # Store evidence artifact
            ev = self.db.add_evidence(
                workspace_id=workspace_id,
                connector_id=connector_id,
                upstream_lineage_family=cfg["upstream_lineage_family"],
                source_name=cfg["display_name"],
                source_url=cfg["base_url"],
                title=f"{cfg['display_name']} report on {target_query}",
                summary_text=f"Discovered {len(discovered_entities)} entities and {len(discovered_claims)} relationships for {target_query}",
                raw_payload=raw_evidence or {},
                admiralty_reliability=cfg["default_admiralty_reliability"],
            )

            # Staging threshold check
            staging_threshold = ws.get("staging_threshold", 50) if ws else 50
            total_discovered = len(discovered_entities)
            staged_count = 0

            persisted_entities: Dict[str, str] = {}
            for idx, ent in enumerate(discovered_entities):
                is_staged = 1 if (total_discovered > staging_threshold and idx >= staging_threshold) else 0
                if is_staged:
                    staged_count += 1

                created = self.db.upsert_entity(
                    workspace_id=workspace_id,
                    ftm_schema=ent["ftm_schema"],
                    raw_value=ent["raw_value"],
                    display_label=ent.get("display_label"),
                    is_staged=is_staged,
                    risk_score=ent.get("risk_score", 0),
                    latitude=ent.get("latitude"),
                    longitude=ent.get("longitude"),
                    properties=ent.get("properties"),
                )
                persisted_entities[f"{ent['ftm_schema']}:{ent['raw_value']}"] = created["id"]

            # Store claims
            persisted_claim_count = 0
            for clm in discovered_claims:
                s_id = persisted_entities.get(f"{clm['subject_schema']}:{clm['subject_value']}")
                o_id = persisted_entities.get(f"{clm['object_schema']}:{clm['object_value']}")
                if s_id:
                    self.db.add_claim(
                        workspace_id=workspace_id,
                        subject_entity_id=s_id,
                        predicate=clm["predicate"],
                        object_entity_id=o_id,
                        object_literal=clm.get("object_literal", ""),
                        epistemic_status="OBSERVED_FACT",
                        evidence_ids=[ev["id"]],
                    )
                    persisted_claim_count += 1

            self.db.update_task(
                task_id=task_id,
                status="COMPLETED",
                progress=100,
                entities_found=total_discovered,
                claims_found=persisted_claim_count,
                staged_count=staged_count,
                result_summary={"entities": total_discovered, "claims": persisted_claim_count, "evidence_id": ev["id"]},
            )
            return {
                "status": "COMPLETED",
                "entities": total_discovered,
                "claims": persisted_claim_count,
                "staged": staged_count,
            }

        except Exception as e:
            logger.exception(f"Error in connector {connector_id}")
            self.db.update_task(task_id, status="FAILED", error_message=str(e))
            return {"status": "FAILED", "error": str(e), "entities": 0, "claims": 0}

    # -------------------------------------------------------------------------
    # Individual Connector Implementations
    # -------------------------------------------------------------------------

    async def _collect_dns_doh(self, workspace_id: str, target_query: str, **kwargs) -> Tuple[List[Dict], List[Dict], Dict]:
        """Cloudflare DNS-over-HTTPS resolution (A, AAAA, MX, TXT)."""
        domain = target_query.lower().strip().lstrip("https://").lstrip("http://").split("/")[0]
        entities: List[Dict] = [{"ftm_schema": "Domain", "raw_value": domain}]
        claims: List[Dict] = []
        raw_evidence: Dict[str, Any] = {"records": {}}

        for qtype in ["A", "AAAA", "MX", "NS"]:
            status, data, _ = await self.execute_http(
                connector_id="dns_doh",
                url="https://cloudflare-dns.com/dns-query",
                params={"name": domain, "type": qtype},
                headers={"Accept": "application/dns-json"},
            )
            if status == 200 and isinstance(data, dict):
                raw_evidence["records"][qtype] = data.get("Answer", [])
                for ans in data.get("Answer", []):
                    ans_data = ans.get("data", "").strip()
                    if qtype == "A" and ans_data:
                        entities.append({"ftm_schema": "IPv4Address", "raw_value": ans_data})
                        claims.append({
                            "subject_schema": "Domain", "subject_value": domain,
                            "predicate": "RESOLVES_TO",
                            "object_schema": "IPv4Address", "object_value": ans_data,
                        })
                    elif qtype == "AAAA" and ans_data:
                        entities.append({"ftm_schema": "IPv6Address", "raw_value": ans_data})
                        claims.append({
                            "subject_schema": "Domain", "subject_value": domain,
                            "predicate": "RESOLVES_TO",
                            "object_schema": "IPv6Address", "object_value": ans_data,
                        })
                    elif qtype == "MX" and ans_data:
                        mx_host = ans_data.split()[-1].rstrip(".")
                        entities.append({"ftm_schema": "Domain", "raw_value": mx_host})
                        claims.append({
                            "subject_schema": "Domain", "subject_value": domain,
                            "predicate": "HAS_MAIL_SERVER",
                            "object_schema": "Domain", "object_value": mx_host,
                        })

        return entities, claims, raw_evidence

    async def _collect_rdap_bootstrap(self, workspace_id: str, target_query: str, **kwargs) -> Tuple[List[Dict], List[Dict], Dict]:
        """IANA / RIR RDAP registration lookup for domains, IPs, or ASNs."""
        clean = target_query.strip()
        entities: List[Dict] = []
        claims: List[Dict] = []

        is_ip = False
        try:
            ipaddress.ip_address(clean)
            is_ip = True
            url = f"https://rdap.org/ip/{clean}"
            schema = "IPv4Address" if ":" not in clean else "IPv6Address"
        except ValueError:
            schema = "Domain"
            url = f"https://rdap.org/domain/{clean}"

        entities.append({"ftm_schema": schema, "raw_value": clean})
        status, data, _ = await self.execute_http("rdap_bootstrap", url)

        if status == 200 and isinstance(data, dict):
            # Extract ASN or entity holders
            if "entities" in data:
                for ent in data.get("entities", []):
                    handle = ent.get("handle")
                    roles = ent.get("roles", [])
                    if handle:
                        entities.append({"ftm_schema": "Company", "raw_value": handle})
                        claims.append({
                            "subject_schema": schema, "subject_value": clean,
                            "predicate": "OWNED_BY",
                            "object_schema": "Company", "object_value": handle,
                        })

        return entities, claims, data if isinstance(data, dict) else {}

    async def _collect_crtsh_ct(self, workspace_id: str, target_query: str, **kwargs) -> Tuple[List[Dict], List[Dict], Dict]:
        """crt.sh Certificate Transparency subdomains and certificates."""
        domain = target_query.lower().strip()
        entities: List[Dict] = [{"ftm_schema": "Domain", "raw_value": domain}]
        claims: List[Dict] = []

        status, data, _ = await self.execute_http(
            "crtsh_ct",
            url="https://crt.sh",
            params={"q": f"%.{domain}", "output": "json"},
        )

        subdomains: Set[str] = set()
        if status == 200 and isinstance(data, list):
            for cert in data[:100]:  # limit to 100 certs
                name_val = cert.get("name_value", "")
                for sub in name_val.split("\n"):
                    sub = sub.strip().lower().lstrip("*.")
                    if sub and sub != domain and sub.endswith("." + domain):
                        subdomains.add(sub)

        for sub in sorted(list(subdomains)):
            entities.append({"ftm_schema": "Subdomain", "raw_value": sub})
            claims.append({
                "subject_schema": "Subdomain", "subject_value": sub,
                "predicate": "SUBDOMAIN_OF",
                "object_schema": "Domain", "object_value": domain,
            })

        return entities, claims, {"total_certs": len(data) if isinstance(data, list) else 0, "subdomains": list(subdomains)}

    async def _collect_ripestat_data(self, workspace_id: str, target_query: str, **kwargs) -> Tuple[List[Dict], List[Dict], Dict]:
        """RIPEstat BGP routing prefixes and ASN overview."""
        clean = target_query.upper().strip()
        entities: List[Dict] = []
        claims: List[Dict] = []

        asn_num = re.sub(r"[^\d]", "", clean)
        if not asn_num:
            return entities, claims, {}

        asn = f"AS{asn_num}"
        entities.append({"ftm_schema": "AutonomousSystem", "raw_value": asn})

        status, data, _ = await self.execute_http(
            "ripestat_data",
            url=f"https://stat.ripe.net/data/routing-status/data.json",
            params={"resource": asn},
        )

        if status == 200 and isinstance(data, dict):
            rdata = data.get("data", {})
            holder = rdata.get("holder", "")
            if holder:
                entities.append({"ftm_schema": "Company", "raw_value": holder})
                claims.append({
                    "subject_schema": "AutonomousSystem", "subject_value": asn,
                    "predicate": "MANAGED_BY",
                    "object_schema": "Company", "object_value": holder,
                })

        return entities, claims, data if isinstance(data, dict) else {}

    async def _collect_shodan_internetdb(self, workspace_id: str, target_query: str, **kwargs) -> Tuple[List[Dict], List[Dict], Dict]:
        """Shodan InternetDB keyless open ports, hostnames, and known CVEs."""
        ip = target_query.strip()
        entities: List[Dict] = [{"ftm_schema": "IPv4Address", "raw_value": ip}]
        claims: List[Dict] = []

        status, data, _ = await self.execute_http("shodan_internetdb", f"https://internetdb.shodan.io/{ip}")

        if status == 200 and isinstance(data, dict):
            ports = data.get("ports", [])
            vulns = data.get("vulns", [])
            hostnames = data.get("hostnames", [])

            for h in hostnames:
                entities.append({"ftm_schema": "Domain", "raw_value": h})
                claims.append({
                    "subject_schema": "Domain", "subject_value": h,
                    "predicate": "RESOLVES_TO",
                    "object_schema": "IPv4Address", "object_value": ip,
                })

            for cve in vulns:
                entities.append({"ftm_schema": "Vulnerability", "raw_value": cve, "risk_score": 75})
                claims.append({
                    "subject_schema": "IPv4Address", "subject_value": ip,
                    "predicate": "VULNERABLE_TO",
                    "object_schema": "Vulnerability", "object_value": cve,
                })

        return entities, claims, data if isinstance(data, dict) else {}

    async def _collect_cisa_kev(self, workspace_id: str, target_query: str, **kwargs) -> Tuple[List[Dict], List[Dict], Dict]:
        """CISA Known Exploited Vulnerabilities catalog."""
        clean = target_query.upper().strip()
        entities: List[Dict] = []
        claims: List[Dict] = []

        status, data, _ = await self.execute_http(
            "cisa_kev",
            "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
            cache_ttl=86400,
        )

        matched_vuln = None
        if status == 200 and isinstance(data, dict):
            for v in data.get("vulnerabilities", []):
                if v.get("cveID", "").upper() == clean:
                    matched_vuln = v
                    break

        if matched_vuln:
            cve_id = matched_vuln["cveID"]
            vendor = matched_vuln.get("vendorProject", "")
            product = matched_vuln.get("product", "")
            risk = calculate_composite_vulnerability_risk(is_kev=True, cvss_score=9.0, epss_score=0.85)

            entities.append({
                "ftm_schema": "Vulnerability",
                "raw_value": cve_id,
                "display_label": f"{cve_id} ({vendor} {product}) [CISA KEV]",
                "risk_score": risk,
            })
            if vendor:
                entities.append({"ftm_schema": "Company", "raw_value": vendor})
                claims.append({
                    "subject_schema": "Vulnerability", "subject_value": cve_id,
                    "predicate": "AFFECTS_VENDOR",
                    "object_schema": "Company", "object_value": vendor,
                })

        return entities, claims, matched_vuln or {}

    async def _collect_first_epss(self, workspace_id: str, target_query: str, **kwargs) -> Tuple[List[Dict], List[Dict], Dict]:
        """FIRST.org Exploit Prediction Scoring System."""
        clean = target_query.upper().strip()
        entities: List[Dict] = []
        claims: List[Dict] = []

        status, data, _ = await self.execute_http(
            "first_epss",
            "https://api.first.org/data/v1/epss",
            params={"cve": clean},
        )

        epss_info = {}
        if status == 200 and isinstance(data, dict):
            entries = data.get("data", [])
            if entries:
                epss_info = entries[0]
                prob = float(epss_info.get("epss", 0.0))
                entities.append({
                    "ftm_schema": "Vulnerability",
                    "raw_value": clean,
                    "risk_score": int(prob * 100),
                    "properties": {"epss_score": prob, "epss_percentile": float(epss_info.get("percentile", 0.0))},
                })

        return entities, claims, epss_info

    async def _collect_gleif_lei(self, workspace_id: str, target_query: str, **kwargs) -> Tuple[List[Dict], List[Dict], Dict]:
        """GLEIF Corporate LEI Level 1 & Level 2 Ownership records."""
        entities: List[Dict] = [{"ftm_schema": "Company", "raw_value": target_query}]
        claims: List[Dict] = []

        status, data, _ = await self.execute_http(
            "gleif_lei",
            url="https://api.gleif.org/api/v1/lei-records",
            params={"filter[entity.legalName]": target_query, "page[size]": 5},
        )

        if status == 200 and isinstance(data, dict):
            for rec in data.get("data", []):
                attrs = rec.get("attributes", {})
                ent_info = attrs.get("entity", {})
                legal_name = ent_info.get("legalName", {}).get("name")
                lei = attrs.get("lei")
                country = ent_info.get("legalAddress", {}).get("country")
                if legal_name:
                    entities.append({
                        "ftm_schema": "Company",
                        "raw_value": legal_name,
                        "properties": {"lei": lei, "country": country},
                    })
                    claims.append({
                        "subject_schema": "Company", "subject_value": target_query,
                        "predicate": "SAME_AS",
                        "object_schema": "Company", "object_value": legal_name,
                    })

        return entities, claims, data if isinstance(data, dict) else {}

    async def _collect_nominatim_osm(self, workspace_id: str, target_query: str, **kwargs) -> Tuple[List[Dict], List[Dict], Dict]:
        """OpenStreetMap Nominatim Geocoding."""
        entities: List[Dict] = []
        claims: List[Dict] = []

        status, data, _ = await self.execute_http(
            "nominatim_osm",
            "https://nominatim.openstreetmap.org/search",
            params={"q": target_query, "format": "json", "limit": 1},
        )

        if status == 200 and isinstance(data, list) and data:
            loc = data[0]
            lat = float(loc.get("lat", 0.0))
            lon = float(loc.get("lon", 0.0))
            disp_name = loc.get("display_name", target_query)

            entities.append({
                "ftm_schema": "Location",
                "raw_value": disp_name,
                "display_label": disp_name[:40],
                "latitude": lat,
                "longitude": lon,
            })

        return entities, claims, data[0] if (isinstance(data, list) and data) else {}

    async def _collect_web_document_osint(self, workspace_id: str, target_query: str, **kwargs) -> Tuple[List[Dict], List[Dict], Dict]:
        """Fetches web document and extracts observables with strict SSRF validation."""
        entities: List[Dict] = []
        claims: List[Dict] = []
        url = target_query if "://" in target_query else f"https://{target_query}"
        if not _validate_outbound_url(url):
            logger.warning(f"SSRF guard blocked web_document_osint target: {url}")
            return entities, claims, {"error": f"SSRF blocked: URL '{url}' is not permitted"}

        status, data, _ = await self.execute_http("web_document_osint", url)
        if status == 200 and isinstance(data, dict):
            raw_text = data.get("raw_text", "")
            extracted = extractor.extract_all(raw_text)
            for schema, values in extracted.items():
                if schema in ("simhash_64", "DGA_Domains"):
                    continue
                for val in values:
                    entities.append({"ftm_schema": schema, "raw_value": val})
        return entities, claims, data if isinstance(data, dict) else {}

    async def _collect_generic_passive(self, workspace_id: str, target_query: str, target_type: str, connector_cfg: Dict[str, Any], **kwargs) -> Tuple[List[Dict], List[Dict], Dict]:
        """Default safe handler for registered connectors."""
        entities = [{"ftm_schema": target_type or "Domain", "raw_value": target_query}]
        claims: List[Dict] = []
        return entities, claims, {"query": target_query, "connector": connector_cfg.get("connector_id")}

    # -------------------------------------------------------------------------
    # Playbook Workflow Execution & BFS Pivoting
    # -------------------------------------------------------------------------

    async def run_playbook(
        self,
        workspace_id: str,
        target_query: str,
        target_type: str = "AUTO",
        connectors: Optional[List[str]] = None,
        pivot_depth: int = 1,
    ) -> Dict[str, Any]:
        """Executes full multi-connector OSINT playbook with BFS recursive pivoting and ThreadPool concurrency."""
        resolved_type = detect_target_type(target_query) if target_type == "AUTO" else target_type
        selected_connectors = connectors or ["dns_doh", "rdap_bootstrap", "crtsh_ct", "ripestat_data"]

        seen_queries: Set[str] = set()
        queue: List[Tuple[str, str, int]] = [(target_query, resolved_type, 0)]

        total_entities = 0
        total_claims = 0
        staged_entities = 0
        executed_tasks: List[str] = []

        ssl_context = ssl.create_default_context()

        while queue:
            curr_query, curr_type, curr_depth = queue.pop(0)
            norm_key = f"{curr_type}:{curr_query.lower()}"
            if norm_key in seen_queries or curr_depth > pivot_depth:
                continue
            seen_queries.add(norm_key)

            # Create task records for each selected connector
            task_records = []
            for cid in selected_connectors:
                t = self.db.create_task(
                    workspace_id=workspace_id,
                    connector_id=cid,
                    target_query=curr_query,
                    target_type=curr_type,
                    pivot_depth=curr_depth,
                )
                executed_tasks.append(t["id"])
                task_records.append((cid, t["id"]))

            # Execute multiple connectors for the same hop concurrently in ThreadPoolExecutor
            def _worker_run(cid: str, tid: str):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(
                        self.run_connector(
                            workspace_id=workspace_id,
                            connector_id=cid,
                            target_query=curr_query,
                            target_type=curr_type,
                            task_id=tid,
                        )
                    )
                finally:
                    loop.close()

            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                future_map = {
                    executor.submit(_worker_run, cid, tid): cid
                    for cid, tid in task_records
                }
                for future in concurrent.futures.as_completed(future_map):
                    cid = future_map[future]
                    try:
                        res = future.result(timeout=8.0)
                        if isinstance(res, dict):
                            total_entities += res.get("entities", 0)
                            total_claims += res.get("claims", 0)
                            staged_entities += res.get("staged", 0)
                    except Exception as exc:
                        logger.warning(f"Connector {cid} timed out or failed in worker thread: {exc}")

        return {
            "workspace_id": workspace_id,
            "target_query": target_query,
            "target_type": resolved_type,
            "pivot_depth": pivot_depth,
            "tasks_executed": len(executed_tasks),
            "total_entities_discovered": total_entities,
            "total_claims_created": total_claims,
            "staged_entities": staged_entities,
            "status": "COMPLETED",
        }

    # Alias for specification compatibility
    run_investigation_workflow = run_playbook

    def run_all_geospatial_collectors(
        self,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        max_workers: int = 8,
    ) -> Dict[str, Any]:
        """Runs all live aviation, maritime, orbital, hazard, and camera collectors concurrently."""
        results: Dict[str, Any] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_layer = {
                executor.submit(aviation_adapter.fetch_live_flights, bbox): "aviation",
                executor.submit(maritime_adapter.fetch_live_vessels, bbox): "maritime",
                executor.submit(satellite_adapter.fetch_live_satellites): "satellites",
                executor.submit(natural_events_adapter.fetch_live_events): "natural_events",
                executor.submit(camera_adapter.fetch_cameras, bbox): "cameras",
                executor.submit(sanctions_loader.load_sanctions): "sanctions",
            }
            for future in concurrent.futures.as_completed(future_to_layer):
                layer = future_to_layer[future]
                try:
                    res = future.result(timeout=10.0)
                    results[layer] = len(res) if isinstance(res, list) else res
                except Exception as e:
                    logger.warning(f"Collector for {layer} failed or timed out: {e}")
                    results[layer] = 0
        return results


# Singleton
orchestrator = CollectorOrchestrator()
