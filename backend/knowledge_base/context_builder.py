"""
context_builder.py — LLM Prompt Context Formatter.

Pure formatting module. Converts RetrievalResult objects into structured,
readable markdown context for LLM generation nodes in LangGraph.
Does NOT perform DB queries, filtering, or ranking.
"""

from typing import List, Union
from knowledge_base.retrieval_models import RetrievalResult, RetrievalResponse


def build_context(results: Union[List[RetrievalResult], RetrievalResponse]) -> str:
    """
    Format a list of RetrievalResult objects or RetrievalResponse into clean markdown context.

    Example Output:
        ### Interview Experience: Google (Software Engineer)
        **Difficulty**: Hard | **Page**: 1 | **Section**: Questions Asked
        - 2 HackerRank problems...

        ### Resume: Aarav Sharma
        **Company**: Amazon | **Role**: Software Engineer | **Section**: Projects
        - ResumeAI: Semantic resume ranking system...
    """
    if isinstance(results, RetrievalResponse):
        chunk_list = results.results
    elif isinstance(results, list):
        chunk_list = results
    else:
        return ""

    if not chunk_list:
        return "No relevant context found."

    context_parts: List[str] = []

    for i, r in enumerate(chunk_list, 1):
        meta = r.metadata
        doc_type = r.document_type or "Document"
        section = r.section or "General"
        page = r.page_number or 1

        header_lines = []

        if "interview" in doc_type.lower() or r.collection == "interview_experiences":
            comp = r.company or meta.get("company", "Unknown")
            role = r.role or meta.get("role", "Software Engineer")
            diff = meta.get("difficulty", "Medium")
            jtype = meta.get("job_type", "FTE")
            header_lines.append(f"### Chunk {i}: Interview Experience — {comp} ({role})")
            header_lines.append(f"**Job Type**: {jtype} | **Difficulty**: {diff} | **Section**: {section} | **Page**: {page}")

        elif "resume" in doc_type.lower() or r.collection == "alumni_resumes":
            name = meta.get("student_name", "Alumni")
            comp = r.company or meta.get("company", "Not Specified")
            role = r.role or meta.get("role", "Software Engineer")
            dept = meta.get("department", "CS")
            header_lines.append(f"### Chunk {i}: Resume — {name}")
            header_lines.append(f"**Company**: {comp} | **Role**: {role} | **Dept**: {dept} | **Section**: {section} | **Page**: {page}")

        else:
            header_lines.append(f"### Chunk {i}: {doc_type} ({r.source_file})")
            header_lines.append(f"**Section**: {section} | **Page**: {page}")

        header = "\n".join(header_lines)
        body = r.content.strip()

        context_parts.append(f"{header}\n\n{body}")

    formatted = "\n\n" + ("─" * 40) + "\n\n".join(context_parts)
    return formatted.strip()
