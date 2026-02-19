from langgraph.graph import StateGraph, END
from state import SummaryState
from llm import llm_call

# --- Node 1: Chunk Summarizer ---
def chunk_summarizer(state: SummaryState) -> SummaryState:
    summaries = []

    for chunk in state["chunks"]:
        prompt = f"""
        Summarize the following text clearly:

        {chunk}
        """
        summaries.append(llm_call(prompt))

    return {**state, "chunk_summaries": summaries}


# --- Node 2: Reducer ---
def reducer(state: SummaryState) -> SummaryState:
    combined = "\n".join(state["chunk_summaries"])

    prompt = f"""
    Combine the following summaries into one coherent summary:

    {combined}
    """

    return {**state, "final_summary": llm_call(prompt)}


# --- Node 3: Final Refinement ---
def final_refinement(state: SummaryState) -> SummaryState:
    prompt = f"""
    Refine the following summary to be concise and well-structured:

    {state["final_summary"]}
    """

    return {**state, "final_summary": llm_call(prompt)}


# --- Graph ---
def build_graph():
    graph = StateGraph(SummaryState)

    graph.add_node("chunk_summarizer", chunk_summarizer)
    graph.add_node("reducer", reducer)
    graph.add_node("final_refinement", final_refinement)

    graph.set_entry_point("chunk_summarizer")
    graph.add_edge("chunk_summarizer", "reducer")
    graph.add_edge("reducer", "final_refinement")
    graph.add_edge("final_refinement", END)

    return graph.compile()
