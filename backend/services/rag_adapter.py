from rag_core.default_pipeline import DefaultRagPipeline
from rag_core.stages.retrieval import retrieve_chunks
from llm import llm_call

class ResumeRagPipeline(DefaultRagPipeline):
    """
    Extends the DefaultRagPipeline to support filtering by roll_no.
    Open/Closed Principle: We extend without modifying the shared core.
    """
    def __init__(self, collection_name: str, roll_no: str, **kwargs):
        super().__init__(collection_name, **kwargs)
        self.roll_no = roll_no

    def retrieve(self, query: str) -> list:
        """Stage 2: Search ChromaDB, filtered by roll_no."""
        where_filter = {"roll_no": self.roll_no} if self.roll_no else None
        return retrieve_chunks(
            query, 
            self.collection_name, 
            k=self.top_k * 3, 
            where=where_filter
        )

    def rewrite(self, query: str) -> str:
        """Stage 1: Override to use local Gemini LLM instead of shared Groq."""
        prompt = f"Rewrite this user query to be precise and searchable for resume analysis: '{query}'. Return ONLY the rewritten query."
        rewritten = llm_call(prompt)
        return rewritten if len(rewritten) > 10 else query

    def generate(self, query: str, context: str) -> str:
        """Stage 5: Override to use local Gemini LLM instead of shared Groq."""
        system = self.system_prompt or "You are an AI assistant."
        full_prompt = f"{system}\n\nCONTEXT:\n{context}\n\nUSER QUESTION: {query}\n\nANSWER:"
        return llm_call(full_prompt)


class ResumeRagAdapter:
    """
    Adapter that isolates the llm_playground project from direct
    RAG dependencies, satisfying the mentor's low coupling requirement.
    """
    def __init__(self, collection_name: str = "student_resumes"):
        self.collection_name = collection_name
        
    def get_resume_context(self, roll_no: str, query: str = "full resume skills experience education projects") -> list:
        """Helper to retrieve resume chunks without exposing the pipeline."""
        pipeline = ResumeRagPipeline(self.collection_name, roll_no=roll_no)
        return pipeline.retrieve(query)

    def analyze_resume(self, query: str, roll_no: str, context_hint: str = "student resume and career guidance", system_prompt: str = None) -> str:
        """Runs the entire 6-stage RAG pipeline for the given student."""
        pipeline = ResumeRagPipeline(
            collection_name=self.collection_name,
            roll_no=roll_no,
            context_hint=context_hint,
            system_prompt=system_prompt
        )
        return pipeline.run(query)

    def insert_resume(self, text: str, metadata: dict = None):
        """Helper to insert resume chunks via the pipeline's insert stage."""
        if metadata and "roll_no" in metadata:
            from knowledge_base.collections import get_collection
            try:
                collection = get_collection(self.collection_name)
                old = collection.get(where={"roll_no": metadata["roll_no"]}, include=["metadatas"])
                if old and old.get("ids"):
                    collection.delete(ids=old["ids"])
                    print(f"🗑️ Deleted {len(old['ids'])} old resume chunks for session {metadata['roll_no']}")
            except Exception as e:
                print(f"⚠️ Error clearing old resume chunks: {e}")

        # Using a dummy pipeline to just access the insert method
        pipeline = ResumeRagPipeline(self.collection_name, roll_no=None)
        return pipeline.insert(text, metadata)

    def generate(self, query: str, context: str, system_prompt: str = None) -> str:
        """Helper to directly generate responses using context (bypassing retrieval)."""
        pipeline = ResumeRagPipeline(self.collection_name, roll_no=None, system_prompt=system_prompt)
        return pipeline.generate(query, context)
