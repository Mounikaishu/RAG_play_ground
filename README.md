# 🧠 PlaceAI - Agentic RAG Placement Mentor

---

## Overall Workflow

```mermaid
flowchart LR

A[Student Query]
-->B(Query Analyzer)

B-->C(Collection Selector)

C-->D[Resume Collection]
C-->E[Interview Collection]
C-->F[Placement Docs]
C-->G[Alumni Collection]

D-->H(Retriever)
E-->H
F-->H
G-->H

H-->I(RRF)

I-->J(Weighted Reranker)

J-->K(Context Refinement)

K-->L(Structured Evidence)

L-->M(Prompt Builder)

M-->N(Groq Llama)

N-->O(Personalized Response)
```
```mermaid
graph TD

Start

-->AnalyzeQuery

AnalyzeQuery

-->SelectCollection

SelectCollection

-->Retrieve

Retrieve

-->RRF

RRF

-->WeightedReranker

WeightedReranker

-->RefineContext

RefineContext

-->ResumeParser

ResumeParser

-->PromptBuilder

PromptBuilder

-->LLM

LLM

-->End
```
```mermaid
flowchart LR

PDF

-->Docling

Docling

-->Chunking

Chunking

-->Embedding

Embedding

-->ChromaDB

```
```mermaid
flowchart TD

Resume

-->SectionDetection

SectionDetection

-->Education

SectionDetection

-->Projects

SectionDetection

-->Skills

SectionDetection

-->Achievements

SectionDetection

-->Certifications

Projects

-->StudentProfile

Skills

-->StudentProfile

Education

-->StudentProfile

Achievements

-->StudentProfile

Certifications

-->StudentProfile
```
```mermaid
graph LR

Query

-->Embedding

Embedding

-->VectorSearch

VectorSearch

-->RRF

RRF

-->WeightedReranker

WeightedReranker

-->ContextRefinement

ContextRefinement

-->Prompt
```
```mermaid
graph TD

UserQuestion

-->IntentDetection

IntentDetection

-->ResumeReview

IntentDetection

-->InterviewPrep

IntentDetection

-->Roadmap

IntentDetection

-->SkillGap

ResumeReview

-->LLM

InterviewPrep

-->LLM

Roadmap

-->LLM

SkillGap

-->LLM
```
| Traditional ChatGPT | PlaceAI |
|--------------------|---------|
| Generic Answers | Personalized Guidance |
| No Resume Understanding | Resume Parsing |
| No Institution Knowledge | Uses Placement Database |
| Hallucinates | Grounded on RAG |
| Fixed Workflow | Agentic Workflow |
## ⭐ STAR

### Situation

Placement information was scattered across resumes, interview experiences, and reports, making personalized guidance difficult.

### Task

Develop an AI Placement Mentor capable of understanding student profiles and institutional placement data.

### Action

Built an Agentic RAG system using LangGraph, ChromaDB, Docling, BGE embeddings, custom Weighted Reranker, Resume Parser, and Dynamic Mentor.

### Result

Successfully generated personalized resume reviews, skill-gap analysis, interview preparation, and career roadmaps grounded in institutional knowledge.
Frontend

React

Backend

FastAPI

Workflow

LangGraph

Framework

LangChain

Parser

Docling

Embeddings

BGE

Vector DB

ChromaDB

LLM

Groq Llama 3.3

Fallback

Gemini

Language

Python