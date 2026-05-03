"""
RAG module for Part 3 — Visual failure knowledge base retrieval.
Same TF-IDF pattern as Parts 1 & 2 for Windows/Python 3.13 compatibility.
"""

import json
import os
import re
from pathlib import Path
from typing import Optional

_retriever_cache = None


def _load_incidents(kb_path: str) -> list[dict]:
    path = Path(kb_path)
    if not path.exists():
        print(f"[RAG] Warning: knowledge base not found at {kb_path}")
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _build_doc_text(inc: dict) -> str:
    return (
        f"Incident {inc['id']}: {inc['title']}. "
        f"Type: {inc['type']}. "
        f"Path: {inc.get('path_pattern', '')}. "
        f"Root cause: {inc['root_cause']} "
        f"Tags: {', '.join(inc.get('tags', []))}."
    )


class _TFIDFRetriever:
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
    global _retriever_cache
    if _retriever_cache is None:
        if kb_path is None:
            kb_path = os.path.join(
                os.path.dirname(__file__), "..", "knowledge_base", "incidents.json"
            )
        incidents = _load_incidents(kb_path)
        docs = [{"text": _build_doc_text(i), "metadata": i} for i in incidents]
        _retriever_cache = _TFIDFRetriever(docs)
        print(f"[RAG] Loaded {len(docs)} visual incidents into retriever.")
    return _retriever_cache


def retrieve(query: str, kb_path: Optional[str] = None, k: int = 2) -> str:
    retriever = get_retriever(kb_path)
    docs = retriever.query(query, k=k)
    items = []
    for doc in docs:
        m = doc["metadata"]
        items.append({
            "incident_id": m["id"],
            "title": m["title"],
            "type": m["type"],
            "root_cause": m["root_cause"],
            "business_impact": m["business_impact"],
            "detection_lag_hours": m.get("detection_lag_hours", "unknown"),
            "runbook": m.get("runbook", "No runbook available."),
            "tags": ", ".join(m.get("tags", [])),
        })
    return json.dumps({"retrieved_count": len(items), "context": items})
