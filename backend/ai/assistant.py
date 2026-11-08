"""backend/ai/assistant.py - GraphRAG Subgraph Compiler, Ollama Client & Post-Generation Citation Validator.

M08: Hybrid RRF Search (FTS5 BM25 + INT8 Vectors) & GraphRAG Citation Validator.
"""

from __future__ import annotations

import datetime
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import urllib.request
import urllib.error

from backend.ai.search_rrf import hybrid_search_engine
from backend.core.database import DatabaseManager, db
from backend.core.graph_analytics import graph_engine


def validate_citation_entailment(
    text: str, valid_evidence_ids: Set[str]
) -> Dict[str, Any]:
    """Validates every [ev_xxxx] citation in the generated response against workspace evidence artifacts."""
    pattern = re.compile(r"\[(ev_[a-zA-Z0-9_-]+)\]")
    found_citations = pattern.findall(text)

    valid = []
    hallucinated = []

    for cid in found_citations:
        if cid in valid_evidence_ids:
            valid.append(cid)
        else:
            hallucinated.append(cid)

    total = len(found_citations)
    score = (len(valid) / total) if total > 0 else 1.0

    return {
        "total_citations": total,
        "valid_citations": sorted(list(set(valid))),
        "hallucinated_citations": sorted(list(set(hallucinated))),
        "citation_integrity_score": round(score, 4),
    }


def validate_citations(
    text: str, valid_citation_ids: Set[str] | list[str]
) -> Tuple[bool, str, Dict[str, Any]]:
    """Strict Citation Enforcement Validator.
    Every factual sentence must carry a valid [ev_...], [PROV:...], or [DELTA:...] citation.
    Any uncited or hallucinated factual claim is stripped.
    Enforces is_valid = (valid_ratio == 1.0 and len(stripped_sentences) == 0).
    """
    valid_set = set(valid_citation_ids)
    pattern = re.compile(r"\[([a-zA-Z0-9_:-]+)\]")

    valid_citations = []
    hallucinated_citations = []
    stripped_sentences = []
    preserved_sentences = []

    lines = text.split("\n")
    for line in lines:
        stripped_line = line.strip()
        if not stripped_line:
            preserved_sentences.append(line)
            continue

        # Headers, divider, italics notes
        if stripped_line.startswith("#") or (stripped_line.startswith("*") and not stripped_line.startswith("*-")):
            preserved_sentences.append(line)
            continue

        raw_cites = pattern.findall(line)
        # Filter to citation identifiers (ev_*, PROV:*, DELTA:*)
        cites = [
            c for c in raw_cites
            if c.startswith("ev_") or c.startswith("PROV:") or c.startswith("DELTA:")
        ]

        if not cites:
            # Bullet point or factual sentence without citation
            if stripped_line.startswith("- ") or len(stripped_line.split()) > 4:
                stripped_sentences.append(line)
                continue
            else:
                preserved_sentences.append(line)
                continue

        line_has_hallucination = False
        for c in cites:
            if c in valid_set or c.endswith(":none"):
                valid_citations.append(c)
            else:
                hallucinated_citations.append(c)
                line_has_hallucination = True

        if line_has_hallucination:
            stripped_sentences.append(line)
        else:
            preserved_sentences.append(line)

    total_found = len(valid_citations) + len(hallucinated_citations)
    valid_ratio = (len(valid_citations) / total_found) if total_found > 0 else (1.0 if not stripped_sentences else 0.0)
    is_valid = (valid_ratio == 1.0 and len(stripped_sentences) == 0)
    cleaned_text = "\n".join(preserved_sentences)

    audit = {
        "is_valid": is_valid,
        "valid_ratio": round(valid_ratio, 4),
        "total_citations": total_found,
        "valid_citations": sorted(list(set(valid_citations))),
        "hallucinated_citations": sorted(list(set(hallucinated_citations))),
        "stripped_sentences_count": len(stripped_sentences),
        "stripped_sentences": stripped_sentences,
    }
    return is_valid, cleaned_text, audit


