"""backend/exporters.py - Multi-Format Export Engine (JSON, CSV, STIX 2.1, FtM JSONL, W3C PROV).

M09: FastAPI REST/WebSocket Server & Multi-Format Export Engine.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from typing import Any, Dict, List

from backend.core.database import DatabaseManager, db


def export_workspace_json(workspace_id: str, database: DatabaseManager = db) -> Dict[str, Any]:
    """Exports full workspace bundle with entities, claims, evidence, and audit logs."""
    ws = database.get_workspace(workspace_id)
    if not ws:
        raise ValueError(f"Workspace {workspace_id} not found")

    entities = database.list_entities(workspace_id=workspace_id, include_staged=True, limit=10000)
    claims = database.list_claims(workspace_id=workspace_id, limit=20000)
    evidence = database.list_evidence(workspace_id=workspace_id, limit=5000)
    reports = database.list_reports(workspace_id=workspace_id)

    return {
        "version": "2.0.0",
        "format": "LocalOSINT_Workspace_JSON",
        "workspace": ws,
        "entities": entities,
        "claims": claims,
        "evidence_artifacts": evidence,
        "reports": reports,
    }


def export_workspace_csv(workspace_id: str, database: DatabaseManager = db) -> str:
    """Exports workspace entities as standard CSV format."""
    entities = database.list_entities(workspace_id=workspace_id, include_staged=True, limit=20000)
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "id", "ftm_schema", "canonical_value", "display_label",
        "sl_belief", "risk_score", "is_staged", "is_shared_infra",
        "independent_sources", "first_seen_at", "last_seen_at"
    ])

    for e in entities:
        writer.writerow([
            e["id"], e["ftm_schema"], e["canonical_value"], e["display_label"],
            e.get("sl_belief", 0.75), e.get("risk_score", 0),
            e.get("is_staged", 0), e.get("is_shared_infra", 0),
            e.get("independent_source_count", 1),
            e.get("first_seen_at", ""), e.get("last_seen_at", ""),
        ])

    return output.getvalue()


def export_workspace_stix(workspace_id: str, database: DatabaseManager = db) -> Dict[str, Any]:
    """Exports workspace knowledge graph as an OASIS STIX 2.1 JSON bundle."""
    ws = database.get_workspace(workspace_id)
    if not ws:
        raise ValueError(f"Workspace {workspace_id} not found")

    entities = database.list_entities(workspace_id=workspace_id, include_staged=False, limit=5000)
    claims = database.list_claims(workspace_id=workspace_id, limit=10000)

    stix_objects: List[Dict[str, Any]] = []
    stix_id_map: Dict[str, str] = {}

    # Map entities to STIX Domain Objects (SDOs)
    for e in entities:
        schema = e["ftm_schema"]
        val = e["canonical_value"]
        lbl = e["display_label"]
        uid = uuid.uuid5(uuid.NAMESPACE_DNS, f"{workspace_id}:{e['id']}")

        if schema in ("Domain", "Subdomain"):
            stix_id = f"infrastructure--{uid}"
            sdo = {
                "type": "infrastructure",
                "spec_version": "2.1",
                "id": stix_id,
                "name": lbl,
                "infrastructure_types": ["domain"],
            }
        elif schema in ("IPv4Address", "IPv6Address"):
            stix_id = f"ipv4-addr--{uid}" if schema == "IPv4Address" else f"ipv6-addr--{uid}"
            sdo = {
                "type": "ipv4-addr" if schema == "IPv4Address" else "ipv6-addr",
                "spec_version": "2.1",
                "id": stix_id,
                "value": val,
            }
        elif schema == "AutonomousSystem":
            stix_id = f"autonomous-system--{uid}"
            num = int(val.replace("AS", "")) if val.replace("AS", "").isdigit() else 0
            sdo = {
                "type": "autonomous-system",
                "spec_version": "2.1",
                "id": stix_id,
                "number": num,
                "name": lbl,
            }
        elif schema == "Vulnerability":
            stix_id = f"vulnerability--{uid}"
            sdo = {
                "type": "vulnerability",
                "spec_version": "2.1",
                "id": stix_id,
                "name": val,
                "description": lbl,
            }
        elif schema in ("Company", "Organization"):
            stix_id = f"identity--{uid}"
            sdo = {
                "type": "identity",
                "spec_version": "2.1",
                "id": stix_id,
                "name": lbl,
                "identity_class": "organization",
            }
        elif schema == "Person":
            stix_id = f"identity--{uid}"
            sdo = {
                "type": "identity",
                "spec_version": "2.1",
                "id": stix_id,
                "name": lbl,
                "identity_class": "individual",
            }
        else:
            stix_id = f"indicator--{uid}"
            sdo = {
                "type": "indicator",
                "spec_version": "2.1",
                "id": stix_id,
                "name": lbl,
                "pattern": f"[{schema}:value = '{val}']",
                "pattern_type": "stix",
            }

        stix_id_map[e["id"]] = stix_id
        stix_objects.append(sdo)

    # Map claims to STIX Relationship Objects (SROs)
    for c in claims:
        s_id = stix_id_map.get(c["subject_entity_id"])
        o_id = stix_id_map.get(c.get("object_entity_id", ""))
        if s_id and o_id:
            rel_uid = uuid.uuid5(uuid.NAMESPACE_DNS, f"{c['id']}")
            rel_sro = {
                "type": "relationship",
                "spec_version": "2.1",
                "id": f"relationship--{rel_uid}",
                "relationship_type": c["predicate"].lower().replace("_", "-"),
                "source_ref": s_id,
                "target_ref": o_id,
                "confidence": int(c.get("sl_belief", 0.75) * 100),
            }
            stix_objects.append(rel_sro)

    return {
        "type": "bundle",
        "id": f"bundle--{uuid.uuid4()}",
        "objects": stix_objects,
    }


def export_workspace_ftm(workspace_id: str, database: DatabaseManager = db) -> str:
    """Exports entities in FollowTheMoney (FtM) JSON Lines format."""
    entities = database.list_entities(workspace_id=workspace_id, include_staged=False, limit=10000)
    lines = []
    for e in entities:
        ftm_rec = {
            "id": e["id"],
            "schema": e["ftm_schema"],
            "properties": {
                "name": [e["display_label"]],
                "canonical": [e["canonical_value"]],
            },
        }
        lines.append(json.dumps(ftm_rec))
    return "\n".join(lines)


def export_workspace_prov(workspace_id: str, database: DatabaseManager = db) -> Dict[str, Any]:
    """Exports evidence artifacts and claims in W3C PROV-JSON standard format."""
    evidence = database.list_evidence(workspace_id=workspace_id, limit=5000)
    claims = database.list_claims(workspace_id=workspace_id, limit=10000)

    prov_entities = {}
    prov_agents = {}
    prov_derivations = {}

    for ev in evidence:
        prov_entities[ev["id"]] = {
            "prov:type": "osint:EvidenceArtifact",
            "osint:source_name": ev["source_name"],
            "osint:upstream_lineage_family": ev["upstream_lineage_family"],
            "osint:payload_sha256": ev["payload_sha256"],
            "osint:observed_at": ev["observed_at"],
            "osint:admiralty": f"{ev['admiralty_reliability']}{ev['admiralty_credibility']}",
        }
        agent_id = f"agent:{ev['connector_id']}"
        prov_agents[agent_id] = {
            "prov:type": "prov:SoftwareAgent",
            "osint:connector": ev["connector_id"],
        }
        if ev.get("parent_evidence_id"):
            der_id = f"der_{ev['id']}"
            prov_derivations[der_id] = {
                "prov:generatedEntity": ev["id"],
                "prov:usedEntity": ev["parent_evidence_id"],
            }

    return {
        "prefix": {
            "prov": "http://www.w3.org/ns/prov#",
            "osint": "https://github.com/Manan7289/OSINT/prov#",
        },
        "entity": prov_entities,
        "agent": prov_agents,
        "wasDerivedFrom": prov_derivations,
    }
