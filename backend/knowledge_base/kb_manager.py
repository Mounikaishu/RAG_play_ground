"""
Knowledge Base Manager — High-level API for managing the institutional KB.
"""

from knowledge_base.collections import (
    store_kb_document, search_kb, get_all_kb_stats,
    delete_kb_document, list_kb_documents, get_collection_count,
)


def add_alumni_profile(name, year, company, role, department, skills, journey):
    """Add an alumni career profile to the KB."""
    doc_id = f"alumni_{name.lower().replace(' ', '_')}_{year}"
    skills_str = ", ".join(skills) if isinstance(skills, list) else skills
    text = f"{name} graduated in {year} from {department} with skills in {skills_str}. Placed at {company} as {role}. {journey}"
    metadata = {
        "category": "alumni",
        "company": company,
        "role": role,
        "department": department,
        "year": str(year),
    }
    store_kb_document("institutional_kb", doc_id, text, metadata)
    return doc_id


def add_interview_experience(company, role, round_type, questions, tips):
    """Add an interview experience to the KB."""
    import time
    doc_id = f"interview_{company.lower().replace(' ', '_')}_{int(time.time())}"
    questions_text = " ".join([f"{i+1}. {q}" for i, q in enumerate(questions)])
    text = f"{company} {role} {round_type} Round: Questions asked: {questions_text}. Tips: {tips}"
    metadata = {
        "category": "interview",
        "company": company,
        "role": role,
        "round": round_type,
    }
    store_kb_document("interview_experiences", doc_id, text, metadata)
    return doc_id


def add_resource(title, content, category):
    """Add a placement resource to the KB."""
    import time
    doc_id = f"resource_{category}_{int(time.time())}"
    text = f"{title}: {content}"
    metadata = {"category": "resource", "type": category}
    store_kb_document("institutional_kb", doc_id, text, metadata)
    return doc_id


def search_knowledge(query, category_filter=None, k=5):
    """Search the institutional KB with optional category filter."""
    where = {"category": category_filter} if category_filter else None
    return search_kb(query, "institutional_kb", k=k, where=where)


def search_interviews(query, company=None, k=5):
    """Search interview experiences with optional company filter."""
    where = {"company": company} if company else None
    return search_kb(query, "interview_experiences", k=k, where=where)


def get_kb_stats():
    """Get knowledge base statistics."""
    stats = get_all_kb_stats()
    return {
        "total_documents": sum(stats.values()),
        "institutional_kb": stats.get("institutional_kb", 0),
        "interview_experiences": stats.get("interview_experiences", 0),
        "student_resumes": stats.get("student_resumes", 0),
    }
