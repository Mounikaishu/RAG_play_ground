"""
test_weighted_reranker.py — Unit tests for rag_core/stages/weighted_reranker.py

Self-contained: uses only stdlib `assert` and `math`.
No pytest / test framework required.

Run:
    cd backend
    python test_weighted_reranker.py
"""
import sys
import os
import math

sys.path.insert(0, os.path.dirname(__file__))

from rag_core.stages.weighted_reranker import (
    weighted_rerank,
    metadata_score,
    section_score,
    completeness_score,
    RerankerWeights,
    _retrieval_score_from_chunk,
)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_chunk(
    text: str = "Sample chunk text with reasonable length for testing purposes.",
    metadata: dict = None,
    distance: float = 0.3,
    rrf_score: float = None,
) -> dict:
    chunk = {"text": text, "metadata": metadata or {"source_file": "test.pdf"}, "distance": distance}
    if rrf_score is not None:
        chunk["rrf_score"] = rrf_score
    return chunk


def _assert_score_in_range(val: float, name: str) -> None:
    assert 0.0 <= val <= 1.0, f"{name} must be in [0.0, 1.0], got {val}"


# ──────────────────────────────────────────────────────────────────────────────
# metadata_score()
# ──────────────────────────────────────────────────────────────────────────────

def test_metadata_score_full():
    meta = {
        "source_file": "alumni.pdf",
        "document_id": "doc_001",
        "collection": "alumni_resumes",
        "section": "experience",
    }
    score = metadata_score(meta)
    _assert_score_in_range(score, "metadata_score full")
    assert score == 1.0, f"Full metadata should score 1.0, got {score}"
    print(f"  metadata_score (full)              = {score:.4f}  ✓")


def test_metadata_score_partial():
    meta = {"source_file": "kb.txt", "collection": "institutional_kb"}
    score = metadata_score(meta)
    _assert_score_in_range(score, "metadata_score partial")
    assert 0.0 < score < 1.0, f"Partial metadata should score between 0 and 1, got {score}"
    print(f"  metadata_score (partial)           = {score:.4f}  ✓")


def test_metadata_score_empty():
    score = metadata_score({})
    assert score == 0.0, f"Empty metadata should score 0.0, got {score}"
    print(f"  metadata_score (empty)             = {score:.4f}  ✓")


def test_metadata_score_none():
    score = metadata_score(None)
    assert score == 0.0, f"None metadata should score 0.0, got {score}"
    print(f"  metadata_score (None)              = {score:.4f}  ✓")


# ──────────────────────────────────────────────────────────────────────────────
# section_score()
# ──────────────────────────────────────────────────────────────────────────────

def test_section_score_known_high_value():
    for sec in ["experience", "projects", "skills"]:
        meta = {"section": sec}
        score = section_score(meta)
        _assert_score_in_range(score, f"section_score({sec})")
        assert score >= 0.85, f"High-value section '{sec}' should score ≥ 0.85, got {score}"
        print(f"  section_score ('{sec}')         = {score:.4f}  ✓")


def test_section_score_empty_section():
    score = section_score({"source_file": "doc.pdf"})
    assert score == 0.5, f"Missing section should return neutral 0.5, got {score}"
    print(f"  section_score (no section key)     = {score:.4f}  ✓")


def test_section_score_unknown_section():
    score = section_score({"section": "hobbies_and_interests"})
    _assert_score_in_range(score, "section_score unknown")
    assert score < 0.5, f"Unknown section should score < 0.5, got {score}"
    print(f"  section_score (unknown section)    = {score:.4f}  ✓")


def test_section_score_empty_metadata():
    score = section_score({})
    assert score == 0.0, f"Empty metadata should score 0.0, got {score}"
    print(f"  section_score (empty meta)         = {score:.4f}  ✓")


# ──────────────────────────────────────────────────────────────────────────────
# completeness_score()
# ──────────────────────────────────────────────────────────────────────────────

