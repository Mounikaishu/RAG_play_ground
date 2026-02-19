from typing import TypedDict, List

class SummaryState(TypedDict):
    raw_text: str
    chunks: List[str]
    chunk_summaries: List[str]
    final_summary: str
