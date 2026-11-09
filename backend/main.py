"""backend/main.py - FastAPI Application, REST/WebSocket API Routers & Static Workstation Server.

M09: FastAPI REST/WebSocket Server & Multi-Format Export Engine.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Body, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.ai.assistant import graphrag_assistant
from backend.ai.search_rrf import hybrid_search_engine
from backend.collectors.orchestrator import orchestrator
from backend.collectors.sweep_delta import sweep_delta_engine
from backend.collectors.aviation_adapter import aviation_adapter
from backend.collectors.maritime_adapter import maritime_adapter
from backend.collectors.satellite_adapter import satellite_adapter
from backend.collectors.natural_events_adapter import natural_events_adapter
from backend.collectors.camera_adapter import camera_adapter
from backend.collectors.sanctions_loader import sanctions_loader
from backend.alerts.alert_engine import alert_engine
from backend.visual.media_forensics import media_forensics_engine
from backend.visual.vision_engine import vision_engine
from backend.visual.consent_guard import (
    consent_guard,
    ConsentViolationError,
    QualityGateRejectionError,
)
from backend.core.config import FRONTEND_DIR, HOST, PORT
from backend.core.database import db
from backend.core.entity_resolution import entity_resolution_engine
from backend.core.graph_analytics import graph_engine
from backend.core.security import HashChainedAuditLogger
from backend.core.spatiotemporal import spatiotemporal_engine
from backend.exporters import (
    export_workspace_csv,
    export_workspace_ftm,
    export_workspace_json,
    export_workspace_prov,
    export_workspace_stix,
)
from backend.nlp.extractor import extractor, refang
from backend.nlp.forensics import analyze_file


MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB file upload limit


# -----------------------------------------------------------------------------
# Demonstration Workspace Seeding
# -----------------------------------------------------------------------------

def seed_demo_workspace_if_empty() -> None:
    """Seeds an initial demonstration investigation case if database has no demonstration workspace."""
    existing = db.list_workspaces()
    if any("Operation Sentinel" in w.get("name", "") for w in existing):
        return

    ws = db.create_workspace(
        name="Operation Sentinel — Infrastructure Footprint",
        description="Demonstration case investigating ASN, CT logs, C2 indicators and corporate LEI ownership",
        tlp_marking="TLP:AMBER",
        opsec_mode="STANDARD",
        scope_domains=["sentinel-intel.org", "darkshadow.net"],
        max_pivot_depth=2,
    )
    ws_id = ws["id"]

    # Entities
    e_domain = db.upsert_entity(ws_id, "Domain", "darkshadow.net", display_label="darkshadow.net (C2 Apex)")
    e_sub = db.upsert_entity(ws_id, "Subdomain", "c2.darkshadow.net", display_label="c2.darkshadow.net", risk_score=85)
    e_ip = db.upsert_entity(ws_id, "IPv4Address", "185.220.101.34", display_label="185.220.101.34", latitude=52.3702, longitude=4.8952, location_label="Amsterdam, NL")
    e_asn = db.upsert_entity(ws_id, "AutonomousSystem", "AS13335", display_label="AS13335 (Cloudflare Inc)")
    e_cve = db.upsert_entity(ws_id, "Vulnerability", "CVE-2024-3400", display_label="CVE-2024-3400 (PAN-OS Zero-Day)", risk_score=95)
    e_co = db.upsert_entity(ws_id, "Company", "ShadowNet Security LLC", display_label="ShadowNet Security LLC")

    # Evidence
    ev1 = db.add_evidence(
        ws_id, "crtsh_ct", "Sectigo_crtsh", "crt.sh CT Log", "https://crt.sh",
        "Certificate Transparency Log for darkshadow.net",
        "Discovered active wildcard certificate and subdomain c2.darkshadow.net",
        {"san": ["darkshadow.net", "*.darkshadow.net", "c2.darkshadow.net"]},
        admiralty_reliability="A", admiralty_credibility=1,
    )
    ev2 = db.add_evidence(
        ws_id, "dns_doh", "Cloudflare", "Cloudflare DoH", "https://cloudflare-dns.com",
        "Authoritative A record resolution for c2.darkshadow.net",
        "Resolved c2.darkshadow.net to 185.220.101.34",
        {"Answer": [{"name": "c2.darkshadow.net", "type": 1, "data": "185.220.101.34"}]},
        admiralty_reliability="A", admiralty_credibility=1,
    )

    # Claims
    db.add_claim(ws_id, e_sub["id"], "SUBDOMAIN_OF", e_domain["id"], epistemic_status="CORROBORATED_FACT", evidence_ids=[ev1["id"]])
    db.add_claim(ws_id, e_sub["id"], "RESOLVES_TO", e_ip["id"], epistemic_status="CORROBORATED_FACT", evidence_ids=[ev2["id"]])
    db.add_claim(ws_id, e_ip["id"], "ROUTED_BY", e_asn["id"], epistemic_status="OBSERVED_FACT", evidence_ids=[ev2["id"]])
    db.add_claim(ws_id, e_ip["id"], "EXPLOITS", e_cve["id"], epistemic_status="DERIVED_INFERENCE")
    db.add_claim(ws_id, e_domain["id"], "REGISTERED_BY", e_co["id"], epistemic_status="OBSERVED_FACT")


logger = logging.getLogger(__name__)

# Scheduled 15-minute Crucix auto-sweeper state
auto_sweeper_state = {
    "enabled": True,
    "interval_seconds": 900,
    "last_sweep_at": None,
    "sweep_count": 0,
}


async def background_scheduled_sweeper():
    """Autonomous Crucix 15-minute scheduled parallel sweep background task."""
    await asyncio.sleep(10)
    while True:
        try:
            if auto_sweeper_state["enabled"]:
                res = sweep_delta_engine.run_sweep()
                auto_sweeper_state["last_sweep_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                auto_sweeper_state["sweep_count"] += 1
                await alert_engine.broadcast_event("SWEEP_COMPLETED", {
                    "sweep_id": res["sweep_id"],
                    "escalation_score": res["escalation_score"],
                    "deltas_count": len(res.get("deltas", [])),
                    "stats": res.get("stats", {}),
                    "source": "SCHEDULED_15M_SWEEPER",
                })
        except Exception as e:
            logger.error(f"Error in background scheduled sweeper: {e}")
        await asyncio.sleep(auto_sweeper_state["interval_seconds"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_demo_workspace_if_empty()
    sanctions_loader.load_sanctions()
    sweeper_task = asyncio.create_task(background_scheduled_sweeper())
    yield
    sweeper_task.cancel()
    await orchestrator.close()


app = FastAPI(
    title="LocalOSINT v3.0 Global Intelligence Command Centre",
    description="Next-Generation Global Intelligence Command Centre unifiying kinetic tracking, Crucix sweep-deltas, orbital propagation, and privacy-preserving visual intelligence.",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# Request & Response Models
# -----------------------------------------------------------------------------

class WorkspaceCreateRequest(BaseModel):
    name: str
    description: str = ""
    tlp_marking: str = "TLP:CLEAR"
    opsec_mode: str = "STANDARD"
    scope_domains: List[str] = Field(default_factory=list)
    max_pivot_depth: int = 2
    staging_threshold: int = 50
    tags: List[str] = Field(default_factory=list)


class EntityCreateRequest(BaseModel):
    ftm_schema: str
    raw_value: str
    display_label: Optional[str] = None
    is_staged: int = 0
    risk_score: int = 0
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_label: str = ""
    properties: Dict[str, Any] = Field(default_factory=dict)
    aliases: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class StagingPromoteRequest(BaseModel):
    entity_ids: Optional[List[str]] = None
    promote_all_above_risk: Optional[int] = None


class ClaimCreateRequest(BaseModel):
    subject_entity_id: str
    predicate: str
    object_entity_id: Optional[str] = None
    object_literal: str = ""
    epistemic_status: str = "OBSERVED_FACT"
    sl_belief: float = 0.75
    sl_disbelief: float = 0.00
    sl_uncertainty: float = 0.25
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)


class PlaybookRunRequest(BaseModel):
    workspace_id: str
    target_query: str
    target_type: str = "AUTO"
    connectors: Optional[List[str]] = None
    pivot_depth: int = 1


class DocumentTextRequest(BaseModel):
    workspace_id: str
    text_content: str
    title: str = "Pasted Intelligence Text"


class MergeRequest(BaseModel):
    primary_entity_id: str
    duplicate_entity_id: str
    match_probability: float = 0.95


class AIQueryRequest(BaseModel):
    workspace_id: str
    query: str


class ReportGenerateRequest(BaseModel):
    workspace_id: str
    title: str
    query: str
    report_type: str = "COMPREHENSIVE"
    tlp_marking: str = "TLP:CLEAR"


class SettingsUpdateRequest(BaseModel):
    settings: Dict[str, str]


class ConnectorUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    plaintext_api_key: Optional[str] = None
    rate_limit_rpm: Optional[int] = None


# -----------------------------------------------------------------------------
# REST Endpoints
# -----------------------------------------------------------------------------

@app.get("/api/health")
@app.get("/api/v2/health")
@app.get("/api/v3/health")
def get_health() -> Dict[str, Any]:
    conns = db.get_connectors()
    workspaces = db.list_workspaces()
    ready_count = sum(1 for c in conns if c["enabled"] and (not c["requires_api_key"] or c["has_api_key"]))

    return {
        "status": "healthy",
        "version": "3.0.0",
        "database_wal": True,
        "onnx_available": True,
        "workspace_count": len(workspaces),
        "connectors_total": len(conns),
        "connectors_ready": ready_count,
        "sanctions_indexed": sanctions_loader.count(),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


# Workspaces
@app.get("/api/workspaces")
@app.get("/api/v2/workspaces")
def list_workspaces():
    return db.list_workspaces()


@app.post("/api/workspaces")
@app.get("/api/v2/workspaces")
def create_workspace(req: WorkspaceCreateRequest):
    return db.create_workspace(
        name=req.name,
        description=req.description,
        tlp_marking=req.tlp_marking,
        opsec_mode=req.opsec_mode,
        scope_domains=req.scope_domains,
        max_pivot_depth=req.max_pivot_depth,
        staging_threshold=req.staging_threshold,
        tags=req.tags,
    )


@app.get("/api/workspaces/{workspace_id}")
@app.get("/api/v2/workspaces/{workspace_id}")
def get_workspace(workspace_id: str):
    ws = db.get_workspace(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


@app.delete("/api/workspaces/{workspace_id}")
@app.delete("/api/v2/workspaces/{workspace_id}")
def delete_workspace(workspace_id: str):
    deleted = db.delete_workspace(workspace_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"status": "DELETED", "workspace_id": workspace_id}


# Entities
@app.get("/api/workspaces/{workspace_id}/entities")
@app.get("/api/v2/workspaces/{workspace_id}/entities")
def list_entities(
    workspace_id: str,
    ftm_schema: Optional[str] = None,
    include_staged: bool = False,
    min_belief: Optional[float] = None,
    q: Optional[str] = None,
    limit: int = 500,
):
    return db.list_entities(
        workspace_id=workspace_id,
        ftm_schema=ftm_schema,
        include_staged=include_staged,
        min_belief=min_belief,
        search_query=q,
        limit=limit,
    )


@app.post("/api/workspaces/{workspace_id}/entities")
@app.post("/api/v2/workspaces/{workspace_id}/entities")
def create_entity(workspace_id: str, req: EntityCreateRequest):
    return db.upsert_entity(
        workspace_id=workspace_id,
        ftm_schema=req.ftm_schema,
        raw_value=req.raw_value,
        display_label=req.display_label,
        is_staged=req.is_staged,
        risk_score=req.risk_score,
        latitude=req.latitude,
        longitude=req.longitude,
        location_label=req.location_label,
        properties=req.properties,
        aliases=req.aliases,
        tags=req.tags,
    )


@app.post("/api/workspaces/{workspace_id}/staging/promote")
@app.post("/api/v2/workspaces/{workspace_id}/staging/promote")
def promote_staging(workspace_id: str, req: StagingPromoteRequest):
    promoted = db.promote_staged_entities(
        workspace_id=workspace_id,
        entity_ids=req.entity_ids,
        min_risk=req.promote_all_above_risk,
    )
    return {"status": "PROMOTED", "promoted_count": promoted}


# Claims (Bitemporal Edges)
@app.get("/api/workspaces/{workspace_id}/claims")
@app.get("/api/workspaces/{workspace_id}/relationships")
@app.get("/api/v2/workspaces/{workspace_id}/claims")
def list_claims(
    workspace_id: str,
    epistemic_status: Optional[str] = None,
    as_of_time: Optional[str] = None,
    subject_id: Optional[str] = None,
    object_id: Optional[str] = None,
    limit: int = 1000,
):
    return db.list_claims(
        workspace_id=workspace_id,
        epistemic_status=epistemic_status,
        as_of_time=as_of_time,
        subject_id=subject_id,
        object_id=object_id,
        limit=limit,
    )


@app.post("/api/workspaces/{workspace_id}/claims")
@app.post("/api/workspaces/{workspace_id}/relationships")
@app.post("/api/v2/workspaces/{workspace_id}/claims")
def create_claim(workspace_id: str, req: ClaimCreateRequest):
    return db.add_claim(
        workspace_id=workspace_id,
        subject_entity_id=req.subject_entity_id,
        predicate=req.predicate,
        object_entity_id=req.object_entity_id,
        object_literal=req.object_literal,
        epistemic_status=req.epistemic_status,
        sl_opinion=(req.sl_belief, req.sl_disbelief, req.sl_uncertainty, 0.50),
        valid_from=req.valid_from,
        valid_until=req.valid_until,
        evidence_ids=req.evidence_ids,
    )


# Collection Playbooks & Forensics
@app.post("/api/collect/workflow")
@app.post("/api/collect/playbook")
@app.post("/api/v2/collect/workflow")
async def run_collection_playbook(req: PlaybookRunRequest):
    return await orchestrator.run_playbook(
        workspace_id=req.workspace_id,
        target_query=req.target_query,
        target_type=req.target_type,
        connectors=req.connectors,
        pivot_depth=req.pivot_depth,
    )


@app.post("/api/collect/document-text")
@app.post("/api/v2/collect/document-text")
def collect_document_text(req: DocumentTextRequest):
    extracted = extractor.extract_all(req.text_content)
    # Store evidence
    ev = db.add_evidence(
        workspace_id=req.workspace_id,
        connector_id="local_doc_forensics",
        upstream_lineage_family="LocalAnalyst",
        source_name="Document Text Paste",
        source_url="local://paste",
        title=req.title,
        summary_text=f"Extracted observables from {req.title}",
        raw_payload={"extracted": extracted},
        simhash_64=extracted.get("simhash_64", "0000000000000000"),
    )
    # Upsert entities
    created = []
    for schema, values in extracted.items():
        if schema in ("simhash_64", "DGA_Domains"):
            continue
        for val in values:
            ent = db.upsert_entity(workspace_id=req.workspace_id, ftm_schema=schema, raw_value=val)
            created.append(ent)

    return {"status": "EXTRACTED", "evidence_id": ev["id"], "entities": created, "extracted": extracted}


@app.post("/api/collect/document-upload")
@app.post("/api/v2/collect/document-upload")
async def collect_document_upload(
    workspace_id: str = Query(...),
    file: UploadFile = File(...),
):
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 25 MB limit")
    analysis = analyze_file(file.filename, contents)

    ev = db.add_evidence(
        workspace_id=workspace_id,
        connector_id="local_doc_forensics",
        upstream_lineage_family="LocalFile",
        source_name=f"File: {file.filename}",
        source_url=f"local://file/{file.filename}",
        title=f"Forensic Analysis of {file.filename}",
        summary_text=f"Analyzed {analysis.get('file_type')} file ({len(contents)} bytes)",
        raw_payload=analysis,
        simhash_64=analysis.get("simhash_64", "0000000000000000"),
    )

    created = []
    for schema, values in analysis.get("entities", {}).items():
        if schema in ("simhash_64", "DGA_Domains"):
            continue
        for val in values:
            ent = db.upsert_entity(workspace_id=workspace_id, ftm_schema=schema, raw_value=val)
            created.append(ent)

    return {"status": "ANALYZED", "evidence_id": ev["id"], "analysis": analysis, "entities": created}


# Entity Resolution
@app.get("/api/workspaces/{workspace_id}/entity-resolution")
@app.get("/api/v2/workspaces/{workspace_id}/entity-resolution")
def get_entity_resolution_candidates(
    workspace_id: str,
    min_probability: float = 0.50,
):
    return entity_resolution_engine.evaluate_candidates(
        workspace_id=workspace_id, min_probability=min_probability
    )


@app.post("/api/workspaces/{workspace_id}/entity-resolution/merge")
@app.post("/api/v2/workspaces/{workspace_id}/entity-resolution/merge")
def merge_entities_endpoint(workspace_id: str, req: MergeRequest):
    return entity_resolution_engine.merge_entities(
        workspace_id=workspace_id,
        primary_entity_id=req.primary_entity_id,
        duplicate_entity_id=req.duplicate_entity_id,
        match_probability=req.match_probability,
    )


@app.post("/api/workspaces/{workspace_id}/entity-resolution/unmerge/{merge_id}")
@app.post("/api/v2/workspaces/{workspace_id}/entity-resolution/unmerge/{merge_id}")
def unmerge_entity_endpoint(workspace_id: str, merge_id: str):
    return entity_resolution_engine.unmerge_entity(workspace_id=workspace_id, merge_id=merge_id)


# Graph & Spatiotemporal
@app.get("/api/workspaces/{workspace_id}/graph")
@app.get("/api/v2/workspaces/{workspace_id}/graph")
def get_workspace_graph(
    workspace_id: str,
    as_of_time: Optional[str] = None,
    hide_shared_infra: bool = False,
    include_staged: bool = False,
):
    graph = graph_engine.analyze_workspace_graph(
        workspace_id=workspace_id,
        as_of_time=as_of_time,
        hide_shared_infra=hide_shared_infra,
        include_staged=include_staged,
    )
    for edge in graph.get("edges", []):
        if "source" not in edge:
            edge["source"] = edge.get("subject_entity_id")
        if "target" not in edge:
            edge["target"] = edge.get("object_entity_id")
        if "schema" not in edge:
            edge["schema"] = edge.get("predicate", "RELATED")
        if "weight" not in edge:
            edge["weight"] = edge.get("ief_edge_weight", 1.0)
    for node in graph.get("nodes", []):
        if "label" not in node:
            node["label"] = node.get("display_label") or node.get("canonical_value")
        if "schema" not in node:
            node["schema"] = node.get("ftm_schema")
    return graph


@app.get("/api/workspaces/{workspace_id}/geospatial")
@app.get("/api/v2/workspaces/{workspace_id}/geospatial")
def get_geospatial_clusters(workspace_id: str):
    return spatiotemporal_engine.get_geospatial_clusters(workspace_id)


@app.get("/api/workspaces/{workspace_id}/timeline")
@app.get("/api/v2/workspaces/{workspace_id}/timeline")
def get_timeline_bursts(workspace_id: str):
    return spatiotemporal_engine.get_timeline_burst_analysis(workspace_id)


@app.get("/api/workspaces/{workspace_id}/evidence")
@app.get("/api/v2/workspaces/{workspace_id}/evidence")
def list_evidence(workspace_id: str, limit: int = 500):
    return db.list_evidence(workspace_id=workspace_id, limit=limit)


# Search, AI Assistant & Reports
@app.get("/api/workspaces/{workspace_id}/search")
@app.get("/api/v2/workspaces/{workspace_id}/search")
def search_workspace(
    workspace_id: str,
    q: str = Query(...),
    mode: str = "hybrid_rrf",
    limit: int = 50,
):
    return hybrid_search_engine.hybrid_search(
        workspace_id=workspace_id, query=q, mode=mode, limit=limit
    )


@app.post("/api/ai/query")
@app.post("/api/v2/ai/query")
def query_ai_assistant(req: AIQueryRequest):
    return graphrag_assistant.compile_graphrag_report(req.workspace_id, req.query)


@app.post("/api/reports/generate")
@app.post("/api/v2/reports/generate")
def generate_report(req: ReportGenerateRequest):
    return graphrag_assistant.generate_and_save_report(
        workspace_id=req.workspace_id,
        title=req.title,
        query=req.query,
        report_type=req.report_type,
        tlp_marking=req.tlp_marking,
    )


@app.get("/api/workspaces/{workspace_id}/reports")
@app.get("/api/v2/workspaces/{workspace_id}/reports")
def list_reports(workspace_id: str):
    return db.list_reports(workspace_id)


# Exporters
@app.get("/api/workspaces/{workspace_id}/export")
@app.get("/api/v2/workspaces/{workspace_id}/export")
def export_workspace(workspace_id: str, format: str = Query("json")):
    fmt = format.lower().strip()
    if fmt == "csv":
        data = export_workspace_csv(workspace_id)
        return Response(content=data, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={workspace_id}.csv"})
    elif fmt == "stix":
        data = export_workspace_stix(workspace_id)
        return JSONResponse(content=data)
    elif fmt == "ftm":
        data = export_workspace_ftm(workspace_id)
        return PlainTextResponse(content=data, headers={"Content-Disposition": f"attachment; filename={workspace_id}.ftm.jsonl"})
    elif fmt == "prov":
        data = export_workspace_prov(workspace_id)
        return JSONResponse(content=data)
    else:
        # Default JSON
        data = export_workspace_json(workspace_id)
        return JSONResponse(content=data)


# Connectors, Tasks, Settings & Audit Logs
@app.get("/api/connectors")
@app.get("/api/v2/connectors")
def list_connectors():
    return db.get_connectors()


@app.put("/api/connectors/{connector_id}")
@app.put("/api/v2/connectors/{connector_id}")
def update_connector_config(connector_id: str, req: ConnectorUpdateRequest):
    updated = db.update_connector(
        connector_id=connector_id,
        enabled=req.enabled,
        plaintext_api_key=req.plaintext_api_key,
        rate_limit_rpm=req.rate_limit_rpm,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Connector not found")
    return {"status": "UPDATED", "connector_id": connector_id}


@app.get("/api/tasks")
@app.get("/api/v2/tasks")
def list_tasks(workspace_id: Optional[str] = None, limit: int = 50):
    return db.list_tasks(workspace_id=workspace_id, limit=limit)


@app.get("/api/settings")
@app.get("/api/v2/settings")
def get_settings():
    settings = db.get_settings()
    audit_entries = db.get_audit_logs(limit=100)
    is_valid, count, msg = HashChainedAuditLogger.verify_chain(audit_entries)
    return {
        "settings": settings,
        "audit_integrity": {
            "is_valid": is_valid,
            "entries_verified": count,
            "status_message": msg,
        },
    }


@app.put("/api/settings")
@app.put("/api/v2/settings")
def update_settings(req: SettingsUpdateRequest):
    for k, v in req.settings.items():
        db.set_setting(k, v)
    return {"status": "UPDATED", "settings": db.get_settings()}


@app.get("/api/audit-logs")
@app.get("/api/v2/audit-logs")
def get_audit_logs(limit: int = 100):
    return db.get_audit_logs(limit=limit)


# -----------------------------------------------------------------------------
# Frontend Workstation API Convenience Endpoints
# -----------------------------------------------------------------------------

@app.get("/api/workspaces/{workspace_id}/dashboard")
def get_workspace_dashboard(workspace_id: str):
    entities = db.list_entities(workspace_id, limit=1000)
    claims = db.list_claims(workspace_id, limit=1000)
    evidence = db.list_evidence(workspace_id, limit=10)
    staged = [e for e in entities if e.get("is_staged")]
    active = [e for e in entities if not e.get("is_staged")]

    top_hubs = sorted(active, key=lambda x: x.get("ief_pagerank", 0.0), reverse=True)[:5]
    hubs_data = [
        {
            "label": h.get("display_label") or h.get("canonical_value"),
            "canonical_value": h.get("canonical_value"),
            "schema": h.get("ftm_schema"),
            "pagerank": h.get("ief_pagerank", 0.0),
            "degree": int(h.get("degree_centrality", 0)),
        }
        for h in top_hubs
    ]

    latest_ev = [
        {
            "id": ev["id"],
            "source_name": ev.get("source_name", "N/A"),
            "admiralty_code": f"{ev.get('admiralty_reliability', 'B')}{ev.get('admiralty_credibility', 2)}",
            "title": ev.get("title", ""),
            "observed_at": ev.get("observed_at", ""),
        }
        for ev in evidence
    ]

    conflicts = [c for c in claims if c.get("sl_disbelief", 0.0) >= 0.25]

    return {
        "entities_count": len(active),
        "claims_count": len(claims),
        "staged_count": len(staged),
        "evidence_count": len(db.list_evidence(workspace_id, limit=10000)),
        "contradiction_alerts_count": len(conflicts),
        "top_hubs": hubs_data,
        "latest_evidence": latest_ev,
    }


@app.get("/api/workspaces/{workspace_id}/staging")
def get_staging_buffer(workspace_id: str):
    entities = db.list_entities(workspace_id, limit=1000)
    return [e for e in entities if e.get("is_staged")]


@app.post("/api/workspaces/{workspace_id}/staging/promote-high-risk")
def promote_high_risk_endpoint(workspace_id: str, threshold: int = 50):
    promoted = db.promote_staged_entities(workspace_id=workspace_id, min_risk=threshold)
    return {"status": "PROMOTED", "promoted_count": promoted}


@app.post("/api/workspaces/{workspace_id}/forensics/paste")
def forensics_paste(workspace_id: str, body: Dict[str, Any] = Body(...)):
    text = body.get("text", "")
    res = extractor.extract_all(text)
    ev = db.add_evidence(
        workspace_id=workspace_id,
        connector_id="local_doc_forensics",
        upstream_lineage_family="LocalAnalyst",
        source_name="Document Text Paste",
        source_url="local://paste",
        title="Advisory Paste Analysis",
        summary_text="Extracted observables from pasted text",
        raw_payload={"extracted": res},
        simhash_64=res.get("simhash_64", "0000000000000000"),
    )
    observables = []
    for schema, values in res.items():
        if schema in ("simhash_64", "DGA_Domains"):
            continue
        for val in values:
            observables.append(val)
            db.upsert_entity(workspace_id=workspace_id, ftm_schema=schema, raw_value=val)
    return {
        "status": "EXTRACTED",
        "refanged_text": refang(text),
        "observables": observables,
        "extracted": res,
        "evidence_id": ev["id"],
    }


@app.post("/api/workspaces/{workspace_id}/forensics/upload")
async def forensics_upload(workspace_id: str, file: UploadFile = File(...)):
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 25 MB limit")
    analysis = analyze_file(file.filename, contents)
    ev = db.add_evidence(
        workspace_id=workspace_id,
        connector_id="local_doc_forensics",
        upstream_lineage_family="LocalFile",
        source_name=f"File: {file.filename}",
        source_url=f"local://file/{file.filename}",
        title=f"Forensic Analysis of {file.filename}",
        summary_text=f"Analyzed {analysis.get('file_type')} file",
        raw_payload=analysis,
        simhash_64=analysis.get("simhash_64", "0000000000000000"),
    )
    return {"status": "ANALYZED", "filename": file.filename, "evidence_id": ev["id"], "analysis": analysis}


@app.get("/api/workspaces/{workspace_id}/resolution/candidates")
def get_er_candidates(workspace_id: str):
    data = entity_resolution_engine.evaluate_candidates(workspace_id=workspace_id)
    raw_candidates = data.get("candidates", [])
    enriched = []
    for c in raw_candidates:
        enriched.append({
            **c,
            "entity_a": {"id": c["entity_a_id"], "label": c["entity_a_label"], "schema": c["entity_a_schema"]},
            "entity_b": {"id": c["entity_b_id"], "label": c["entity_b_label"], "schema": c["entity_b_schema"]},
            "waterfall": {"factors": c.get("waterfall_factors", [])},
            "fs_log2_weight": c.get("fellegi_sunter_log2_weight", 0.0),
        })
    return enriched


@app.get("/api/workspaces/{workspace_id}/resolution/ledger")
def get_er_ledger(workspace_id: str):
    history = entity_resolution_engine.get_merge_ledger(workspace_id=workspace_id)
    return [
        {
            "merge_id": h["id"],
            "winner_id": h["winner_entity_id"],
            "absorbed_id": h["absorbed_entity_id"],
            "match_probability": h["match_probability"],
            "status": "UNMERGED" if h.get("is_reverted") else "MERGED",
            "merged_at": h.get("merged_at"),
        }
        for h in history
    ]


@app.post("/api/workspaces/{workspace_id}/resolution/merge")
def merge_resolution_endpoint(workspace_id: str, body: Dict[str, Any] = Body(...)):
    primary = body.get("winner_id") or body.get("primary_entity_id")
    dup = body.get("absorbed_id") or body.get("duplicate_entity_id")
    prob = float(body.get("match_probability", 0.95))
    res = entity_resolution_engine.merge_entities(
        workspace_id=workspace_id,
        primary_entity_id=primary,
        duplicate_entity_id=dup,
        match_probability=prob,
    )
    return res


@app.post("/api/workspaces/{workspace_id}/resolution/unmerge")
def unmerge_resolution_endpoint(workspace_id: str, body: Dict[str, Any] = Body(...)):
    merge_id = body.get("merge_id")
    return entity_resolution_engine.unmerge_entity(workspace_id=workspace_id, merge_id=merge_id)


@app.get("/api/workspaces/{workspace_id}/graph/node/{entity_id}")
def get_graph_node_details(workspace_id: str, entity_id: str):
    ent = db.get_entity(entity_id)
    if not ent:
        raise HTTPException(status_code=404, detail="Entity not found")
    adj = graph_engine.analyze_workspace_graph(workspace_id)
    predicted = []
    for link in adj.get("predicted_links", []):
        u = link.get("u")
        v = link.get("v")
        if u == entity_id or v == entity_id:
            other = v if u == entity_id else u
            o_ent = db.get_entity(other)
            o_label = o_ent.get("display_label") if o_ent else other
            predicted.append({
                "target_id": other,
                "target_label": o_label,
                "score": link.get("score", 0.0),
            })
    return {
        **ent,
        "belief_score": ent.get("sl_belief", 0.75),
        "disbelief_score": ent.get("sl_disbelief", 0.0),
        "uncertainty_score": ent.get("sl_uncertainty", 0.25),
        "pagerank": ent.get("ief_pagerank", 0.0),
        "predicted_missing_links": predicted[:5],
    }


@app.post("/api/workspaces/{workspace_id}/collect")
async def collect_endpoint(workspace_id: str, body: Dict[str, Any] = Body(...)):
    target = body.get("target") or body.get("target_query")
    schema = body.get("schema_type") or body.get("target_type")
    depth = int(body.get("depth", 1))
    connectors = body.get("connectors")
    return await orchestrator.run_playbook(
        workspace_id=workspace_id,
        target_query=target,
        target_type=schema,
        connectors=connectors,
        pivot_depth=depth,
    )


@app.post("/api/workspaces/{workspace_id}/ai/query")
def ai_query_ws(workspace_id: str, body: Dict[str, Any] = Body(...)):
    query = body.get("query", "")
    res = graphrag_assistant.compile_graphrag_report(workspace_id, query)
    res["response"] = res.get("answer_markdown", "")
    return res


@app.post("/api/workspaces/{workspace_id}/ai/report")
def ai_report_ws(workspace_id: str, body: Dict[str, Any] = Body(...)):
    title = body.get("title", "Investigation Report")
    query = body.get("query", "Comprehensive Findings")
    return graphrag_assistant.generate_and_save_report(
        workspace_id=workspace_id,
        title=title,
        query=query,
    )


@app.get("/api/workspaces/{workspace_id}/provenance")
def get_provenance_ledger(workspace_id: str):
    return db.list_evidence(workspace_id=workspace_id, limit=500)


@app.get("/api/export/{workspace_id}/{format_type}")
def export_alias(workspace_id: str, format_type: str):
    return export_workspace(workspace_id=workspace_id, format=format_type)


@app.get("/api/search")
def search_alias(q: str = Query(...), workspace_id: Optional[str] = Query(None), mode: str = "hybrid_rrf", limit: int = 50):
    if not workspace_id:
        workspaces = db.list_workspaces()
        if not workspaces:
            return {"results": []}
        workspace_id = workspaces[0]["id"]
    results = hybrid_search_engine.hybrid_search(workspace_id=workspace_id, query=q, mode=mode, limit=limit)
    return {"results": results}


@app.get("/api/vault")
def get_vault():
    conns = db.get_connectors()
    return [
        {
            "name": c["connector_id"],
            "category": c["category"],
            "requires_key": bool(c["requires_api_key"]),
            "masked_key": "********" if c.get("encrypted_api_key") else "",
            "rate_limit_rpm": c.get("rate_limit_rpm", 60),
            "circuit_breaker_status": c.get("circuit_state", "READY"),
        }
        for c in conns
    ]


@app.post("/api/vault")
def update_vault(body: Dict[str, Any] = Body(...)):
    name = body.get("connector_name")
    key = body.get("api_key")
    db.update_connector(connector_id=name, plaintext_api_key=key)
    return {"status": "SAVED", "connector_name": name}


@app.post("/api/settings")
def update_settings_post(body: Dict[str, Any] = Body(...)):
    for k, v in body.items():
        db.set_setting(k, str(v))
    return {"status": "UPDATED", "settings": db.get_settings()}


# -----------------------------------------------------------------------------
# V3.0 CRUCIX SWEEP-DELTA ENDPOINTS
# -----------------------------------------------------------------------------

class SweepRunRequest(BaseModel):
    investigation_id: str = "default"
    bbox: Optional[List[float]] = None  # [min_lon, min_lat, max_lon, max_lat]


@app.post("/api/v1/sweeps/run")
async def run_sweep_endpoint(req: SweepRunRequest = Body(default_factory=SweepRunRequest)):
    bbox_tuple = tuple(req.bbox) if req.bbox and len(req.bbox) == 4 else None
    result = sweep_delta_engine.run_sweep(
        investigation_id=req.investigation_id,
        bbox=bbox_tuple,
    )
    # Broadcast to SSE subscribers
    await alert_engine.broadcast_event("SWEEP_COMPLETED", {
        "sweep_id": result["sweep_id"],
        "escalation_score": result["escalation_score"],
        "deltas_count": len(result.get("deltas", [])),
        "stats": result.get("stats", {}),
    })
    return result


@app.get("/api/v1/sweeps/latest")
def get_latest_sweep_endpoint():
    latest = db.get_latest_sweep_run()
    if not latest:
        # Run an initial bootstrap sweep
        return sweep_delta_engine.run_sweep()
    sweep_id = latest["sweep_id"]
    deltas = db.get_sweep_deltas(sweep_id)
    return {
        **latest,
        "deltas": deltas,
    }


@app.get("/api/v1/sweeps/{sweep_id}/deltas")
def get_sweep_deltas_endpoint(sweep_id: str, severity: Optional[str] = None):
    return db.get_sweep_deltas(sweep_id, severity=severity)


@app.get("/api/v1/sweeps/latest/briefing")
def get_latest_sweep_briefing_endpoint():
    latest = db.get_latest_sweep_run()
    if not latest:
        sweep_res = sweep_delta_engine.run_sweep()
        sweep_id = sweep_res["sweep_id"]
    else:
        sweep_id = latest["sweep_id"]

    briefing = graphrag_assistant.generate_sweep_briefing(sweep_id)
    return briefing


@app.get("/api/v1/sweeps/auto/status")
def get_auto_sweep_status():
    return auto_sweeper_state


@app.post("/api/v1/sweeps/auto/toggle")
def toggle_auto_sweep(enabled: Optional[bool] = Query(None)):
    if enabled is not None:
        auto_sweeper_state["enabled"] = enabled
    else:
        auto_sweeper_state["enabled"] = not auto_sweeper_state["enabled"]
    return auto_sweeper_state


# -----------------------------------------------------------------------------
# V3.0 GEOSPATIAL & KINETIC LAYERS ENDPOINTS
# -----------------------------------------------------------------------------

@app.get("/api/v1/geospatial/layers")
def get_geospatial_layers(
    layers: Optional[str] = Query(None, description="Comma-separated layer types, e.g. AIRCRAFT,VESSEL,SATELLITE,EARTHQUAKE,CAMERA"),
    since: Optional[str] = Query(None),
    limit: int = Query(2000, le=5000),
):
    layer_types = [l.strip().upper() for l in layers.split(",")] if layers else None
    tracks = db.query_geo_tracks(layer_types=layer_types, since_iso=since, limit=limit)

    # If tracks is empty, trigger a quick sweep to populate
    if not tracks:
        sweep_delta_engine.run_sweep()
        tracks = db.query_geo_tracks(layer_types=layer_types, since_iso=since, limit=limit)

    features = []
    for t in tracks:
        props = {
            "track_id": t.get("track_id"),
            "entity_id": t.get("entity_id"),
            "layer_type": t.get("layer_type"),
            "display_label": t.get("display_label"),
            "callsign_or_name": t.get("callsign_or_name"),
            "altitude_m": t.get("altitude_m"),
            "heading": t.get("heading"),
            "speed_kts": t.get("speed_kts"),
            "telemetry_status": t.get("telemetry_status"),
            "source_network": t.get("source_network"),
            "is_military": t.get("is_military"),
            "is_sanctioned": t.get("is_sanctioned"),
            "risk_score": t.get("risk_score"),
            "observed_at": t.get("observed_at"),
            "metadata": t.get("metadata", {}),
        }
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [t.get("lon"), t.get("lat")],
            },
            "properties": props,
        })

    # Add GPS interference zones if aircraft present
    gps_zones = spatiotemporal_engine.compute_gps_interference_zones(tracks)
    for z in gps_zones:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": z["polygon"],
            },
            "properties": {
                "layer_type": "GPS_JAMMING",
                "display_label": f"GPS Interference Zone ({z['severity']})",
                "severity": z["severity"],
                "aircraft_count": z["aircraft_count"],
                "avg_nacp": z["avg_nacp"],
                "telemetry_status": "DERIVED_INFERENCE",
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "count": len(features),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


@app.get("/api/v1/geospatial/replay")
def get_geospatial_replay(
    timestamp_iso: str = Query(..., description="Target timestamp ISO"),
    window_minutes: int = Query(30, ge=1, le=1440),
):
    try:
        target_dt = datetime.datetime.fromisoformat(timestamp_iso.replace("Z", "+00:00"))
    except Exception:
        target_dt = datetime.datetime.now(datetime.timezone.utc)

    start_dt = target_dt - datetime.timedelta(minutes=window_minutes)
    end_dt = target_dt + datetime.timedelta(minutes=window_minutes)

    tracks = db.query_geo_tracks(
        since_iso=start_dt.isoformat(),
        until_iso=end_dt.isoformat(),
        limit=3000,
    )
    features = []
    for t in tracks:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [t.get("lon"), t.get("lat")],
            },
            "properties": {
                "track_id": t.get("track_id"),
                "entity_id": t.get("entity_id"),
                "layer_type": t.get("layer_type"),
                "display_label": t.get("display_label"),
                "callsign_or_name": t.get("callsign_or_name"),
                "telemetry_status": "HISTORICAL",
                "speed_kts": t.get("speed_kts"),
                "altitude_m": t.get("altitude_m"),
                "heading": t.get("heading"),
                "is_sanctioned": t.get("is_sanctioned"),
                "is_military": t.get("is_military"),
                "observed_at": t.get("observed_at"),
                "metadata": t.get("metadata", {}),
            },
        })
    return {
        "type": "FeatureCollection",
        "features": features,
        "replay_timestamp": target_dt.isoformat(),
        "window_minutes": window_minutes,
        "count": len(features),
    }


@app.get("/api/v1/geospatial/satellites")
def get_satellites_endpoint(timestamp_iso: Optional[str] = None):
    target_dt = None
    if timestamp_iso:
        try:
            target_dt = datetime.datetime.fromisoformat(timestamp_iso.replace("Z", "+00:00"))
        except Exception:
            pass
    return satellite_adapter.fetch_live_satellites(target_time=target_dt)


@app.get("/api/v1/geospatial/proximity")
def get_geospatial_proximity(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(50.0, ge=1.0, le=500.0),
    layers: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
):
    """Argos Atlas-style spatial proximity correlation:
    Discovers all kinetic assets, infrastructure, and cameras within radius_km.
    """
    layer_types = [l.strip().upper() for l in layers.split(",")] if layers else None
    proximate = spatiotemporal_engine.find_proximate_assets(
        center_lat=lat,
        center_lon=lon,
        radius_km=radius_km,
        layer_types=layer_types,
        limit=limit,
    )
    return {
        "center": {"lat": lat, "lon": lon},
        "radius_km": radius_km,
        "count": len(proximate),
        "proximate_assets": proximate,
    }


# -----------------------------------------------------------------------------
# V3.0 GEOFENCES & REAL-TIME SSE ENDPOINTS
# -----------------------------------------------------------------------------

class GeofenceCreateRequest(BaseModel):
    name: str
    polygon_geojson: Any  # Dict or List or String
    monitored_layers: Optional[List[str]] = None
    min_severity: str = "MEDIUM"
    notify_channels: Optional[List[str]] = None


@app.post("/api/v1/geofences")
def create_geofence_endpoint(req: GeofenceCreateRequest):
    poly_str = json.dumps(req.polygon_geojson) if not isinstance(req.polygon_geojson, str) else req.polygon_geojson
    gid = db.create_geofence(
        name=req.name,
        polygon_geojson=poly_str,
        monitored_layers=req.monitored_layers,
        min_severity=req.min_severity,
        notify_channels=req.notify_channels,
    )
    return {"geofence_id": gid, "name": req.name, "status": "CREATED"}


@app.get("/api/v1/geofences")
def list_geofences_endpoint(active_only: bool = True):
    return db.list_geofences(active_only=active_only)


@app.delete("/api/v1/geofences/{geofence_id}")
def delete_geofence_endpoint(geofence_id: str):
    ok = db.delete_geofence(geofence_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Geofence not found")
    return {"status": "DELETED", "geofence_id": geofence_id}


@app.get("/api/v1/stream")
async def sse_event_stream():
    return StreamingResponse(
        alert_engine.subscribe_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# -----------------------------------------------------------------------------
# V3.0 PRIVACY-PRESERVING VISUAL INTELLIGENCE STUDIO ENDPOINTS
# -----------------------------------------------------------------------------

class VisualAnalyzeJsonRequest(BaseModel):
    image_b64: str
    filename: str = "uploaded_asset.jpg"
    investigation_id: str = "default"
    blur_bystanders: bool = True


@app.post("/api/v1/visual/analyze")
async def analyze_visual_asset(
    request: Request,
    blur_bystanders: bool = Query(True),
):
    import base64
    content_type = request.headers.get("content-type", "")
    img_bytes = b""
    filename = "unknown.jpg"
    inv_id = "default"
    blur = blur_bystanders

    if "application/json" in content_type:
        body = await request.json()
        b64_str = body.get("image_b64", "")
        if "," in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        img_bytes = base64.b64decode(b64_str)
        filename = body.get("filename", "upload.jpg")
        inv_id = body.get("investigation_id", "default")
        if "blur_bystanders" in body:
            blur = bool(body["blur_bystanders"])
    else:
        form = await request.form()
        uploaded_file = form.get("file")
        if uploaded_file and hasattr(uploaded_file, "read"):
            img_bytes = await uploaded_file.read()
            filename = getattr(uploaded_file, "filename", "upload.jpg") or "upload.jpg"
        elif "image_b64" in form:
            b64_str = form.get("image_b64", "")
            if "," in b64_str:
                b64_str = b64_str.split(",", 1)[1]
            img_bytes = base64.b64decode(b64_str)
            filename = form.get("filename", "upload.jpg")
        if "blur_bystanders" in form:
            blur = str(form["blur_bystanders"]).lower() in ("true", "1")
        if "investigation_id" in form:
            inv_id = str(form["investigation_id"])

    if len(img_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty image data.")

    # 1. Media Forensics (EXIF, GPS, C2PA, Hashes)
    forensics = media_forensics_engine.parse_image_forensics(img_bytes, filename=filename)

    # 2. Vision Engine (YuNet Face Detection, Sharpness Quality Gate, Mandatory Default Bystander Blurring)
    vision_res = vision_engine.analyze_image(img_bytes, blur_bystanders=blur)

    # 3. Near-duplicate search
    phash_hex = forensics.get("phash_64", "")
    similar_assets = db.find_similar_visual_assets(phash_hex, max_hamming=10) if phash_hex else []

    # 4. Save to visual_assets table
    asset_record = {
        "investigation_id": inv_id,
        "filename": filename,
        "sha256_hash": forensics.get("sha256_hash", ""),
        "phash_64": forensics.get("phash_64", ""),
        "dhash_64": forensics.get("dhash_64", ""),
        "ahash_64": forensics.get("ahash_64", ""),
        "width": vision_res.get("dimensions", [0, 0])[0],
        "height": vision_res.get("dimensions", [0, 0])[1],
        "laplacian_sharpness": vision_res.get("laplacian_sharpness", 0.0),
        "quality_grade": vision_res.get("quality_grade", "MODERATE"),
        "faces_detected": vision_res.get("faces_detected", 0),
        "bystanders_blurred": blur,
        "exif_json": forensics.get("exif", {}),
        "c2pa_json": forensics.get("c2pa", {}),
        "lat": forensics.get("gps", {}).get("lat") if forensics.get("gps") else None,
        "lon": forensics.get("gps", {}).get("lon") if forensics.get("gps") else None,
        "redacted_image_b64": vision_res.get("processed_image_b64", ""),
    }
    asset_id = db.save_visual_asset(asset_record)

    return {
        "asset_id": asset_id,
        "filename": filename,
        "forensics": forensics,
        "vision": {
            "faces_detected": vision_res.get("faces_detected", 0),
            "laplacian_sharpness": vision_res.get("laplacian_sharpness", 0.0),
            "quality_grade": vision_res.get("quality_grade", "MODERATE"),
            "quality_gate_passed": vision_res.get("quality_gate_passed", False),
            "bystanders_blurred": blur,
            "face_crops": vision_res.get("faces", []),
        },
        "similar_assets_count": len(similar_assets),
        "similar_assets": similar_assets[:5],
        "redacted_image_b64": vision_res.get("processed_image_b64", ""),
    }


class GalleryEnrollRequest(BaseModel):
    image_b64: str
    subject_name: str
    consent_purpose: str
    consent_attestation: bool
    expiration_days: int = 90


@app.post("/api/v1/visual/gallery/enroll")
def enroll_consented_gallery_subject(req: GalleryEnrollRequest):
    import base64
    if not req.consent_attestation:
        raise HTTPException(
            status_code=403,
            detail="Biometric enrollment rejected: Explicit consent attestation is legally mandatory.",
        )
    b64_str = req.image_b64.split(",", 1)[1] if "," in req.image_b64 else req.image_b64
    img_bytes = base64.b64decode(b64_str)
    try:
        result = consent_guard.enroll_subject(
            image_bytes=img_bytes,
            subject_name=req.subject_name,
            consent_purpose=req.consent_purpose,
            consent_attestation=req.consent_attestation,
            expiration_days=req.expiration_days,
        )
        return result
    except ConsentViolationError as cve:
        raise HTTPException(status_code=403, detail=str(cve))
    except QualityGateRejectionError as qre:
        raise HTTPException(status_code=422, detail=str(qre))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class VerifyProbeRequest(BaseModel):
    probe_image_b64: str
    consent_reason: str
    bbox: Optional[List[int]] = None


@app.post("/api/v1/visual/verify")
def verify_visual_probe(req: VerifyProbeRequest):
    import base64
    if not req.consent_reason or not req.consent_reason.strip():
        raise HTTPException(
            status_code=403,
            detail="Verification rejected: consent_reason is mandatory. Unconsented stranger matching is architecturally blocked.",
        )
    b64_str = req.probe_image_b64.split(",", 1)[1] if "," in req.probe_image_b64 else req.probe_image_b64
    img_bytes = base64.b64decode(b64_str)
    try:
        result = consent_guard.verify_against_gallery(
            probe_image_bytes=img_bytes,
            consent_reason=req.consent_reason,
            bbox=req.bbox,
        )
        return result
    except ConsentViolationError as cve:
        raise HTTPException(status_code=403, detail=str(cve))
    except QualityGateRejectionError as qre:
        raise HTTPException(status_code=422, detail=str(qre))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/visual/assets")
def list_visual_assets_endpoint(limit: int = 100):
    return db.list_visual_assets(limit=limit)


@app.get("/api/v1/visual/assets/{asset_id}")
def get_visual_asset_endpoint(asset_id: str):
    asset = db.get_visual_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Visual asset not found")
    return asset


@app.get("/api/v1/visual/gallery")
def list_gallery_subjects_endpoint(non_expired_only: bool = True):
    return db.list_consented_faces(non_expired_only=non_expired_only)


@app.delete("/api/v1/visual/gallery/{gallery_id}")
def revoke_gallery_subject_endpoint(gallery_id: str):
    with db.get_connection() as conn:
        cur = conn.execute("DELETE FROM consented_face_gallery WHERE gallery_id = ?;", (gallery_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Subject not found")
    db.append_audit_log(action="CONSENT_GALLERY_REVOKE", details=f"Revoked consented gallery ID: {gallery_id}")
    return {"status": "REVOKED", "gallery_id": gallery_id}


# -----------------------------------------------------------------------------
# V3.0 SANCTIONS & CAMERAS LOOKUP ENDPOINTS
# -----------------------------------------------------------------------------

@app.get("/api/v1/sanctions/lookup")
def lookup_sanctions(
    mmsi: Optional[str] = None,
    imo: Optional[str] = None,
    icao24: Optional[str] = None,
    tail_number: Optional[str] = None,
    name: Optional[str] = None,
):
    match = sanctions_loader.match_asset(
        mmsi=mmsi,
        imo=imo,
        icao24=icao24,
        tail_number=tail_number,
        name=name,
    )
    return {"matched": match is not None, "record": match}


@app.get("/api/v1/cameras")
def get_cameras_endpoint():
    cameras = camera_adapter.fetch_cameras()
    return {"cameras": cameras, "count": len(cameras)}


# -----------------------------------------------------------------------------
# Static UI Mount
# -----------------------------------------------------------------------------

assets_path = FRONTEND_DIR / "assets"
if assets_path.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")


@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>LocalOSINT v2.0 Workstation</h1><p>Frontend loading...</p>")