def test_completeness_score_ideal():
    text = " ".join(["word"] * 80)  # 80 words — ideal range
    score = completeness_score(text)
    assert score == 1.0, f"80-word chunk should score 1.0, got {score}"
    print(f"  completeness_score (80 words)      = {score:.4f}  ✓")


def test_completeness_score_short():
    text = "few words"
    score = completeness_score(text)
    _assert_score_in_range(score, "completeness_score short")
    assert score < 0.5, f"Very short chunk should score < 0.5, got {score}"
    print(f"  completeness_score (2 words)       = {score:.4f}  ✓")


def test_completeness_score_long():
    text = " ".join(["word"] * 400)  # 400 words — verbose
    score = completeness_score(text)
    _assert_score_in_range(score, "completeness_score long")
    assert score < 0.75, f"400-word chunk should score < 0.75, got {score}"
    print(f"  completeness_score (400 words)     = {score:.4f}  ✓")


def test_completeness_score_empty():
    score = completeness_score("")
    assert score == 0.0, f"Empty text should score 0.0, got {score}"
    print(f"  completeness_score (empty)         = {score:.4f}  ✓")


# ──────────────────────────────────────────────────────────────────────────────
# _retrieval_score_from_chunk()
# ──────────────────────────────────────────────────────────────────────────────

def test_retrieval_score_rrf_path():
    chunk = {"rrf_score": 0.020}
    score = _retrieval_score_from_chunk(chunk)
    _assert_score_in_range(score, "_retrieval_score rrf")
    print(f"  retrieval_score (rrf_score=0.020)  = {score:.4f}  ✓")


def test_retrieval_score_distance_path():
    chunk = {"distance": 0.2}
    score = _retrieval_score_from_chunk(chunk)
    _assert_score_in_range(score, "_retrieval_score dist")
    assert score > 0.5, f"Low distance (0.2) should give score > 0.5, got {score}"
    print(f"  retrieval_score (distance=0.2)     = {score:.4f}  ✓")


def test_retrieval_score_fallback():
    chunk = {}
    score = _retrieval_score_from_chunk(chunk)
    assert score == 0.5, f"No signal should return 0.5, got {score}"
    print(f"  retrieval_score (no fields)        = {score:.4f}  ✓")


# ──────────────────────────────────────────────────────────────────────────────
# RerankerWeights.validate()
# ──────────────────────────────────────────────────────────────────────────────

def test_weights_valid_default():
    w = RerankerWeights()
    w.validate()  # must not raise
    print("  RerankerWeights (default) validate = PASS  ✓")


def test_weights_invalid_sum():
    w = RerankerWeights(semantic=0.9, metadata=0.9)
    try:
        w.validate()
        assert False, "validate() should raise ValueError for bad weights"
    except ValueError:
        print("  RerankerWeights (bad sum) ValueError  ✓")


# ──────────────────────────────────────────────────────────────────────────────
# weighted_rerank() — Integration tests
# ──────────────────────────────────────────────────────────────────────────────

_CHUNKS = [
    _make_chunk(
        text="Python FastAPI developer with experience in REST APIs and microservices.",
        metadata={"source_file": "alumni1.pdf", "document_id": "d001", "collection": "alumni_resumes", "section": "experience"},
        distance=0.15,
        rrf_score=0.025,
    ),
    _make_chunk(
        text="Machine learning engineer skilled in TensorFlow, PyTorch, and scikit-learn.",
        metadata={"source_file": "alumni2.pdf", "document_id": "d002", "collection": "alumni_resumes", "section": "skills"},
        distance=0.25,
        rrf_score=0.018,
    ),
    _make_chunk(
        text="Summary: Placement guide.",
        metadata={},
        distance=0.90,
    ),
]


def test_output_type_and_length():
    result = weighted_rerank("Python developer", _CHUNKS)
    assert isinstance(result, list), "weighted_rerank must return a list"
    assert len(result) == len(_CHUNKS), "Length must be preserved"
    print(f"  weighted_rerank output type+length = PASS  ✓")


