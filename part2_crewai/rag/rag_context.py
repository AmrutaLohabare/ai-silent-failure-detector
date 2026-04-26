"""
RAG module for Part 2 — shared across all 3 CrewAI agents.

Key difference from Part 1:
- All 3 agents share the same retriever instance (singleton)
- Returns agent_verdict and analyzer_reasoning fields
- Supports querying by incident type to help Analyzer find overrule evidence
- TF-IDF fallback (no sentence-transformers needed for Windows compatibility)
"""

import json
import os
import re
from pathlib import Path
from typing import Optional


_retriever_cache: Optional[object] = None


def _load_incidents(kb_path: str) -> list[dict]:
    path = Path(kb_path)
    if not path.exists():
        print(f"[RAG] Warning: knowledge base not found at {kb_path}")
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _incidents_to_docs(incidents: list[dict]) -> list[dict]:
    docs = []
    for inc in incidents:
        text = (
            f"Incident {inc['id']}: {inc['title']}. "
            f"Type: {inc['type']}. "
            f"Path: {inc.get('path_pattern', '')}. "
            f"Root cause: {inc['root_cause']} "
            f"Verdict: {inc.get('agent_verdict', 'UNKNOWN')}. "
            f"Tags: {', '.join(inc.get('tags', []))}."
        )
        docs.append({
            "text": text,
            "metadata": {
                "id": inc["id"],
                "type": inc["type"],
                "path_pattern": inc.get("path_pattern", ""),
                "title": inc["title"],
                "root_cause": inc["root_cause"],
                "runbook": inc.get("runbook", "No runbook available."),
                "business_impact": inc["business_impact"],
                "detection_lag_hours": inc.get("detection_lag_hours", "unknown"),
                "agent_verdict": inc.get("agent_verdict", "UNKNOWN"),
                "analyzer_reasoning": inc.get("analyzer_reasoning", ""),
                "tags": ", ".join(inc.get("tags", [])),
            },
        })
    return docs


class _TFIDFRetriever:
    """Keyword overlap retriever — no dependencies, runs fully offline."""

    def __init__(self, docs: list[dict]):
        self.docs = docs

    def query(self, text: str, k: int = 2) -> list[dict]:
        query_terms = set(re.findall(r'\w+', text.lower()))
        scored = []
        for doc in self.docs:
            doc_terms = set(re.findall(r'\w+', doc["text"].lower()))
            score = len(query_terms & doc_terms)
            scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:k]]


def get_retriever(kb_path: Optional[str] = None) -> _TFIDFRetriever:
    """Singleton retriever shared across all agents."""
    global _retriever_cache
    if _retriever_cache is None:
        if kb_path is None:
            kb_path = os.path.join(
                os.path.dirname(__file__), "..", "knowledge_base", "incidents.json"
            )
        incidents = _load_incidents(kb_path)
        docs = _incidents_to_docs(incidents)
        _retriever_cache = _TFIDFRetriever(docs)
        print(f"[RAG] Loaded {len(docs)} incidents into shared retriever.")
    return _retriever_cache


def retrieve(query: str, kb_path: Optional[str] = None, k: int = 2) -> str:
    """
    Main retrieval function called by any agent.
    Returns JSON string with context items.
    """
    retriever = get_retriever(kb_path)
    docs = retriever.query(query, k=k)

    items = []
    for doc in docs:
        m = doc["metadata"]
        items.append({
            "incident_id": m["id"],
            "title": m["title"],
            "type": m["type"],
            "path_pattern": m["path_pattern"],
            "root_cause": m["root_cause"],
            "business_impact": m["business_impact"],
            "detection_lag_hours": m["detection_lag_hours"],
            "agent_verdict": m["agent_verdict"],
            "analyzer_reasoning": m["analyzer_reasoning"],
            "runbook": m["runbook"],
            "tags": m["tags"],
        })

    return json.dumps({
        "retrieved_count": len(items),
        "context": items,
    })
