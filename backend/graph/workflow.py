"""
LangGraph Workflow Builder with unified multi-source retrieval.

Workflow pipeline:
retrieve_all (KB + Resume + Alumni + Interviews + Materials) ──(conditional by mode)──> mentor/interview_prep/ats/resume_match ──> memory ──> END
"""

from langgraph.graph import StateGraph, END
from graph.state import PlacementState
from graph.nodes import (
    retrieve_all_node,
    mentor_node,
    interview_prep_node,
    ats_node,
    resume_match_node,
    memory_node,
)


def route_by_mode(state: PlacementState) -> str:
    """Route directly to the appropriate generation node based on mode."""
    mode = state.get("mode", "mentor")
    if mode == "interview_prep":
        return "interview_prep"
    elif mode == "ats":
        return "ats"
    elif mode == "resume_match":
        return "resume_match"
    else:
        return "mentor"


def build_placement_graph():
    """Build the LangGraph workflow with unified multi-source retrieval."""
    graph = StateGraph(PlacementState)

    # ── Retrieval Node ──
    graph.add_node("retrieve_all", retrieve_all_node)

    # ── Generation Nodes ──
    graph.add_node("mentor", mentor_node)
    graph.add_node("interview_prep", interview_prep_node)
    graph.add_node("ats", ats_node)
    graph.add_node("resume_match", resume_match_node)
    graph.add_node("memory", memory_node)

    # ── Entry ──
    graph.set_entry_point("retrieve_all")

    # ── Route directly from retrieval to generation by mode ──
    graph.add_conditional_edges(
        "retrieve_all",
        route_by_mode,
        {
            "mentor": "mentor",
            "interview_prep": "interview_prep",
            "ats": "ats",
            "resume_match": "resume_match",
        },
    )

    # ── All generation nodes → memory → END ──
    graph.add_edge("mentor", "memory")
    graph.add_edge("interview_prep", "memory")
    graph.add_edge("ats", "memory")
    graph.add_edge("resume_match", "memory")
    graph.add_edge("memory", END)

    return graph.compile()
