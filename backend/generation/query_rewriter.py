"""
query_rewriter.py — Phase 3: Production-Quality Query Rewriting Module

PURPOSE
-------
Improve retrieval quality by transforming vague, ambiguous, or abbreviated user queries
into precise, semantically rich queries before they reach the Retrieval Engine.

DESIGN PRINCIPLES
-----------------
1. Smart Rewrites Only     — Leave well-formed, specific queries unchanged.
2. Intent Preservation     — Never alter what the user is asking; only clarify it.
3. No Hallucination        — The rewriter NEVER invents facts, names, or companies.
4. Abbreviation Expansion  — Expand domain-specific abbreviations (ML, DS, SDE, etc.)
5. Fallback Safety         — If the LLM call fails, return the original query unmodified.
6. Observable              — Emits structured logs for every rewrite decision.

INTEGRATION
-----------
This module is injected as a LangGraph node (`rewrite_query_node`) that runs BEFORE
the `retrieve_all_node`. The rewritten query is stored in `state["rewritten_query"]`
and used by all downstream retrieval operations. The original query is preserved in
`state["original_query"]` for transparency and debugging.

USAGE
-----
    from generation.query_rewriter import QueryRewriter

    rewriter = QueryRewriter()
    result = rewriter.rewrite("ML job at FAANG")
    # RewriteResult(
    #     original="ML job at FAANG",
    #     rewritten="machine learning engineer job opportunities at top tech companies",
    #     was_rewritten=True,
    #     reason="Expanded abbreviations and vague terms"
    # )
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional

from llm import llm_call

logger = logging.getLogger("uvicorn.error")

# ──────────────────────────────────────────────────────────────────────────────
# Domain Abbreviation Map
# Expanded BEFORE sending to LLM — deterministic, no LLM needed for simple cases
# ──────────────────────────────────────────────────────────────────────────────
ABBREVIATION_MAP: dict[str, str] = {
    r"\bML\b": "machine learning",
    r"\bDL\b": "deep learning",
    r"\bDS\b": "data science",
    r"\bDE\b": "data engineering",
    r"\bSDE\b": "software development engineer",
    r"\bSWE\b": "software engineer",
    r"\bSWED\b": "software engineer",
    r"\bNLP\b": "natural language processing",
    r"\bCV\b": "computer vision",
    r"\bAI\b": "artificial intelligence",
    r"\bLLM\b": "large language model",
    r"\bFAANG\b": "top tech companies (Facebook, Amazon, Apple, Netflix, Google)",
    r"\bMNC\b": "multinational company",
    r"\bCSE\b": "computer science and engineering",
    r"\bECE\b": "electronics and communication engineering",
    r"\bGPA\b": "grade point average",
    r"\bCGPA\b": "cumulative grade point average",
    r"\bOA\b": "online assessment",
    r"\bHR\b": "human resources",
    r"\bCTC\b": "cost to company (salary package)",
    r"\bLPA\b": "lakhs per annum",
    r"\bPPO\b": "pre-placement offer",
    r"\bDB\b": "database",
    r"\bSQL\b": "structured query language",
    r"\bNoSQL\b": "NoSQL database",
    r"\bAPI\b": "application programming interface",
    r"\bREST\b": "REST API",
    r"\bDSA\b": "data structures and algorithms",
    r"\bOS\b": "operating systems",
    r"\bOOPS\b": "object-oriented programming",
    r"\bOOP\b": "object-oriented programming",
    r"\bCP\b": "competitive programming",
    r"\bSD\b": "system design",
    r"\bA2Z\b": "complete end-to-end",
}

# ──────────────────────────────────────────────────────────────────────────────
# Heuristics: when is a query already "specific enough" to skip LLM rewriting?
# ──────────────────────────────────────────────────────────────────────────────
# A query is considered SPECIFIC if:
#   - It is longer than 12 words
#   - It contains a proper company name (Google, Amazon, etc.)
#   - It already contains highly specific technical terms
SPECIFIC_COMPANY_NAMES = {
    "google", "amazon", "microsoft", "apple", "meta", "netflix", "adobe",
    "flipkart", "infosys", "wipro", "tcs", "accenture", "deloitte", "oracle",
    "salesforce", "jpmorgan", "goldman sachs", "morgan stanley", "goldman",
    "morgan", "uber", "airbnb", "linkedin", "twitter", "tesla", "nvidia",
    "qualcomm", "samsung", "intel", "amd", "ibm", "cisco", "vmware",
    "byju", "swiggy", "zomato", "paytm", "phonepe", "razorpay", "meesho",
    "ola", "oyo", "cred", "freshworks", "zoho", "mindtree", "hexaware",
}

VAGUE_TRIGGERS = {
    "jobs for me", "help me", "what should i do", "tell me", "show me",
    "i need", "any tips", "how to", "give me", "find me", "suggest",
    "explain", "analyse my", "analyze my", "check my", "review my",
}


# ──────────────────────────────────────────────────────────────────────────────
# Result Data Class
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class RewriteResult:
    """Structured output of a single query rewrite operation."""
    original: str
    rewritten: str
    was_rewritten: bool
    reason: str
    abbreviations_expanded: list[str]


# ──────────────────────────────────────────────────────────────────────────────
# QueryRewriter — Main Class
# ──────────────────────────────────────────────────────────────────────────────
class QueryRewriter:
    """
    Production-quality query rewriter for the PlaceAI RAG system.

    Rewrites vague or abbreviated user queries into precise, semantically rich
    queries that improve ChromaDB retrieval quality without altering user intent.

    The rewriter uses a two-pass strategy:
      Pass 1 — Deterministic abbreviation expansion (no LLM needed)
      Pass 2 — LLM-based semantic rewriting (only if needed)
    """

    SYSTEM_PROMPT_TEMPLATE = """\
