"""
LangGraph Workflow Builder with conditional routing based on mode.

Retrieval pipeline:
- Mentor mode:         retrieve_kb → retrieve_alumni → retrieve_resume → retrieve_materials → mentor → memory
- Interview prep mode: retrieve_kb → retrieve_interviews_enhanced → retrieve_alumni → retrieve_resume → interview_prep → memory
- ATS mode:            retrieve_kb → retrieve_resume → retrieve_materials → ats → memory
- Resume match mode:   retrieve_kb → retrieve_resume_matching → retrieve_resume → resume_match → memory
"""

from langgraph.graph import StateGraph, END
from graph.state import PlacementState
from graph.nodes import (
    retrieve_kb_node,
    retrieve_resume_node,
    retrieve_interview_node,
    retrieve_alumni_guidance_node,
    retrieve_interview_experience_node,
    retrieve_resume_matching_node,
    retrieve_placement_materials_node,
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
        return "interview_chain"
    elif mode == "ats":
        return "ats_chain"
    elif mode == "resume_match":
        return "match_chain"
    else:
        return "mentor_chain"


def build_placement_graph():
    """Build the LangGraph workflow with conditional routing and multi-source retrieval."""
    graph = StateGraph(PlacementState)

    # ── Retrieval Nodes ──
    graph.add_node("retrieve_kb", retrieve_kb_node)
    graph.add_node("retrieve_resume", retrieve_resume_node)
    graph.add_node("retrieve_interviews", retrieve_interview_node)
    graph.add_node("retrieve_alumni", retrieve_alumni_guidance_node)
    graph.add_node("retrieve_interviews_enhanced", retrieve_interview_experience_node)
    graph.add_node("retrieve_matching", retrieve_resume_matching_node)
    graph.add_node("retrieve_materials", retrieve_placement_materials_node)

    # ── Generation Nodes ──
    graph.add_node("mentor", mentor_node)
    graph.add_node("interview_prep", interview_prep_node)
    graph.add_node("ats", ats_node)
    graph.add_node("resume_match", resume_match_node)
    graph.add_node("memory", memory_node)

    # ── Entry: always retrieve KB first ──
    graph.set_entry_point("retrieve_kb")

    # ── Route by mode after KB retrieval ──
    graph.add_conditional_edges(
        "retrieve_kb",
        route_by_mode,
        {
            "mentor_chain": "retrieve_alumni",
            "interview_chain": "retrieve_interviews_enhanced",
            "ats_chain": "retrieve_resume",
            "match_chain": "retrieve_matching",
        },
    )

    # ── Mentor Chain ──
    # retrieve_kb → retrieve_alumni → retrieve_resume → retrieve_materials → mentor → memory
    graph.add_edge("retrieve_alumni", "retrieve_resume")

    # After resume retrieval in mentor chain, go to materials
    # We need a conditional to differentiate chains sharing retrieve_resume
    # Instead, use a simpler approach: mentor chain goes through materials
    def route_after_resume(state: PlacementState) -> str:
        mode = state.get("mode", "mentor")
        if mode == "mentor":
            return "to_materials"
        elif mode == "ats":
            return "to_ats_materials"
        elif mode == "interview_prep":
            return "to_interview_gen"
        else:
            return "to_match_gen"

    graph.add_conditional_edges(
        "retrieve_resume",
        route_after_resume,
        {
            "to_materials": "retrieve_materials",
            "to_ats_materials": "retrieve_materials",
            "to_interview_gen": "interview_prep",
            "to_match_gen": "resume_match",
        },
    )

    # After materials retrieval, route to generation
    def route_after_materials(state: PlacementState) -> str:
        mode = state.get("mode", "mentor")
        if mode == "ats":
            return "to_ats"
        else:
            return "to_mentor"

    graph.add_conditional_edges(
        "retrieve_materials",
        route_after_materials,
        {
            "to_mentor": "mentor",
            "to_ats": "ats",
        },
    )

    # ── Interview Prep Chain ──
    # retrieve_kb → retrieve_interviews_enhanced → retrieve_alumni → retrieve_resume → interview_prep → memory
    graph.add_edge("retrieve_interviews_enhanced", "retrieve_alumni")
    # retrieve_alumni already connects to retrieve_resume (shared edge above)

    # ── ATS Chain ──
    # retrieve_kb → retrieve_resume → retrieve_materials → ats → memory
    # (handled by conditional edges above)

    # ── Resume Match Chain ──
    # retrieve_kb → retrieve_matching → retrieve_resume → resume_match → memory
    graph.add_edge("retrieve_matching", "retrieve_resume")
    # retrieve_resume → resume_match (handled by conditional edge)

    # ── All generation nodes → memory → END ──
    graph.add_edge("mentor", "memory")
    graph.add_edge("interview_prep", "memory")
    graph.add_edge("ats", "memory")
    graph.add_edge("resume_match", "memory")
    graph.add_edge("memory", END)

    return graph.compile()
