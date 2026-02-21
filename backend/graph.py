from langgraph.graph import StateGraph, END
from state import ChatState
from vectorstore import retrieve_relevant_chunks
from llm import llm_call


# 🔹 Node 1: Retrieve Relevant Resume Sections
def retrieve_node(state: ChatState) -> ChatState:
    chunks = retrieve_relevant_chunks(state["question"])
    context = "\n\n".join(chunks)

    return {
        **state,
        "context": context
    }


# 🔹 Node 2: Resume Coach (LLM)
def coach_node(state: ChatState) -> ChatState:
    history_text = "\n".join(state["history"])

    prompt = f"""
    You are a senior technical recruiter and career mentor.

    Resume Context:
    {state["context"]}

    Conversation History:
    {history_text}

    Student Question:
    {state["question"]}

    Provide:
    - Honest evaluation
    - Strengths
    - Weaknesses
    - Specific improvement suggestions
    - Practical next steps
    """

    answer = llm_call(prompt)

    return {
        **state,
        "answer": answer
    }


# 🔹 Node 3: Memory Update
def memory_node(state: ChatState) -> ChatState:
    updated_history = state["history"] + [
        f"Student: {state['question']}",
        f"Coach: {state['answer']}"
    ]

    return {
        **state,
        "history": updated_history
    }


def build_graph():
    graph = StateGraph(ChatState)

    graph.add_node("retrieve", retrieve_node)
    graph.add_node("coach", coach_node)
    graph.add_node("memory", memory_node)

    graph.set_entry_point("retrieve")

    graph.add_edge("retrieve", "coach")
    graph.add_edge("coach", "memory")
    graph.add_edge("memory", END)

    return graph.compile()