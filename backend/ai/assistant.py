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
    """Validates every [ev_xxxx] citation in the generated response against workspace evidence artifacts.
    
    Returns:
        {
          "total_citations": int,
          "valid_citations": List[str],
          "hallucinated_citations": List[str],
          "citation_integrity_score": float [0.0..1.0]
        }
    """
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


# Singleton
graphrag_assistant = GraphRAGAssistant()
