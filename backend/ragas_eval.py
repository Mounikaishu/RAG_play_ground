from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall
)

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.embeddings import HuggingFaceEmbeddings


# -------------------------
# Gemini LLM
# -------------------------

GOOGLE_API_KEY = "AIzaSyCTW8i1glxFDUE9qMQgV2wUvJ-p2PRpEQk"

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=GOOGLE_API_KEY
)

# -------------------------
# Embeddings
# -------------------------

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

# -------------------------
# Example Dataset
# -------------------------

data = {
    "question": [
        "What are my strengths?"
    ],

    "answer": [
        "You are strong in Python and problem solving."
    ],

    "contexts": [[
        "Student solved 348 LeetCode problems and has Python projects."
    ]],

    "ground_truth": [
        "Strong in Python and problem solving."
    ]
}

dataset = Dataset.from_dict(data)

print("Starting evaluation...")

result = evaluate(
    dataset=dataset,
    metrics=[
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall
    ],
    llm=llm,
    embeddings=embeddings
)

print("Evaluation completed")
print(result)