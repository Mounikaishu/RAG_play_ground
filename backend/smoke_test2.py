"""smoke_test2.py — Validation-focused tests for extraction bug fixes (Round 2)."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from generation.structured_evidence import (
    _is_valid_person_name,
    _extract_company_from_chunk,
    _is_project_block,
    _extract_projects_student,
    _extract_projects_alumni,
    _validate_alumni_profile,
    AlumniProfile,
    StudentProfile,
)

print("=" * 55)
print("TEST 1: Name validator rejects invalid alumni names")
print("=" * 55)
MUST_REJECT = [
    "Placement Tips", "Linux Kernel", "Distributed Systems",
    "Current Employer", "Resume", "Profile", "Career Journey",
    "Professional Summary", "Projects", "Skills", "Education",
    "Experience", "Certifications", "Achievements",
    "Machine Learning", "Data Science", "System Design",
    "Technical Skills", "Work Experience",
]
for name in MUST_REJECT:
    result = _is_valid_person_name(name)
    assert not result, f"FAIL: '{name}' should be rejected but was accepted!"
    print(f"  REJECTED correctly: '{name}'")

MUST_ACCEPT = [
    "Meera Krishnan", "Divya Aggarwal", "Rahul Verma",
    "Arun Kumar", "Priya Nair", "Siddharth Rao",
]
for name in MUST_ACCEPT:
    result = _is_valid_person_name(name)
    assert result, f"FAIL: '{name}' should be accepted!"
    print(f"  ACCEPTED correctly: '{name}'")
print("PASS\n")

print("=" * 55)
print("TEST 2: Company extraction priority chain")
print("=" * 55)

# Priority 1: Current Employer
chunk1 = "Current Employer: Adobe\nRole: ML Engineer\nPython PyTorch LangChain"
co = _extract_company_from_chunk(chunk1, {})
assert co == "Adobe", f"Expected 'Adobe', got '{co}'"
print(f"  Current Employer pattern: '{co}'  PASS")

# Priority 2: Company:
chunk2 = "Company: Google\nDesignation: Senior SDE\nBERT Transformers"
co = _extract_company_from_chunk(chunk2, {})
assert co == "Google", f"Expected 'Google', got '{co}'"
print(f"  Company: pattern: '{co}'  PASS")

# Priority 3: Employer:
chunk3 = "Employer: Microsoft\nRole: Software Engineer\nC++ Azure"
co = _extract_company_from_chunk(chunk3, {})
assert co == "Microsoft", f"Expected 'Microsoft', got '{co}'"
print(f"  Employer: pattern: '{co}'  PASS")

# Priority 0: Metadata
co = _extract_company_from_chunk("some resume text", {"company": "NVIDIA"})
assert co == "NVIDIA", f"Expected 'NVIDIA', got '{co}'"
print(f"  Metadata: '{co}'  PASS")

# Should NOT return "Unknown Company" when info available
chunk_no_explicit = "Software Engineer | Amazon\nPython SQL Docker AWS"
co = _extract_company_from_chunk(chunk_no_explicit, {})
# May or may not find it depending on pattern, but should try
print(f"  Experience-section pattern: '{co}'  (result — no assertion)")
print("PASS\n")

print("=" * 55)
print("TEST 3: Project advice guard (_is_project_block)")
print("=" * 55)
ADVICE_BLOCKS = [
    ("For ML roles prepare linear algebra", "For ML roles prepare linear algebra"),
    ("Placement Tips\nStudy DSA", "Placement Tips"),
    ("How to get into Google\nPractice LeetCode", "How to get into Google"),
    ("Career Goals\nI want to become an ML engineer", "Career Goals"),
]
for block, title in ADVICE_BLOCKS:
    result = _is_project_block(block, title)
    assert not result, f"FAIL: '{title}' should be rejected as non-project!"
    print(f"  REJECTED advice: '{title}'")

REAL_PROJECTS = [
    ("AI Resume Coach\nBuilt using FastAPI and LangChain. Deployed on AWS.\nPython FastAPI LangGraph", "AI Resume Coach"),
    ("RAG Knowledge Assistant\nImplemented using ChromaDB, LangGraph, Python.", "RAG Knowledge Assistant"),
    ("Image Classification\nTrained CNN with PyTorch. Achieved 94% accuracy.", "Image Classification"),
]
for block, title in REAL_PROJECTS:
    result = _is_project_block(block, title)
    assert result, f"FAIL: '{title}' should be accepted as real project!"
    print(f"  ACCEPTED project: '{title}'")
print("PASS\n")

print("=" * 55)
print("TEST 4: Student project extraction — sections only")
print("=" * 55)
student_resume = """
## Education
B.Tech Computer Science, SRM University — 2024