class GraphRAGAssistant:
    """Deterministic GraphRAG Subgraph Compiler with optional local Ollama LLM integration."""

    def __init__(self, database: DatabaseManager = db) -> None:
        self.db = database

    def compile_graphrag_report(
        self, workspace_id: str, query: str
    ) -> Dict[str, Any]:
        """Compiles an epistemically stratified intelligence synthesis from local subgraph knowledge."""
        # 1. Retrieve top matching entities and evidence via Hybrid RRF Search
        search_results = hybrid_search_engine.hybrid_search(
            workspace_id=workspace_id, query=query, mode="hybrid_rrf", limit=10
        )
        seed_entity_ids: Set[str] = set()
        for res in search_results:
            if res.get("record_kind") == "ENTITY":
                seed_entity_ids.add(res["record_id"])

        # 2. Extract active claims involving seed entities
        claims = self.db.list_claims(workspace_id=workspace_id, limit=500)
        seed_claims: List[Dict[str, Any]] = []
        for clm in claims:
            s_id = clm.get("subject_entity_id")
            o_id = clm.get("object_entity_id")
            if s_id in seed_entity_ids or o_id in seed_entity_ids or not seed_entity_ids:
                seed_claims.append(clm)

        # 3. Categorize claims by epistemic status
        facts = []
        inferences = []
        contradictions = []
        cited_evidence_ids: Set[str] = set()

        for clm in seed_claims:
            s_ent = self.db.get_entity(clm["subject_entity_id"])
            s_lbl = s_ent["display_label"] if s_ent else clm["subject_entity_id"]
            o_ent = self.db.get_entity(clm.get("object_entity_id", ""))
            o_lbl = o_ent["display_label"] if o_ent else (clm.get("object_literal") or "")
            pred = clm["predicate"]

            ev_ids = clm.get("evidence_ids", [])
            for eid in ev_ids:
                cited_evidence_ids.add(eid)
            cite_tag = f" [{' '.join(f'[{eid}]' for eid in ev_ids)}]" if ev_ids else ""

            status = clm.get("epistemic_status", "OBSERVED_FACT")
            disbelief = clm.get("sl_disbelief", 0.0)

            line = f"- **{s_lbl}** `{pred}` **{o_lbl}** (belief: {clm.get('sl_belief', 0.75):.2f}){cite_tag}"

            if disbelief >= 0.25 or status == "UNVERIFIED_CLAIM":
                contradictions.append(f"{line} *(Conflict/Disbelief: {disbelief:.2f})*")
            elif status in ("OBSERVED_FACT", "CORROBORATED_FACT"):
                facts.append(line)
            else:
                inferences.append(line)

        # 4. Fetch evidence details for Citation Audit
        evidence_records = {}
        for eid in cited_evidence_ids:
            ev = self.db.get_evidence(eid)
            if ev:
                evidence_records[eid] = ev

        # 5. Synthesize Epistemically Stratified Markdown
        sections = [
            f"# Intelligence Briefing: {query}",
            f"*Generated locally by LocalOSINT GraphRAG Engine for Workspace `{workspace_id}`*\n",
            "### 1. Observed & Corroborated Facts",
        ]
        if facts:
            sections.extend(facts[:15])
        else:
            sections.append("*No directly corroborated factual edges found for this query.*")

        sections.append("\n### 2. Graph-Derived Inferences & Hypotheses")
        if inferences:
            sections.extend(inferences[:10])
        else:
            sections.append("*No automated multi-hop inferences active for this target.*")

        sections.append("\n### 3. Contradictions, Disagreements & Investigation Gaps")
        if contradictions:
            sections.extend(contradictions[:10])
        else:
            sections.append("*No high-disbelief source contradictions detected.*")

        sections.append("\n### 4. Citation Verification Audit")
        if evidence_records:
            for eid, ev in sorted(evidence_records.items()):
                sections.append(
                    f"- `[{eid}]` **{ev['source_name']}** ({ev['upstream_lineage_family']}) — *\"{ev['title']}\"* [Admiralty: {ev['admiralty_reliability']}{ev['admiralty_credibility']}]"
                )
        else:
            sections.append("*No cryptographic evidence records attached.*")

        markdown_output = "\n".join(sections)

        # Validate citation entailment
        all_ws_evidence = {e["id"] for e in self.db.list_evidence(workspace_id=workspace_id)}
        audit = validate_citation_entailment(markdown_output, all_ws_evidence)

        return {
            "workspace_id": workspace_id,
            "query": query,
            "answer_markdown": markdown_output,
            "citation_audit": audit,
            "evidence_count": len(evidence_records),
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

    def generate_and_save_report(
        self,
        workspace_id: str,
        title: str,
        query: str,
        report_type: str = "COMPREHENSIVE",
        tlp_marking: str = "TLP:CLEAR",
    ) -> Dict[str, Any]:
        """Synthesizes an intelligence report and persists it to the reports table."""
        synthesis = self.compile_graphrag_report(workspace_id, query)
        created = self.db.create_report(
            workspace_id=workspace_id,
            title=title,
            content_markdown=synthesis["answer_markdown"],
            report_type=report_type,
            tlp_marking=tlp_marking,
            citation_audit=synthesis["citation_audit"],
            metadata={"query": query, "evidence_count": synthesis["evidence_count"]},
        )
        self.db.append_audit_log(
            "REPORT_GENERATED",
            f"Generated '{title}' ({report_type}, {tlp_marking}) with {synthesis['citation_audit']['total_citations']} citations",
            workspace_id,
        )
        return created

    def generate_sweep_briefing(self, sweep_id: str = "latest") -> Dict[str, Any]:
        """Synthesizes top deltas, sanctions matches, and geofence breaches into an executive Markdown SitRep."""
        if sweep_id == "latest":
            latest_run = self.db.get_latest_sweep_run() if hasattr(self.db, "get_latest_sweep_run") else None
            if not latest_run:
                return {
                    "sweep_id": "none",
                    "briefing_markdown": "# Executive Intelligence Briefing (SitRep)\n*No sweep records available. Run a collection sweep to populate.*",
                    "escalation_score": 0.0,
                    "deltas_count": 0,
                    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                }
            sweep_id = latest_run["sweep_id"]
            run_data = latest_run
        else:
            run_data = self.db.get_sweep_run(sweep_id) if hasattr(self.db, "get_sweep_run") else {}
            if not run_data:
                run_data = self.db.get_latest_sweep_run() if hasattr(self.db, "get_latest_sweep_run") else {}

        deltas = self.db.get_sweep_deltas(sweep_id) if hasattr(self.db, "get_sweep_deltas") else []

        sanctions = [d for d in deltas if d.get("delta_type") == "SANCTION_MATCH_DETECTED"]
        geofences = [d for d in deltas if d.get("delta_type") == "ENTERED_GEOFENCE"]
        escalations = [d for d in deltas if d.get("delta_type") == "ESCALATED_RISK"]
        new_entities = [d for d in deltas if d.get("delta_type") == "NEW_ENTITY"]
        dark_gaps = [d for d in deltas if d.get("delta_type") == "AIS_DARK_GAP"]

        escalation_score = run_data.get("escalation_score", 0.0) if run_data else 0.0

        lines = [
            f"# Executive Intelligence Briefing (SitRep) — Sweep `{sweep_id}`",
            f"**Global Escalation Index:** `{escalation_score:.1f}/100` | **Generated:** {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n",
            "### 1. Sanctions & Maritime Dark-Ship Anomalies",
        ]
        if sanctions or dark_gaps:
            for s in sanctions[:5]:
                lines.append(f"- **[SANCTION DETECTED]** {s['title']}: {s['description']} [DELTA:{s['delta_id']}]")
            for dg in dark_gaps[:5]:
                lines.append(f"- **[AIS DARK GAP]** {dg['title']}: {dg['description']} [DELTA:{dg['delta_id']}]")
        else:
            lines.append("- No new OFAC SDN sanction matches or anomalous AIS gaps detected in this sweep. [DELTA:none]")

        lines.append("\n### 2. Geofence Breaches & Monitored Watch Zones")
        if geofences:
            for g in geofences[:5]:
                lines.append(f"- **[GEOFENCE BREACH]** {g['title']}: {g['description']} [DELTA:{g['delta_id']}]")
        else:
            lines.append("- All monitored watch-zones reported zero unauthorized asset intrusions. [DELTA:none]")

        lines.append("\n### 3. Kinetic & Hazard Escalations")
        if escalations:
            for e in escalations[:5]:
                lines.append(f"- **[ESCALATION]** {e['title']}: {e['description']} [DELTA:{e['delta_id']}]")
        else:
            lines.append("- Seismic, thermal anomaly, and aviation transponder severity indices remain within baseline. [DELTA:none]")

        lines.append("\n### 4. Newly Ingested Intelligence Signals")
        if new_entities:
            for n in new_entities[:6]:
                lines.append(f"- **[NEW ASSET]** {n['title']}: {n['description']} [DELTA:{n['delta_id']}]")
        else:
            lines.append("- Zero newly emerged novel entities in this collection cycle. [DELTA:none]")

        briefing_md = "\n".join(lines)
        return {
            "sweep_id": sweep_id,
            "briefing_markdown": briefing_md,
            "escalation_score": escalation_score,
            "deltas_count": len(deltas),
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }


# Singleton
graphrag_assistant = GraphRAGAssistant()