You are a search query expander for a university placement RAG system.

Your ONLY task: expand abbreviations and clarify ambiguous wording in the user's query.

STRICT RULES:
1. EXPAND ABBREVIATIONS ONLY: Replace acronyms with their full forms (ML → Machine Learning).
2. PRESERVE INTENT EXACTLY: Do NOT change what the user is asking about.
3. DO NOT INVENT INTENT: Never convert a keyword into a question, career advice, or a roadmap request.
4. DO NOT ADD CONTEXT: Never add "how to become", "career path", "required skills", "roadmap", etc.
5. KEEP IT SHORT: Output 1 sentence or a short phrase — not a paragraph.
6. RETURN ONLY THE REWRITTEN QUERY. No explanation, no prefix, no quotes.
7. If the query has no abbreviations and is already clear, return it UNCHANGED.

EXAMPLES (follow these exactly):
  Input: ML               → Output: Machine Learning
  Input: SDE job          → Output: Software Development Engineer job
  Input: FAANG interview  → Output: top tech company interview
  Input: DSA tips         → Output: data structures and algorithms tips
  Input: Who joined Google → Output: Who joined Google
  Input: ML career path   → Output: Machine Learning career path
  Input: show me resumes  → Output: show me resumes

Domain Context: {context_hint}

Original Query: {query}

