"""
LangGraph Workflow Builder with unified multi-source retrieval.

Workflow pipeline (Phase 3):
  rewrite_query ──► retrieve_all ──(conditional by mode)──► mentor/interview_prep/resume_match ──► memory ──► END

Phase 3 Change:
  Added rewrite_query_node as the new entry point. It uses the production
  QueryRewriter (generation/query_rewriter.py) to transform vague or abbreviated
  queries into precise, searchable queries before they hit the Retrieval Engine.
"""

from langgraph.graph import StateGraph, END
from graph.state import PlacementState
from graph.nodes import (
    rewrite_query_node,
    retrieve_all_node,
    mentor_node,
    interview_prep_node,
    resume_match_node,
    memory_node,
)


def route_by_mode(state: PlacementState) -> str:
    """Route directly to the appropriate generation node based on mode."""
    mode = state.get("mode", "mentor")
    if mode == "interview_prep":
        return "interview_prep"
    elif mode == "resume_match":
        return "resume_match"
    else:
        return "mentor"


def build_placement_graph():
    """Build the LangGraph workflow with Phase 3 query rewriting + unified retrieval."""
    graph = StateGraph(PlacementState)

    # ── Phase 3: Query Rewriting Node (new entry point) ──
    graph.add_node("rewrite_query", rewrite_query_node)

    # ── Retrieval Node ──
    graph.add_node("retrieve_all", retrieve_all_node)

    # ── Generation Nodes ──
    graph.add_node("mentor", mentor_node)
    graph.add_node("interview_prep", interview_prep_node)
    graph.add_node("resume_match", resume_match_node)
    graph.add_node("memory", memory_node)

    # ── Entry: rewrite_query is now the first node ──
    graph.set_entry_point("rewrite_query")

    # ── rewrite_query → retrieve_all (always) ──
    graph.add_edge("rewrite_query", "retrieve_all")

    # ── Route from retrieval to generation by mode ──
    graph.add_conditional_edges(
        "retrieve_all",
        route_by_mode,
        {
            "mentor": "mentor",
            "interview_prep": "interview_prep",
            "resume_match": "resume_match",
        },
    )

    # ── All generation nodes → memory → END ──
    graph.add_edge("mentor", "memory")
    graph.add_edge("interview_prep", "memory")
    graph.add_edge("resume_match", "memory")
    graph.add_edge("memory", END)

    return graph.compile()
