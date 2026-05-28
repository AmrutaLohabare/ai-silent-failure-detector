"""RAG module for Part 6 - observability incident retrieval."""

import json
import os
import re
from typing import Optional

_cache = None


def retrieve(query: str, kb_path: Optional[str] = None, k: int = 2) -> str:
    global _cache
    if _cache is None:
        if kb_path is None:
            kb_path = os.path.join(
                os.path.dirname(__file__), "..", "knowledge_base", "incidents.json"
            )
        with open(kb_path, encoding="utf-8") as f:
            incidents = json.load(f)
        _cache = []
        for inc in incidents:
            text = (
                inc["id"] + " " + inc["type"] + " " + inc["title"] + " " +
                inc["root_cause"] + " " + " ".join(inc.get("tags", []))
            ).lower()
            _cache.append({"text": text, "metadata": inc})
        print("[RAG] Loaded " + str(len(_cache)) + " observability incidents.")

    query_terms = set(re.findall(r"\w+", query.lower()))
    scored = []
    for doc in _cache:
        score = len(query_terms & set(re.findall(r"\w+", doc["text"])))
        scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)

    items = []
    for _, doc in scored[:k]:
        m = doc["metadata"]
        items.append({
            "incident_id": m["id"],
            "title": m["title"],
            "type": m["type"],
            "root_cause": m["root_cause"],
            "business_impact": m["business_impact"],
            "detection_lag_hours": m.get("detection_lag_hours"),
            "runbook": m.get("runbook", ""),
            "signal_correlation": m.get("signal_correlation", {}),
            "tags": ", ".join(m.get("tags", [])),
        })

    return json.dumps({"retrieved_count": len(items), "context": items})


def reset():
    global _cache
    _cache = None