Rewritten Query:"""

    def __init__(self, min_rewrite_length: int = 10):
        """
        Args:
            min_rewrite_length: Minimum character length for the LLM output to be
                                accepted as a valid rewrite. Below this threshold,
                                the original query is used as a safety fallback.
        """
        self.min_rewrite_length = min_rewrite_length

    # ── Public API ────────────────────────────────────────────────────────────

    def rewrite(
        self,
        query: str,
        context_hint: str = "",
    ) -> RewriteResult:
        """
        Rewrites a user query for better retrieval.

        Args:
            query:        Raw user input from the LangGraph state.
            context_hint: Optional domain context e.g. "career goal is SDE at Google".

        Returns:
            RewriteResult with original, rewritten, and metadata.
        """
        if not query or not query.strip():
            return RewriteResult(
                original=query,
                rewritten=query,
                was_rewritten=False,
                reason="Empty query — returned as-is",
                abbreviations_expanded=[],
            )

        original_query = query.strip()

        # ── Pass 1: Deterministic abbreviation expansion ───────────────────
        expanded_query, expanded_abbrevs = self._expand_abbreviations(original_query)

        # ── Short-circuit: already specific + no abbreviations found ───────
        if not expanded_abbrevs and self._is_already_specific(original_query):
            logger.info(f"[QueryRewriter] SKIP — query already specific: '{original_query}'")
            return RewriteResult(
                original=original_query,
                rewritten=original_query,
                was_rewritten=False,
                reason="Query already specific and well-formed",
                abbreviations_expanded=[],
            )

        # ── Pass 2: LLM-based semantic rewriting ──────────────────────────
        rewritten = self._llm_rewrite(expanded_query, context_hint)

        # Safety check: if LLM output is suspiciously short, fall back
        if len(rewritten) < self.min_rewrite_length:
            logger.warning(
                f"[QueryRewriter] LLM returned short output ({len(rewritten)} chars), "
                f"falling back to abbreviation-expanded query."
            )
            rewritten = expanded_query

        was_rewritten = rewritten.lower() != original_query.lower()
        reason = self._build_reason(expanded_abbrevs, was_rewritten)

        logger.info(
            f"[QueryRewriter] Original: '{original_query}' | "
            f"Rewritten: '{rewritten}' | Was rewritten: {was_rewritten}"
        )

        return RewriteResult(
            original=original_query,
            rewritten=rewritten,
            was_rewritten=was_rewritten,
            reason=reason,
            abbreviations_expanded=expanded_abbrevs,
        )

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _expand_abbreviations(self, query: str) -> tuple[str, list[str]]:
        """
        Replaces known abbreviations in the query with their full forms.

        Returns:
            (expanded_query, list_of_abbreviations_that_were_expanded)
        """
        expanded = query
        found: list[str] = []

        for pattern, replacement in ABBREVIATION_MAP.items():
            new_expanded = re.sub(pattern, replacement, expanded)
            if new_expanded != expanded:
                # Extract the actual abbreviation text that was matched
                match = re.search(pattern, query)
                if match:
                    found.append(match.group(0))
                expanded = new_expanded

        return expanded, found

    def _is_already_specific(self, query: str) -> bool:
        """
        Returns True if the query appears specific enough to skip LLM rewriting.

        Heuristics:
          - More than 12 words → already verbose/specific
          - Contains a recognized company name
          - Does NOT contain any vague trigger phrases
        """
        words = query.lower().split()
        word_count = len(words)

        # Too long — already detailed
        if word_count > 12:
            return True

        # Contains specific company name — likely specific intent
        query_lower = query.lower()
        for company in SPECIFIC_COMPANY_NAMES:
            if company in query_lower:
                # But only if it doesn't also have a vague trigger
                for trigger in VAGUE_TRIGGERS:
                    if trigger in query_lower:
                        return False
                return True

        # Contains vague trigger phrases → needs rewriting
        for trigger in VAGUE_TRIGGERS:
            if trigger in query_lower:
                return False

        # Short query (≤ 5 words) → probably vague
        if word_count <= 5:
            return False

        return True

    def _llm_rewrite(self, query: str, context_hint: str) -> str:
        """
        Sends the query to the LLM for semantic rewriting.

        Uses llm_call() from backend/llm.py which provides:
          - Primary: Groq (llama-3.3-70b-versatile)
          - Fallback chain: other Groq models → Gemini models → mock
        """
        prompt = self.SYSTEM_PROMPT_TEMPLATE.format(
            query=query,
            context_hint=context_hint if context_hint else "university placement, career guidance, resume analysis",
        )

        try:
            response = llm_call(prompt)
            rewritten = response.strip() if response else query

            # Strip common LLM prefixes that can slip through
            prefixes_to_strip = [
                "rewritten query:", "rewritten:", "output:", "result:",
                "answer:", "query:", "here is", "here's",
            ]
            rewritten_lower = rewritten.lower()
            for prefix in prefixes_to_strip:
                if rewritten_lower.startswith(prefix):
                    rewritten = rewritten[len(prefix):].strip()
                    rewritten_lower = rewritten.lower()

            # Strip surrounding quotes if LLM wrapped the output
            rewritten = rewritten.strip('"\'')

            return rewritten if rewritten else query

        except Exception as exc:
            logger.warning(f"[QueryRewriter] LLM call failed: {exc} — returning original")
            return query

    @staticmethod
    def _build_reason(expanded_abbrevs: list[str], was_rewritten: bool) -> str:
        """Builds a human-readable reason string for the rewrite decision."""
        parts = []
        if expanded_abbrevs:
            parts.append(f"Expanded abbreviations: {', '.join(expanded_abbrevs)}")
        if was_rewritten:
            parts.append("LLM semantic rewriting applied")
        if not parts:
            return "Query already specific — no rewriting needed"
        return "; ".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# Module-level singleton (shared instance for efficiency)
# ──────────────────────────────────────────────────────────────────────────────
_rewriter_instance: Optional[QueryRewriter] = None


def get_query_rewriter() -> QueryRewriter:
    """Returns the module-level singleton QueryRewriter instance."""
    global _rewriter_instance
    if _rewriter_instance is None:
        _rewriter_instance = QueryRewriter()
    return _rewriter_instance
