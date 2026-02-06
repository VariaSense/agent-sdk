"""Tests for vector.search tool behavior."""

from agent_sdk.tool_packs.builtin import TOOL_DEFINITIONS


def test_vector_search_returns_citations():
    tool = TOOL_DEFINITIONS["vector.search"].func
    payload = tool(
        {
            "query": "programming language",
            "top_k": 2,
            "documents": [
                {"doc_id": "doc1", "content": "Python is a programming language", "source": "wiki"},
                {"doc_id": "doc2", "content": "Cats are animals", "source": "wiki"},
            ],
        }
    )

    assert "matches" in payload
    assert "citations" in payload
    assert len(payload["citations"]) == 2
    assert payload["citations"][0]["doc_id"] == "doc1"
