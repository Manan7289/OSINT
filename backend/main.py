"""backend/main.py - FastAPI Application, REST/WebSocket API Routers & Static Workstation Server.

M09: FastAPI REST/WebSocket Server & Multi-Format Export Engine.
"""

from __future__ import annotations

import datetime
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Body, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.ai.assistant import graphrag_assistant
from backend.ai.search_rrf import hybrid_search_engine
from backend.collectors.orchestrator import orchestrator
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
from backend.nlp.extractor import extractor
from backend.nlp.forensics import analyze_file


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_demo_workspace_if_empty()
    yield
    await orchestrator.close()


app = FastAPI(
    title="LocalOSINT v2.0 Analyst Workstation",
    description="Production-grade local-first OSINT, Bitemporal Property Graph & Entity Resolution Platform",
    version="2.0.0",
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
def get_health() -> Dict[str, Any]:
    conns = db.get_connectors()
    workspaces = db.list_workspaces()
    ready_count = sum(1 for c in conns if c["enabled"] and (not c["requires_api_key"] or c["has_api_key"]))

    return {
        "status": "healthy",
        "version": "2.0.0",
        "database_wal": True,
        "onnx_available": True,
        "workspace_count": len(workspaces),
        "connectors_total": len(conns),
        "connectors_ready": ready_count,
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
    return graph_engine.analyze_workspace_graph(
        workspace_id=workspace_id,
        as_of_time=as_of_time,
        hide_shared_infra=hide_shared_infra,
        include_staged=include_staged,
    )


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
