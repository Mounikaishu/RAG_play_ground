"""
retrieval_models.py — Data Models for Retrieval Engine.

Defines structured objects for retrieval query analysis, search candidates,
and unified responses across all vector collections.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class RetrievalResult:
    """
    Structured retrieval candidate returned by the Retrieval Engine.

    Fields:
        content           -- Raw chunk text
        similarity_score  -- Relevance score (percentage 0.0 to 100.0)
        distance          -- Raw distance metric from ChromaDB (lower = more similar)
        collection        -- ChromaDB collection name
        metadata          -- Complete raw metadata dictionary
        source_file       -- Filename of source document
        page_number       -- Page number where chunk originated
        section           -- Section title / heading
        document_type     -- Document type (e.g. "resume", "interview_experience", "placement_material")
        company           -- Extracted company entity (if available)
        role              -- Extracted role entity (if available)
    """
    content: str
    similarity_score: float
    distance: float
    collection: str
    metadata: Dict[str, Any]
    source_file: str
    page_number: int
    section: str
    document_type: str
    company: Optional[str] = None
    role: Optional[str] = None


@dataclass
class QueryAnalysis:
    """
    Structured query intent and metadata filters extracted from natural language.

    Fields:
        original_query    -- User's original query
        cleaned_query     -- Cleaned query text
        detected_company  -- Normalized company name (e.g. "Google", "Amazon")
        detected_role     -- Normalized role (e.g. "Software Engineer")
        detected_job_type -- Normalized job type ("FTE" or "Internship")
        detected_difficulty -- "Easy", "Medium", or "Hard"
        detected_doc_type -- Targeted document type ("resume", "interview_experience", "placement_material")
        detected_round    -- Interview round name (e.g. "Technical Round 1")
        detected_section  -- Targeted section (e.g. "Projects", "Skills")
        filters           -- Formatted ChromaDB 'where' clause dictionary
    """
    original_query: str
    cleaned_query: str
    detected_company: Optional[str] = None
    detected_role: Optional[str] = None
    detected_job_type: Optional[str] = None
    detected_difficulty: Optional[str] = None
    detected_doc_type: Optional[str] = None
    detected_round: Optional[str] = None
    detected_section: Optional[str] = None
    filters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalResponse:
    """
    Unified response payload returned by the Retrieval Engine facade.
    """
    query: str
    query_analysis: QueryAnalysis
    results: List[RetrievalResult]
    total_found: int
    collections_searched: List[str]
    execution_time_ms: float
    collection_distribution: Dict[str, int] = field(default_factory=dict)
