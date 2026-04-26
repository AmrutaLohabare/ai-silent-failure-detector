"""
RAG module for AI Silent Failure Detector.

Builds a FAISS vector store from the knowledge base (past incidents + runbooks)
and exposes a LangChain Tool that retrieves relevant context for any detected anomaly.

Design decisions:
- Uses sentence-transformers (all-MiniLM-L6-v2) for embeddings — free, fast, no API key needed
- Falls back to TF-IDF keyword search if sentence-transformers is unavailable
- Vector store is built once at startup and cached in memory
- Each retrieved document includes: root cause, runbook steps, business impact
"""

import json
import os
import re
from pathlib import Path
from typing import Optional

from langchain.tools import BaseTool
from pydantic import BaseModel, Field


# ─── Embedding Backend Selection ─────────────────────────────────────────────

def _build_vector_store(kb_path: str) -> object:
    """
    Build and return a retriever from the knowledge base.
    Tries sentence-transformers + FAISS first, falls back to BM25/TF-IDF.
    """
    incidents = _load_knowledge_base(kb_path)
    docs = _incidents_to_documents(incidents)

    try:
        from langchain_community.vectorstores import FAISS
        from langchain_community.embeddings import HuggingFaceEmbeddings

        print("[RAG] Building FAISS vector store with sentence-transformers...")
        embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        vectorstore = FAISS.from_texts(
            texts=[d["text"] for d in docs],
            embedding=embeddings,
            metadatas=[d["metadata"] for d in docs],
        )
        print(f"[RAG] Vector store built — {len(docs)} documents indexed.")
        return vectorstore.as_retriever(search_kwargs={"k": 2})

    except ImportError:
        print("[RAG] sentence-transformers/FAISS not available — using TF-IDF fallback.")
        return _TFIDFRetriever(docs)


def _load_knowledge_base(kb_path: str) -> list[dict]:
    path = Path(kb_path)
    if not path.exists():
        print(f"[RAG] Warning: knowledge base not found at {kb_path}")
        return []
    with open(path) as f:
        return json.load(f)


def _incidents_to_documents(incidents: list[dict]) -> list[dict]:
    """
    Convert incident JSON records to flat text documents for embedding.
    Each document is a rich string combining all searchable fields.
    """
    docs = []
    for inc in incidents:
        text = (
            f"Incident {inc['id']}: {inc['title']}. "
            f"Failure type: {inc['type']}. "
            f"Path pattern: {inc.get('path_pattern', 'unknown')}. "
            f"Root cause: {inc['root_cause']} "
            f"Business impact: {inc['business_impact']} "
            f"Tags: {', '.join(inc.get('tags', []))}. "
            f"Resolution: {inc['resolution']}"
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
                "tags": ", ".join(inc.get("tags", [])),
            },
        })
    return docs


# ─── TF-IDF Fallback Retriever ─────────────────────────────────────────────

class _TFIDFRetriever:
    """
    Simple keyword-based fallback when sentence-transformers is unavailable.
    Scores documents by term overlap with the query.
    """

    def __init__(self, docs: list[dict]):
        self.docs = docs

    def get_relevant_documents(self, query: str) -> list:
        query_terms = set(re.findall(r'\w+', query.lower()))
        scored = []
        for doc in self.docs:
            text_terms = set(re.findall(r'\w+', doc["text"].lower()))
            overlap = len(query_terms & text_terms)
            scored.append((overlap, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:2]

        # Return objects that mimic LangChain Document interface
        return [_FakeDoc(doc["text"], doc["metadata"]) for _, doc in top]

    def invoke(self, query: str) -> list:
        return self.get_relevant_documents(query)


class _FakeDoc:
    def __init__(self, page_content: str, metadata: dict):
        self.page_content = page_content
        self.metadata = metadata


# ─── Singleton Vector Store ─────────────────────────────────────────────────

_retriever_cache: Optional[object] = None

def get_retriever(kb_path: Optional[str] = None) -> object:
    global _retriever_cache
    if _retriever_cache is None:
        if kb_path is None:
            kb_path = os.path.join(
                os.path.dirname(__file__), "..", "knowledge_base", "incidents.json"
            )
        _retriever_cache = _build_vector_store(kb_path)
    return _retriever_cache


# ─── LangChain RAG Tool ────────────────────────────────────────────────────

class RAGContextInput(BaseModel):
    anomaly_summary: str = Field(
        description=(
            "A plain-English description of the detected anomaly. Include: "
            "the failure type, affected path, and any observed symptoms. "
            "Example: 'EMPTY_SUCCESS_RESPONSE on /api/auth/refresh — "
            "14 HTTP 200 responses with zero-byte body detected.'"
        )
    )


class RAGContextTool(BaseTool):
    name: str = "rag_context"
    description: str = (
        "Retrieves relevant past incidents and runbooks from the knowledge base "
        "that are similar to the current anomaly. Call this after anomaly_detector "
        "and before silent_failure_reporter. "
        "Input: a description of the detected anomaly. "
        "Output: similar past incidents with root causes, business impact, and runbook steps."
    )
    args_schema: type[BaseModel] = RAGContextInput
    kb_path: Optional[str] = None

    def _run(self, anomaly_summary: str) -> str:
        retriever = get_retriever(self.kb_path)

        try:
            # LangChain retriever interface
            if hasattr(retriever, "invoke"):
                docs = retriever.invoke(anomaly_summary)
            else:
                docs = retriever.get_relevant_documents(anomaly_summary)
        except Exception as e:
            return json.dumps({"error": f"RAG retrieval failed: {str(e)}", "context": []})

        if not docs:
            return json.dumps({
                "context": [],
                "message": "No similar past incidents found in knowledge base.",
            })

        context_items = []
        for doc in docs:
            m = doc.metadata
            context_items.append({
                "incident_id": m.get("id", "unknown"),
                "title": m.get("title", ""),
                "failure_type": m.get("type", ""),
                "path_pattern": m.get("path_pattern", ""),
                "root_cause": m.get("root_cause", ""),
                "business_impact": m.get("business_impact", ""),
                "detection_lag_hours": m.get("detection_lag_hours", "unknown"),
                "runbook": m.get("runbook", "No runbook available."),
                "tags": m.get("tags", ""),
            })

        return json.dumps({
            "retrieved_count": len(context_items),
            "context": context_items,
        })

    async def _arun(self, anomaly_summary: str) -> str:
        return self._run(anomaly_summary)
