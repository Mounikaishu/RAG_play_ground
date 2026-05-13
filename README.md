# 🎓 PlaceAI — AI-Powered Placement & Career Guidance Platform

An intelligent, multi-user placement ecosystem for universities built with **FastAPI**, **React**, **ChromaDB**, **LangGraph**, and **Google Gemini AI**. It provides students with personalized career guidance, ATS resume analysis, and interview preparation — while giving the placement cell powerful candidate search and analytics tools.

---

## 📑 Table of Contents

- [Architecture Overview](#architecture-overview)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Authentication System](#authentication-system)
- [Database & Storage](#database--storage)
- [Resume Processing Pipeline](#resume-processing-pipeline)
- [Knowledge Base System](#knowledge-base-system)
- [LangGraph AI Workflow](#langgraph-ai-workflow)
- [API Endpoints Reference](#api-endpoints-reference)
- [User Flows](#user-flows)
- [Setup & Installation](#setup--installation)
- [Environment Variables](#environment-variables)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     FRONTEND (React.js)                         │
│  ┌──────────┐  ┌──────────────────┐  ┌───────────────────────┐  │
│  │Login/Reg │  │Student Dashboard │  │Placement Cell Dashboard│  │
│  │  Page    │  │Career|Interview  │  │Search|KB|Analytics     │  │
│  │          │  │ATS|Resume Match  │  │Bulk Register|Upload    │  │
│  └──────────┘  └──────────────────┘  └───────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP (axios)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   BACKEND (FastAPI)                              │
│                                                                 │
│  ┌─────────────┐  ┌───────────────┐  ┌────────────────────┐    │
│  │ Auth Router  │  │Student Router │  │ Placement Router   │    │
│  │/auth/*      │  │/student/*     │  │ /placement/*       │    │
│  └──────┬──────┘  └───────┬───────┘  └─────────┬──────────┘    │
│         │                 │                     │               │
│  ┌──────▼──────┐  ┌───────▼───────────────────  │               │
│  │ auth.py     │  │  LangGraph Workflow       │ │               │
│  │ JWT tokens  │  │  ┌─────┐ ┌────┐ ┌──────┐ │ │               │
│  │ password    │  │  │Retr.│→│Route│→│Generate│ │               │
│  │ hashing     │  │  │KB   │ │Mode │ │Answer │ │               │
│  └──────┬──────┘  │  └─────┘ └────┘ └──────┘ │ │               │
│         │         └───────────┬───────────────┘ │               │
│  ┌──────▼──────┐              │                 │               │
│  │ database.py │      ┌───────▼───────┐  ┌──────▼──────┐       │
│  │ users.json  │      │  Gemini LLM   │  │metadata_    │       │
│  └─────────────┘      │  (llm.py)     │  │extractor.py │       │
│                       └───────────────┘  └─────────────┘       │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              ChromaDB (In-Memory Vector Store)           │    │
│  │                                                         │    │
│  │  ┌──────────────────┐  ┌─────────────────────────────┐  │    │
│  │  │ institutional_kb │  │ interview_experiences        │  │    │
│  │  │ Alumni profiles  │  │ Company-wise Q&A             │  │    │
│  │  │ Skill roadmaps   │  │ Round-specific experiences   │  │    │
│  │  │ Placement tips   │  └─────────────────────────────┘  │    │
│  │  │ ATS guides       │                                   │    │
│  │  └──────────────────┘  ┌─────────────────────────────┐  │    │
│  │                        │ student_resumes (main)       │  │    │
│  │  ┌──────────────────┐  │ All student resume chunks    │  │    │
│  │  │student_resumes_  │  └─────────────────────────────┘  │    │
│  │  │  2026            │                                   │    │
│  │  │  2027            │  ┌─────────────────────────────┐  │    │
│  │  │  2028  ← Year    │  │ department_resumes          │  │    │
│  │  │  2029    specific│  │ (resume_repository.py)       │  │    │
│  │  └──────────────────┘  └─────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | React.js, Axios, React Markdown | Single-page app with student & placement dashboards |
| **Backend** | FastAPI (Python) | REST API server with JWT authentication |
| **AI/LLM** | Google Gemini (gemini-3-flash-preview, 2.0-flash, 2.0-pro) | Career guidance, ATS analysis, interview prep |
| **Orchestration** | LangGraph (StateGraph) | Multi-step AI workflow with conditional routing |
| **Vector DB** | ChromaDB (in-memory) | Semantic search over resumes & knowledge base |
| **User DB** | JSON file (`users.json`) | Lightweight user account storage |
| **PDF Parsing** | PyPDF | Extract text from resume PDFs |

---

## Project Structure

```
llm_playground/
├── backend/
│   ├── .env                      # GEMINI_API_KEY
│   ├── main.py                   # FastAPI app entry point
│   ├── config.py                 # Environment config loader
│   ├── auth.py                   # JWT tokens, password hashing, DEFAULT_PASSWORD
│   ├── database.py               # User CRUD on users.json
│   ├── models.py                 # Pydantic request/response models
│   ├── llm.py                    # Gemini API calls with retry & model fallback
│   ├── pdf_loader.py             # PDF → raw text extraction
│   ├── chunker.py                # Text → overlapping chunks
│   ├── metadata_extractor.py     # LLM-based resume metadata extraction
│   ├── vectorstore.py            # Legacy single-resume ChromaDB store
│   ├── resume_repository.py      # Multi-student dept-level ChromaDB store
│   ├── state.py                  # Legacy chat state
│   ├── users.json                # User accounts database
│   ├── requirements.txt          # Python dependencies
│   │
│   ├── routers/
│   │   ├── auth_router.py        # /auth/* endpoints
│   │   ├── student_router.py     # /student/* endpoints
│   │   └── placement_router.py   # /placement/* endpoints
│   │
│   ├── graph/
│   │   ├── state.py              # PlacementState TypedDict
│   │   ├── nodes.py              # LangGraph node functions
│   │   └── workflow.py           # LangGraph workflow builder
│   │
│   └── knowledge_base/
│       ├── collections.py        # ChromaDB multi-collection manager
│       ├── kb_manager.py         # High-level KB API
│       └── kb_seeder.py          # Seeds KB with synthetic data on startup
│
└── frontend/
    └── src/
        ├── App.js                # Main app (Login, Student, Placement dashboards)
        ├── App.css               # Styling
        ├── index.js              # React entry
        └── context/
            └── AuthContext.js    # Auth state management (token, user, login/register)
```

---

## Authentication System

### How It Works

```
┌──────────────────────────────────────────────────────────┐
│                   REGISTRATION FLOW                       │
│                                                          │
│  Student provides:                                       │
│    • name              → "Mounika"                       │
│    • roll_no           → "24b01a1275" (= username)       │
│    • college_email     → "24b01a1275@svecw.edu.in"       │
│    • department        → "IT"                            │
│    • passing_out_year  → 2028                            │
│    • skills            → ["c++", "dsa"]                  │
│                                                          │
│  System auto-assigns:                                    │
│    • password = "svecw@2026" (DEFAULT_PASSWORD)          │
│    • year_of_study = computed from passing_out_year      │
│    • password_is_default = true                          │
│                                                          │
│  Response includes the default password so the student   │
│  knows what to use for first login.                      │
└──────────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Feature | Detail |
|---------|--------|
| **Username** | Registration number (roll_no), normalized to lowercase |
| **Default Password** | `svecw@2026` — same for all new users (defined in `auth.py → DEFAULT_PASSWORD`) |
| **College Email** | Must end with `@svecw.edu.in` — validated at Pydantic model level |
| **Passing Out Year** | Taken as input (not extracted from roll_no) to support lateral entries |
| **Year of Study** | Auto-computed: `4 - (passing_out_year - current_academic_year) + 1`, clamped 1–4 |
| **Password Change** | `POST /auth/change-password` — requires old password + new password (min 6 chars) |
| **Password Hashing** | SHA-256 with random 16-byte salt: `salt:hash` format |
| **JWT Tokens** | Custom Base64-encoded payload + HMAC-SHA256 signature, 7-day expiry |

### Password Hashing (auth.py)

```
Input: "svecw@2026"
        ↓
Generate random salt: "4221228963bd6fdb"
        ↓
SHA-256("4221228963bd6fdb" + "svecw@2026")
        ↓
Stored as: "4221228963bd6fdb:d0ec8d38f9505..."
```

### JWT Token Structure

```
Base64(JSON payload) + "." + HMAC-SHA256(payload, SECRET_KEY)

Payload contains:
{
  "roll_no": "24b01a1275",
  "role": "student",
  "name": "Mounika",
  "college_email": "24b01a1275@svecw.edu.in",
  "passing_out_year": 2028,
  "exp": 1747483200
}
```

---

## Database & Storage

### 1. User Database — `users.json`

A flat JSON file where keys are roll numbers:

```json
{
  "24b01a1275": {
    "name": "Mounika",
    "roll_no": "24b01a1275",
    "department": "IT",
    "password_hash": "salt:hash",
    "role": "student",
    "skills": ["c++", "dsa"],
    "college_email": "24b01a1275@svecw.edu.in",
    "passing_out_year": 2028,
    "year_of_study": 2,
    "password_is_default": false,
    "resume_uploaded": true,
    "conversations": {}
  }
}
```

**CRUD operations** are in `database.py`:
- `register_user()` → creates new entry
- `get_user()` → reads by roll_no (recomputes year_of_study dynamically)
- `update_user_profile()` → updates non-sensitive fields
- `update_password()` → changes password hash, sets `password_is_default: false`
- `get_students_by_year()` → filters by passing_out_year
- `get_available_years()` → returns all distinct years

### 2. Vector Database — ChromaDB (In-Memory)

ChromaDB stores document embeddings for semantic search. All collections are **in-memory** (reset on server restart).

#### Collections Map

| Collection Name | What It Stores | Seeded On Startup? | Metadata Fields |
|----------------|---------------|-------------------|-----------------|
| `institutional_kb` | Alumni profiles, skill roadmaps, ATS guides, placement tips | ✅ Yes (21 docs) | category, company, role, department, year |
| `interview_experiences` | Company-wise interview Q&A, round details | ✅ Yes (10 docs) | category, company, role, round |
| `student_resumes` | All student resume chunks (main/universal) | ❌ On upload | roll_no, student_name, department, skills, passing_out_year |
| `student_resumes_{year}` | Year-specific resume chunks (e.g., `student_resumes_2028`) | ❌ On upload | Same as above |
| `department_resumes` | Department-level resume repository | ❌ On bulk upload | student_name, department, skills, cgpa, projects, passing_out_year |

#### How Year-Specific Storage Works

```
Student uploads resume
        ↓
System reads passing_out_year from user profile (e.g., 2028)
        ↓
Resume chunks are stored in TWO collections:
  1. "student_resumes"      ← universal collection (backward compatible)
  2. "student_resumes_2028" ← year-specific collection
        ↓
Placement cell can search:
  • All students → queries "student_resumes"
  • 2028 batch only → queries "student_resumes_2028"
```

---

## Resume Processing Pipeline

### Step-by-Step Flow

```
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: PDF Upload                                          │
│ Student uploads resume.pdf via POST /student/upload-resume   │
│ File saved temporarily as temp_resume_{roll_no}.pdf          │
│ Module: student_router.py                                    │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 2: Text Extraction                                      │
│ PyPDF reads each page and concatenates text                  │
│ Module: pdf_loader.py → load_pdf()                           │
│ Output: raw string of all resume text                        │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 3: Chunking                                             │
│ Text split into overlapping chunks for better retrieval      │
│ Module: chunker.py → chunk_text_with_overlap()               │
│ Parameters: chunk_size=500 words, overlap=100 words          │
│ Output: ["chunk_0", "chunk_1", "chunk_2", ...]               │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 4: Store in ChromaDB                                    │
│ Each chunk stored with metadata in vector collections        │
│ Module: knowledge_base/collections.py → store_student_resume()│
│                                                              │
│ Stored in:                                                   │
│   • "student_resumes" (universal)                            │
│   • "student_resumes_{passing_out_year}" (year-specific)     │
│                                                              │
│ Each chunk gets:                                             │
│   ID: "resume_{roll_no}_{collection}_{chunk_index}"          │
│   Metadata: {roll_no, student_name, department, skills,      │
│              chunk_index, passing_out_year}                   │
│                                                              │
│ ChromaDB auto-generates embeddings using its default model   │
│ (all-MiniLM-L6-v2 sentence transformer)                     │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 5: Update User Profile                                  │
│ Set resume_uploaded=true in users.json                        │
│ Temp PDF file is deleted                                     │
└─────────────────────────────────────────────────────────────┘
```

### How Retrieval Works

```
Query: "students with Python and ML skills"
                    ↓
        ChromaDB embeds the query using
        the same sentence transformer model
                    ↓
        Cosine similarity search against
        all stored resume chunk embeddings
                    ↓
        Returns top-k most similar chunks
        with metadata and distance scores
                    ↓
        Results grouped by student_name,
        average distance → relevance score (0-100)
                    ↓
        Sorted by relevance, top 3 chunks per student returned
```

---

## Knowledge Base System

### Seeding (kb_seeder.py)

On first startup, ChromaDB is seeded with **31 synthetic documents**:

| Category | Count | Examples |
|----------|-------|---------|
| Alumni Profiles | 10 | Google ML Engineer, Amazon SDE-1, Microsoft Full-Stack |
| Interview Experiences | 10 | Amazon all rounds, Google technical, Flipkart machine coding |
| Skill Roadmaps | 6 | Backend Dev (6mo), AI/ML (8mo), Frontend (5mo), DSA (4mo) |
| Placement Resources | 5 | ATS guide, top 50 DSA questions, behavioral prep, system design |

### KB Manager (kb_manager.py)

High-level API for adding/searching:

| Function | Collection | Purpose |
|----------|-----------|---------|
| `add_alumni_profile()` | institutional_kb | Store alumni career journeys |
| `add_interview_experience()` | interview_experiences | Store company interview Q&A |
| `add_resource()` | institutional_kb | Store guides, roadmaps, tips |
| `search_knowledge()` | institutional_kb | Semantic search with optional category filter |
| `search_interviews()` | interview_experiences | Search with optional company filter |

---

## LangGraph AI Workflow

The chat system uses **LangGraph** to orchestrate a multi-step AI pipeline with conditional routing based on the user's selected mode.

### Workflow Graph

```
                    ┌──────────────┐
                    │  ENTRY POINT │
                    └──────┬───────┘
                           ▼
                  ┌─────────────────┐
                  │  retrieve_kb    │  Searches institutional_kb
                  │  (always runs)  │  for alumni, roadmaps, tips
                  └────────┬────────┘
                           ▼
                  ┌─────────────────┐
                  │retrieve_resume  │  Searches student_resumes
                  │ (always runs)   │  filtered by user's roll_no
                  └────────┬────────┘
                           ▼
                  ┌─────────────────┐
                  │  ROUTE BY MODE  │  Conditional branching
                  └───┬───┬───┬───┬─┘
                      │   │   │   │
         ┌────────────┘   │   │   └────────────┐
         ▼                ▼   ▼                ▼
  ┌────────────┐  ┌──────────┐ ┌─────┐  ┌─────────────┐
  │  mentor    │  │interview │ │ ats │  │resume_match │
  │  Career    │  │  _prep   │ │Score│  │ vs Alumni   │
  │  guidance  │  │Company Q&A│ │Check│  │  Compare    │
  └─────┬──────┘  └────┬─────┘ └──┬──┘  └──────┬──────┘
        │               │          │             │
        └───────┬───────┴──────┬───┘             │
                │              └─────────────────┘
                ▼
         ┌────────────┐
         │  memory    │  Appends Q&A to conversation history
         └─────┬──────┘
               ▼
            ┌─────┐
            │ END │
            └─────┘
```

### What Each Node Does

| Node | Input Context | LLM Prompt Role | Output |
|------|--------------|-----------------|--------|
| `retrieve_kb` | Searches `institutional_kb` with user's question + career goal | N/A (retrieval only) | `context_kb` |
| `retrieve_resume` | Searches `student_resumes` filtered by `roll_no` | N/A (retrieval only) | `context_resume` |
| `retrieve_interviews` | Searches `interview_experiences` filtered by company | N/A (retrieval only) | `context_interviews` |
| `mentor` | KB + Resume + History | "AI Career Mentor at university placement cell" | Personalized career guidance |
| `interview_prep` | Interviews + Resume + KB + History | "AI Interview Coach with real interview data" | Company-specific prep |
| `ats` | Resume + KB | "Expert ATS analyzer and resume reviewer" | ATS score breakdown |
| `resume_match` | Resume + KB (alumni) | "AI Resume Matching system" | Gap analysis vs placed alumni |
| `memory` | Previous Q&A | N/A | Appends to history (last 20 kept) |

### LLM Call Chain (llm.py)

```
Prompt sent to Gemini API
        ↓
Try model: gemini-3-flash-preview
  ├─ Success → return response
  └─ Fail (503/429) → retry with exponential backoff (2s, 4s)
        ↓ (all retries failed)
Try model: gemini-2.0-flash
  ├─ Success → return response
  └─ Fail → retry...
        ↓
Try model: gemini-2.0-pro → gemini-1.0-pro
        ↓ (all failed)
Return: "⚠️ AI model is busy right now."
```

---

## API Endpoints Reference

### Authentication (`/auth`)

| Endpoint | Method | Auth | Body | Description |
|----------|--------|------|------|-------------|
| `/auth/register` | POST | ❌ | `{name, roll_no, college_email, department, passing_out_year, skills[], role}` | Register with auto-assigned default password |
| `/auth/login` | POST | ❌ | `{roll_no, password}` | Login, returns JWT + warns if default password |
| `/auth/me` | GET | ✅ JWT | — | Get current user profile |
| `/auth/change-password` | POST | ✅ JWT | `{old_password, new_password}` | Change password (min 6 chars) |
| `/auth/bulk-register` | POST | ✅ Placement | `{students: [{name, roll_no, college_email, department, passing_out_year}]}` | Register multiple students at once |

### Student (`/student`)

| Endpoint | Method | Auth | Body | Description |
|----------|--------|------|------|-------------|
| `/student/upload-resume` | POST | ✅ JWT | `file` (multipart) | Upload PDF, stores in year-specific collection |
| `/student/chat` | POST | ✅ JWT | `{question, mode, career_goal?, target_company?, target_role?}` | Chat through LangGraph workflow |
| `/student/ats-score` | POST | ✅ JWT | — | Get structured ATS score JSON |
| `/student/profile` | GET | ✅ JWT | — | Get student profile |

### Placement Cell (`/placement`)

| Endpoint | Method | Auth | Body/Params | Description |
|----------|--------|------|-------------|-------------|
| `/placement/search` | POST | ✅ Placement | `{query, year?}` | Semantic search across resumes (optional year filter) |
| `/placement/upload-kb` | POST | ✅ Placement | `{title, content, category, company?, role?}` | Add document to knowledge base |
| `/placement/upload-resumes` | POST | ✅ Placement | `files[], passing_out_year` | Bulk upload resume PDFs |
| `/placement/students` | GET | ✅ Placement | `?year=2028` | List students (optional year filter) |
| `/placement/students/years` | GET | ✅ Placement | — | List all available passing out years |
| `/placement/analytics` | GET | ✅ Placement | `?year=2028` | Dashboard stats, skills, departments |
| `/placement/kb-documents` | GET | ✅ Placement | `?collection=...` | List KB documents |
| `/placement/kb/{doc_id}` | DELETE | ✅ Placement | — | Delete a KB document |

---

## User Flows

### Flow 1: New Student Registration & First Login

```
1. Placement cell bulk-registers students OR student self-registers
2. Account created with:
   • username = roll_no (e.g., "24b01a1275")
   • password = "svecw@2026" (default)
   • college_email validated as @svecw.edu.in
3. Student logs in with roll_no + default password
4. System warns: "You are using the default password"
5. Student changes password via /auth/change-password
6. password_is_default → false
```

### Flow 2: Resume Upload & Year-Based Storage

```
1. Student uploads resume PDF → POST /student/upload-resume
2. pdf_loader.py extracts raw text from PDF
3. chunker.py splits into 500-word chunks with 100-word overlap
4. System reads passing_out_year from user profile (e.g., 2028)
5. Chunks stored in ChromaDB:
   • "student_resumes" (universal, all years)
   • "student_resumes_2028" (year-specific)
6. Each chunk gets metadata: roll_no, name, department, skills, passing_out_year
7. users.json updated: resume_uploaded = true
```

### Flow 3: Student Chat (Career Guidance)

```
1. Student asks: "How do I prepare for Google?"
2. LangGraph workflow starts:
   a. retrieve_kb: Searches institutional_kb → finds Google alumni profile, roadmaps
   b. retrieve_resume: Searches student_resumes where roll_no=user → gets resume context
   c. route_by_mode: mode="mentor" → goes to mentor node
   d. mentor: Builds prompt with KB context + resume + history → calls Gemini
   e. memory: Saves Q&A to conversation history
3. AI response returned with personalized advice
```

### Flow 4: Placement Cell Searches by Year

```
1. Placement cell: POST /placement/search {query: "Python ML", year: 2028}
2. search_student_resumes() targets "student_resumes_2028" collection
3. ChromaDB semantic search returns top matching chunks
4. Results grouped by student, scored 0-100
5. Gemini ranks candidates with explanations
6. Response: {answer: "AI ranking...", candidates: [{name, skills, score}]}
```

---

## Setup & Installation

### Prerequisites

- Python 3.10+
- Node.js 18+
- Google Gemini API key

### Backend Setup

```bash
cd backend
pip install -r requirements.txt
# Create .env file
echo "GEMINI_API_KEY=your_key_here" > .env
# Run server
uvicorn main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm start
# Opens at http://localhost:3000
```

### Dependencies (requirements.txt)

```
fastapi          # Web framework
uvicorn          # ASGI server
google-genai     # Gemini AI SDK
langgraph        # AI workflow orchestration
pypdf            # PDF text extraction
python-dotenv    # .env file loading
chromadb         # Vector database
python-multipart # File upload support
```

---

## Environment Variables

| Variable | Location | Purpose |
|----------|----------|---------|
| `GEMINI_API_KEY` | `backend/.env` | Google Gemini API authentication |
| `JWT_SECRET` | `auth.py` (hardcoded, override via env) | JWT signing key |
| `REACT_APP_API_URL` | Frontend env | Backend URL (default: `http://localhost:8000`) |

---

## Important Notes

- **ChromaDB is in-memory** — all vector data is lost on server restart. The knowledge base is re-seeded automatically, but student resumes must be re-uploaded.
- **users.json is persistent** — user accounts survive restarts.
- **Default password** can be changed in `auth.py → DEFAULT_PASSWORD`.
- **College email domain** is validated as `@svecw.edu.in` in `models.py`.
- **Year of study** is dynamically recomputed on every profile read based on current date.
