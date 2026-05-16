import os
import pandas as pd
from datasets import Dataset
from graph.workflow import build_placement_graph
from ragas import evaluate
from ragas.metrics import (
    answer_relevancy,
    faithfulness,
    context_recall,
    context_precision,
)
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

# 1. Initialize your specific LangGraph
placement_graph = build_placement_graph()

# 2. Define Test Questions
test_questions = [
    {
        "question": "What is the typical interview process for a SWE role at Goldman Sachs?",
        "ground_truth": "The Goldman Sachs SWE interview process typically involves an online assessment (HackerRank), followed by 1-2 technical phone screens focusing on DSA (arrays, strings, trees), and finally 3-4 onsite/virtual rounds covering advanced DSA, system design, and behavioral/culture fit."
    },
    {
        "question": "How can I improve my resume for ATS parsers?",
        "ground_truth": "To improve your resume for ATS parsers, use standard section headings (Experience, Education, Skills), avoid complex formatting like tables or graphics, use a standard font, and ensure keywords from the job description are naturally integrated into your bullet points."
    }
]

def generate_ragas_dataset(test_cases):
    """Run questions through the actual LangGraph and extract contexts."""
    data = {"question": [], "answer": [], "contexts": [], "ground_truth": []}
    
    for case in test_cases:
        question = case["question"]
        
        # EXACT state dictionary used in routers/student_router.py
        state = {
            "user_id": "dummy_student",
            "student_name": "Test Student",
            "student_dept": "Computer Science",
            "student_skills": "Python, React, Machine Learning",
            "question": question,
            "mode": "mentor", # Using mentor mode for general questions
            "context_kb": "",
            "context_resume": "",
            "context_interviews": "",
            "context_alumni": "",
            "context_placement": "",
            "answer": "",
            "history": [],
            "career_goal": "",
            "target_company": "",
            "target_role": "",
        }
        
        print(f"\nProcessing query: {question}")
        # Run through the graph
        result = placement_graph.invoke(state)
        
        # Extract the final answer
        answer = result.get("answer", "")
        
        # Extract ALL contexts retrieved by Chroma in your graph
        # Ragas expects a list of strings for contexts
        contexts = []
        for ctx_key in ["context_kb", "context_interviews", "context_alumni", "context_resume", "context_placement"]:
            ctx_data = result.get(ctx_key, "")
            if ctx_data and isinstance(ctx_data, str) and ctx_data.strip():
                # We can split by chunks if you formatted them that way, or just pass the whole string as one chunk
                contexts.append(ctx_data)
        
        data["question"].append(question)
        data["answer"].append(answer)
        data["contexts"].append(contexts)
        data["ground_truth"].append(case["ground_truth"])
        
    return Dataset.from_dict(data)

def main():
    print("Step 1: Generating answers and retrieving contexts using your actual LangGraph...")
    eval_dataset = generate_ragas_dataset(test_questions)
    
    # 3. Setup Ragas Evaluation (Using Gemini)
    if "GOOGLE_API_KEY" not in os.environ:
        print("\n⚠️ WARNING: GOOGLE_API_KEY environment variable is not set!")
        print("Please set it before running the evaluation. E.g.:")
        print("$env:GOOGLE_API_KEY='your-key-here'  # PowerShell")
        print("export GOOGLE_API_KEY='your-key-here' # Bash")
        return

    print("\nStep 2: Initializing Gemini Evaluator...")
    evaluator_llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash") 
    evaluator_embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    
    print("\nStep 3: Running Ragas evaluation...")
    # Note: Using Ragas 0.4.3
    result = evaluate(
        dataset=eval_dataset,
        metrics=[
            context_precision,
            faithfulness,
            answer_relevancy,
            context_recall,
        ],
        llm=evaluator_llm,
        embeddings=evaluator_embeddings
    )
    
    print("\nStep 4: Saving results...")
    df = result.to_pandas()
    df.to_csv("ragas_evaluation_results.csv", index=False)
    
    print("\n✅ Evaluation complete! Results saved to ragas_evaluation_results.csv")
    print(df.head())

if __name__ == "__main__":
    main()