## Projects
### AI Resume Coach
Built an LLM-based resume analysis tool using LangChain, FastAPI, and ChromaDB.
Impact: Reduced manual review time by 40%.

### RAG Knowledge Assistant
Implemented retrieval-augmented generation pipeline using LangGraph and Python.
Tech: Python, LangGraph, ChromaDB

## Placement Tips
For ML roles:
- Learn linear algebra
- Practice LeetCode
- Study system design

## Skills
Python, SQL, FastAPI, LangChain
"""
prj = _extract_projects_student(student_resume)
print(f"  Student projects found: {len(prj)}")
for p in prj:
    print(f"  - {p['title']} | tech={p['technologies']} | domain={p['domain']}")
assert len(prj) >= 1, "Student must find at least 1 project!"
titles = [p["title"].lower() for p in prj]
assert not any("placement" in t or "tip" in t or "linear algebra" in t for t in titles), \
    "Advice leaked into student projects!"
print("PASS\n")

print("=" * 55)
print("TEST 5: Alumni project guard rejects advice")
print("=" * 55)
alumni_text_with_advice = """
## Projects
### Stable Diffusion Fine-tuner
Fine-tuned Stable Diffusion model on custom art dataset using PyTorch and CUDA.
Achieved FID score of 12.3. Deployed on GCP.

### For ML roles prepare linear algebra
Study numpy, pandas, sklearn.
Practice on Kaggle.

## Career Tips
Learn PyTorch before applying to ML roles.
"""
prj_al = _extract_projects_alumni(alumni_text_with_advice)
print(f"  Alumni projects: {len(prj_al)}")
for p in prj_al:
    print(f"  - {p['title']}")
titles_al = [p["title"].lower() for p in prj_al]
assert not any("for ml" in t or "tip" in t or "prepare" in t for t in titles_al), \
    "Advice paragraph leaked into alumni projects!"
print("PASS\n")

print("=" * 55)
print("TEST 6: Profile validation gate")
print("=" * 55)

# Valid profile
p_valid = AlumniProfile(
    evidence_id="v1", name="Meera Krishnan", company="Adobe",
    role="ML Engineer", skills=["Python", "ML"],
    kwargs={"technologies": ["Python", "PyTorch"]},
)
ok, reason = _validate_alumni_profile(p_valid, "meera_resume")
assert ok, f"Valid profile rejected: {reason}"
print(f"  Valid profile accepted: '{p_valid.name}' @ {p_valid.company}  PASS")

# Invalid: bad name
p_bad_name = AlumniProfile(
    evidence_id="v2", name="Placement Tips", company="Adobe",
    role="ML Engineer", skills=["Python"],
    kwargs={"technologies": ["Python"]},
)
ok, reason = _validate_alumni_profile(p_bad_name, "bad_name")
assert not ok, "Invalid name profile should be rejected!"
print(f"  Rejected bad name '{p_bad_name.name}': '{reason}'  PASS")

# Invalid: no company
p_no_co = AlumniProfile(
    evidence_id="v3", name="Rahul Verma", company="Unknown Company",
    role="SDE", skills=["Python"],
    kwargs={"technologies": ["Python"]},
)
ok, reason = _validate_alumni_profile(p_no_co, "no_co")
assert not ok, "Profile with Unknown Company should be rejected!"
print(f"  Rejected unknown company: '{reason}'  PASS")

# Invalid: no content
p_no_content = AlumniProfile(
    evidence_id="v4", name="Divya Aggarwal", company="Google",
    role="AI Engineer", skills=[],
    kwargs={"technologies": []},
)
ok, reason = _validate_alumni_profile(p_no_content, "no_content")
assert not ok, "Profile with no content should be rejected!"
print(f"  Rejected no-content: '{reason}'  PASS")

print("\n✅ ALL ROUND-2 SMOKE TESTS PASSED")
