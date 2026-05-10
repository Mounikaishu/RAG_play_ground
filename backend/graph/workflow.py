"""
LangGraph Workflow Builder with conditional routing based on mode.
"""

from langgraph.graph import StateGraph, END
from graph.state import PlacementState
from graph.nodes import (
    retrieve_kb_node,
    retrieve_resume_node,
    retrieve_interview_node,
    mentor_node,
    interview_prep_node,
    ats_node,
    resume_match_node,
    memory_node,
)


def route_by_mode(state: PlacementState) -> str:
    """Route to the appropriate processing chain based on mode."""
    mode = state.get("mode", "mentor")
    if mode == "interview_prep":
        return "retrieve_interviews"
    elif mode == "ats":
        return "ats_process"
    elif mode == "resume_match":
        return "match_process"
    else:
        return "mentor_process"


def build_placement_graph():
    """Build the LangGraph workflow with conditional routing."""
    graph = StateGraph(PlacementState)

    # Add all nodes
    graph.add_node("retrieve_kb", retrieve_kb_node)
    graph.add_node("retrieve_resume", retrieve_resume_node)
    graph.add_node("retrieve_interviews", retrieve_interview_node)
    graph.add_node("mentor", mentor_node)
    graph.add_node("interview_prep", interview_prep_node)
    graph.add_node("ats", ats_node)
    graph.add_node("resume_match", resume_match_node)
    graph.add_node("memory", memory_node)

    # Entry: always retrieve KB and resume first
    graph.set_entry_point("retrieve_kb")
    graph.add_edge("retrieve_kb", "retrieve_resume")

    # After resume retrieval, route by mode
    graph.add_conditional_edges(
        "retrieve_resume",
        route_by_mode,
        {
            "retrieve_interviews": "retrieve_interviews",
            "ats_process": "ats",
            "match_process": "resume_match",
            "mentor_process": "mentor",
        },
    )

    # Interview prep chain
    graph.add_edge("retrieve_interviews", "interview_prep")
    graph.add_edge("interview_prep", "memory")

    # Direct chains
    graph.add_edge("mentor", "memory")
    graph.add_edge("ats", "memory")
    graph.add_edge("resume_match", "memory")

    # Memory → END
    graph.add_edge("memory", END)

    return graph.compile()