def test_final_score_added():
    result = weighted_rerank("Python developer", _CHUNKS)
    for chunk in result:
        assert "final_score" in chunk, "Each chunk must have 'final_score' key"
        assert isinstance(chunk["final_score"], float), "'final_score' must be float"
    print("  final_score key added to all chunks = PASS  ✓")


def test_text_and_metadata_not_mutated():
    import copy
    original_texts = [c["text"] for c in _CHUNKS]
    original_metas = [copy.deepcopy(c.get("metadata", {})) for c in _CHUNKS]

    weighted_rerank("Python developer", _CHUNKS)

    for i, chunk in enumerate(_CHUNKS):
        assert chunk["text"] == original_texts[i], f"text mutated for chunk {i}"
        assert chunk.get("metadata", {}) == original_metas[i], f"metadata mutated for chunk {i}"
    print("  text + metadata immutability       = PASS  ✓")


def test_sorted_descending():
    result = weighted_rerank("Python developer", _CHUNKS)
    scores = [c["final_score"] for c in result]
    assert scores == sorted(scores, reverse=True), "Result must be sorted descending by final_score"
    print("  sorted descending by final_score   = PASS  ✓")


def test_empty_chunks():
    result = weighted_rerank("any query", [])
    assert result == [], "Empty input must return empty list"
    print("  empty chunks → []                  = PASS  ✓")


def test_empty_query_fallback():
    """Empty query should still return a valid list (semantic score defaults to 0)."""
    result = weighted_rerank("", _CHUNKS)
    assert isinstance(result, list), "Even with empty query, must return list"
    assert len(result) == len(_CHUNKS), "No chunks should be dropped for empty query"
    print("  empty query → valid list returned  = PASS  ✓")


def test_custom_weights():
    custom_w = RerankerWeights(
        semantic=0.10,
        metadata=0.40,
        section=0.20,
        completeness=0.20,
        retrieval=0.10,
    )
    result = weighted_rerank("Python developer", _CHUNKS, weights=custom_w)
    assert len(result) == len(_CHUNKS), "Custom weights must return all chunks"
    print("  custom weights accepted            = PASS  ✓")


def test_scores_in_range():
    result = weighted_rerank("Python developer", _CHUNKS)
    for chunk in result:
        s = chunk["final_score"]
        assert 0.0 <= s <= 1.0, f"final_score {s} out of [0.0, 1.0]"
    print("  all final_scores in [0.0, 1.0]     = PASS  ✓")


# ──────────────────────────────────────────────────────────────────────────────
# Run all tests
# ──────────────────────────────────────────────────────────────────────────────

def run_all():
    tests = [
        # metadata_score
        test_metadata_score_full,
        test_metadata_score_partial,
        test_metadata_score_empty,
        test_metadata_score_none,
        # section_score
        test_section_score_known_high_value,
        test_section_score_empty_section,
        test_section_score_unknown_section,
        test_section_score_empty_metadata,
        # completeness_score
        test_completeness_score_ideal,
        test_completeness_score_short,
        test_completeness_score_long,
        test_completeness_score_empty,
        # retrieval_score
        test_retrieval_score_rrf_path,
        test_retrieval_score_distance_path,
        test_retrieval_score_fallback,
        # RerankerWeights
        test_weights_valid_default,
        test_weights_invalid_sum,
        # weighted_rerank
        test_output_type_and_length,
        test_final_score_added,
        test_text_and_metadata_not_mutated,
        test_sorted_descending,
        test_empty_chunks,
        test_empty_query_fallback,
        test_custom_weights,
        test_scores_in_range,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ FAILED: {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ ERROR:  {test.__name__}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'─' * 60}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("\n✅ ALL WEIGHTED RERANKER TESTS PASSED")
    else:
        print(f"\n❌ {failed} TEST(S) FAILED")
        sys.exit(1)


if __name__ == "__main__":
    print("=" * 60)
    print("  WeightedReranker Test Suite")
    print("=" * 60)
    run_all()
