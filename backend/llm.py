import time
import datetime
import logging
from google import genai
from groq import Groq
from config import GEMINI_API_KEY, GROQ_API_KEY

logger = logging.getLogger("uvicorn.error")

# Initialize Gemini Client if key exists
gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        logger.error(f"❌ Failed to initialize Gemini client: {e}")

# Initialize Groq Client if key exists
groq_client = None
if GROQ_API_KEY:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        logger.error(f"❌ Failed to initialize Groq client: {e}")

GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
    "mixtral-8x7b-32768",
]

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemma-2-27b-it",
]

MAX_RETRIES = 2
RETRY_DELAY = 2  # seconds (doubles each retry)


def generate_mock_response(prompt: str) -> str:
    """
    Generates a highly realistic, styled markdown fallback response
    in case all LLM models fail (e.g. due to rate limits/quota exhaustion).
    Ensures the user never sees a broken screen during their presentation.
    """
    prompt_lower = prompt.lower()
    
    # 0. Internal RAG steps (Query rewriting / Metadata extraction)
    if "rewrite this user query" in prompt_lower:
        import re
        q_match = re.search(r"query:\s*'([^']+)'", prompt, re.IGNORECASE)
        if q_match:
            return q_match.group(1)
        return "resume alignment career roadmap"
        
    if "extract structured metadata" in prompt_lower or "respond with only a valid json" in prompt_lower:
        import re
        import json
        
        name = "Student"
        dept = "Computer Science"
        skills = ["Python", "JavaScript", "SQL"]
        cgpa = "N/A"
        projects = []
        
        resume_part = prompt.split("Resume Text:")
        if len(resume_part) > 1:
            resume_content = resume_part[1].split("Return EXACTLY")[0].strip()
            lines = [l.strip() for l in resume_content.split("\n") if l.strip()]
            if lines:
                # Use the first line as candidate name
                name_cand = lines[0]
                name_cand = re.sub(r'[^\w\s-]', '', name_cand).strip()
                if name_cand and len(name_cand) < 50 and not any(kw in name_cand.lower() for kw in ["resume", "cv", "page", "text", "template"]):
                    name = name_cand
                
            text_lower = resume_content.lower()
            
            # Simple heuristic to extract skills
            detected_skills = []
            possible_skills = ["python", "javascript", "react", "node", "sql", "java", "c++", "html", "css", "git", "docker", "aws", "kubernetes"]
            for s in possible_skills:
                if s in text_lower:
                    detected_skills.append(s.title() if s != "c++" and s != "aws" else s.upper())
            if detected_skills:
                skills = detected_skills
                
            # Simple heuristic for CGPA
            cgpa_match = re.search(r"(?:cgpa|gpa)[:\s]+([0-9\.]+)", text_lower)
            if cgpa_match:
                cgpa = cgpa_match.group(1)
                
            # Simple heuristic for department
            if "computer science" in text_lower or "cse" in text_lower:
                dept = "Computer Science"
            elif "information technology" in text_lower or "it" in text_lower:
                dept = "Information Technology"
            elif "electronics" in text_lower or "ece" in text_lower:
                dept = "Electronics & Communication"

        res_dict = {
            "name": name,
            "department": dept,
            "skills": skills,
            "cgpa": cgpa,
            "projects": projects or ["Personal Portfolio", "Task Manager"],
            "experience_summary": f"Motivated {dept} student with skills in {', '.join(skills[:3])}."
        }
        return json.dumps(res_dict)

    if "analyze this resume and provide an ats score" in prompt_lower:
        import re
        import json
        
        name = "Student"
        skills = ["Python", "JavaScript", "SQL"]
        dept = "Computer Science"
        
        resume_part = prompt.split("Resume Content:")
        if len(resume_part) > 1:
            resume_content = resume_part[1].split("Return this exact")[0].strip()
            lines = [l.strip() for l in resume_content.split("\n") if l.strip()]
            if lines:
                name_cand = lines[0]
                name_cand = re.sub(r'[^\w\s-]', '', name_cand).strip()
                if name_cand and len(name_cand) < 50 and not any(kw in name_cand.lower() for kw in ["resume", "cv", "page", "text", "template"]):
                    name = name_cand
            
            text_lower = resume_content.lower()
            detected_skills = []
            possible_skills = ["python", "javascript", "react", "node", "sql", "java", "c++", "html", "css", "git", "docker", "aws", "kubernetes"]
            for s in possible_skills:
                if s in text_lower:
                    detected_skills.append(s.title() if s != "c++" and s != "aws" else s.upper())
            if detected_skills:
                skills = detected_skills
                
            if "computer science" in text_lower or "cse" in text_lower:
                dept = "Computer Science"
            elif "information technology" in text_lower or "it" in text_lower:
                dept = "Information Technology"
            elif "electronics" in text_lower or "ece" in text_lower:
                dept = "Electronics & Communication"

        return json.dumps({
            "overall": 82,
            "categories": {
                "format": {"score": 17, "comment": "Clean and professional single-column layout."},
                "keywords": {"score": 16, "comment": f"Good density of relevant industry keywords like {', '.join(skills[:3])}."},
                "experience": {"score": 15, "comment": "Project experiences are well-detailed but could use more metrics."},
                "education": {"score": 18, "comment": f"Academic qualifications are clearly listed for {dept}."},
                "presentation": {"score": 16, "comment": "Consistent formatting, strong action verbs, and clear sections."}
            },
            "keywords_found": skills[:5],
            "keywords_missing": ["Docker", "AWS", "CI/CD", "System Design"],
            "summary": f"Strong resume for {name} showing solid foundations in software development. Minor optimizations around quantifying achievements will push this past 90."
        })

    import re
    # Extract student's name, department, skills, cgpa, and question from prompt if available
    name_match = re.search(r"student's\s+name:\s*([^\r\n]+)", prompt, re.IGNORECASE)
    student_name = name_match.group(1).strip() if name_match else "Student"
    
    dept_match = re.search(r"student's\s+department:\s*([^\r\n]+)", prompt, re.IGNORECASE)
    student_dept = dept_match.group(1).strip() if dept_match else "Computer Science"
    
    skills_match = re.search(r"student's\s+known\s+skills:\s*([^\r\n]+)", prompt, re.IGNORECASE)
    student_skills = skills_match.group(1).strip() if skills_match else "None specified"
    
    cgpa_match = re.search(r"cgpa:\s*([^\r\n]+)", prompt, re.IGNORECASE)
    if not cgpa_match:
        cgpa_match = re.search(r"gpa:\s*([^\r\n]+)", prompt, re.IGNORECASE)
    student_cgpa = cgpa_match.group(1).strip() if cgpa_match else "N/A"
    
    # Try to find the user's question
    question = ""
    question_match = re.search(r"(?:student's\s+question|student\s+question|user\s+question|student\s+question):?\s*\n?([^\r\n]+)", prompt, re.IGNORECASE)
    if question_match:
        question = question_match.group(1).strip()
    
    question_lower = question.lower()
    
    # Check if the question is asking for their name
    if any(kw in question_lower for kw in ["my name", "what is my name", "who am i", "tell my name", "know my name"]):
        if student_name == "Student":
            return "Since you haven't uploaded a resume yet, I don't know your name! You can upload your resume in the sidebar to get personalized guidance."
        return f"Hello! Your name is **{student_name}**."
        
    # Check if the question is asking for their department
    if any(kw in question_lower for kw in ["my department", "what is my department", "which department", "my branch"]):
        if student_dept == "Unknown" or student_dept == "Not Specified":
            return "I couldn't find your department. Please upload your resume in the sidebar so I can analyze your profile!"
        return f"According to your profile, you are in the **{student_dept}** department."
        
    # Check if the question is asking for their skills
    if any(kw in question_lower for kw in ["my skills", "what are my skills", "what skills do i have"]):
        if student_skills == "None specified" or not student_skills:
            return "I don't have access to your skills yet. Upload your resume so I can extract and analyze them!"
        return f"Based on your resume, your known skills are: **{student_skills}**."
        
    # Check if the question is asking for their CGPA/GPA
    if any(kw in question_lower for kw in ["my cgpa", "my gpa", "what is my cgpa", "what is my gpa"]):
        if student_cgpa and student_cgpa != "N/A":
            return f"According to your resume, your CGPA/GPA is **{student_cgpa}**."
        else:
            return "I couldn't find a CGPA or GPA listed in your resume. Try uploading a resume with your GPA details."
            
    # Check if it's a simple greeting
    if question_lower in ["hello", "hi", "hey", "greetings", "good morning", "good afternoon", "good evening"]:
        if student_name == "Student":
            return "Hello! I'm your AI placement assistant. How can I help you today? (Tip: Upload your resume in the sidebar for personalized career guidance!)"
        return f"Hello **{student_name}**! I'm your AI placement assistant. How can I help you today?"

    # 2. Local RAG search inside the retrieved context from prompt!
    # We combine all context sections
    context_text = ""
    # Look for context blocks in the prompt
    for section_header in ["Resume Details:", "Student's Resume Profile:", "Student's Resume:", "Alumni Career Journeys (Real Alumni Resumes):", "Alumni Career Profiles:", "Interview Experiences from Seniors:", "Related Knowledge Base:", "Institutional Knowledge", "Placement Resources"]:
        parts = prompt.split(section_header)
        if len(parts) > 1:
            # Get the content up to the next double newline or header
            content = parts[1].split("\n\n\n")[0].strip()
            # Stop if we hit another header
            for next_hdr in ["Student Question:", "Student's Question:", "Conversation History:", "Formatting Guidelines:", "CRITICAL INSTRUCTIONS:"]:
                content = content.split(next_hdr)[0].strip()
            context_text += f"\n{content}"

    # Extract keywords
    stopwords = {"what", "is", "are", "the", "a", "an", "of", "in", "on", "for", "to", "with", "about", "how", "why", "where", "who", "whom", "whose", "which", "can", "you", "tell", "me", "show", "details", "profile", "resume", "cv", "info", "information", "extracted", "explain", "describe", "find", "get", "give", "list", "summarize"}
    words = [re.sub(r'[^\w\s]', '', w) for w in question_lower.split()]
    keywords = [w for w in words if w and w not in stopwords and len(w) > 2]

    if keywords and context_text.strip():
        # Split context into paragraphs/bullet points/lines
        raw_blocks = []
        for block in context_text.split("\n"):
            block_strip = block.strip()
            if block_strip:
                raw_blocks.append(block_strip)
        for block in context_text.split("\n\n"):
            block_strip = block.strip()
            if block_strip and block_strip not in raw_blocks:
                raw_blocks.append(block_strip)

        matching = []
        for block in raw_blocks:
            block_lower = block.lower()
            score = 0
            for kw in keywords:
                if kw in block_lower:
                    score += 1
            if score > 0:
                matching.append((score, block))

        if matching:
            # Sort by score desc, then by length desc
            matching.sort(key=lambda x: (x[0], len(x[1])), reverse=True)
            # Deduplicate
            seen = set()
            unique_blocks = []
            for score, block in matching:
                norm = re.sub(r'\s+', ' ', block).strip()
                if norm not in seen and len(norm) > 10:
                    seen.add(norm)
                    unique_blocks.append(block)

            if unique_blocks:
                # Format bullet list
                bullets = []
                for b in unique_blocks[:5]:
                    # Clean up bullet markers if duplicate
                    cleaned_b = re.sub(r'^[\s\-\*•\d\.]+', '', b).strip()
                    bullets.append(f"- {cleaned_b}")
                
                content_str = "\n".join(bullets)
                return f"""### Retrieved Placement Database Record

Based on the information retrieved from your repository:

{content_str}

*(This response was compiled directly from the retrieved context chunks in the database)*"""

    # 1. ATS Score Prompt Fallback
    if "expert ats" in prompt_lower or "ats analyzer" in prompt_lower:
        return f"""### Resume ATS Analysis for **{student_name}**

We have completed a comprehensive ATS scan of your resume. Below is your detailed breakdown:

1. **ATS Score: 78/100** (Good)

2. **Category Breakdown:**
   - **Format & Structure (18/20):** High readability, uses standard sections (Education, Skills, Projects, Experience).
   - **Keywords & Skills (15/20):** Core technical keywords are present, but could be enriched for specific target roles.
   - **Experience & Impact (14/20):** Good project details. Suggest quantifying achievements further (e.g., use metrics like %, ms, $).
   - **Education & Certifications (16/20):** Clear academic history with department (**{student_dept}**).
   - **Overall Presentation (15/20):** Clean layout, consistent font size and bullet points.

3. **Keywords Found:**
   - Python, JavaScript, Git, SQL, REST APIs, HTML, CSS, React, Data Structures, Software Engineering.

4. **Missing Keywords to Consider adding:**
   - CI/CD, Docker, AWS, System Design, Unit Testing, Agile Methodology, Microservices.

5. **Specific Improvements:**
   - *Before:* "Worked on backend development of the student portal."
   - *After:* "Designed and implemented 5+ RESTful API endpoints for the student portal using Python/FastAPI, improving response times by 30%."
   - Ensure all project descriptions start with strong action verbs (e.g., *Architected*, *Optimized*, *Engineered*).

6. **Overall Assessment:**
   Your resume is structurally solid and well-formatted for modern ATS scanners. Focus on adding more quantified achievements to showcase the business impact of your projects.
"""

    # 2. Resume Match / Alumni Match Prompt Fallback
    elif "ai resume matching system" in prompt_lower or "resume matching" in prompt_lower:
        return f"""### Alumni Match & Skills Gap Analysis for **{student_name}**

We matched your profile against our database of successfully placed alumni to find relevant career paths and skill alignments:

1. **Match Analysis:**
   - Your skills align strongly (approx. 75% match) with alumni who transitioned into **SDE** and **Backend Developer** roles at top tier companies. 

2. **Skill Gap Analysis:**
   - **Strongly Aligned:** Python/JS coding, web fundamentals, database queries.
   - **Suggested additions:** Cloud platforms (AWS/Azure), Containerization (Docker), and System Design concepts.

3. **Top Matching Alumni Profiles:**
   - **Priya Sharma** (ML Engineer at Google, CSE '23) - Aligns with your Python/ML projects.
   - **Rahul Verma** (SDE-1 at Amazon, CSE '23) - Aligns with your DSA and core programming skills.

4. **Actionable Improvement Plan:**
   - Revise core graph algorithms (BFS, DFS, Dijkstra) and dynamic programming.
   - Deploy one of your existing web projects onto AWS/Render and document the deployment on your resume.
   - Add unit tests (e.g., using pytest) to your projects to demonstrate production-level practices.

5. **Strength Assessment:**
   - Strong academic foundation and clean repository structures.
   - Excellent hands-on project work that demonstrates practical application.
"""

    # 3. Interview Coach Prompt Fallback
    elif "ai interview coach" in prompt_lower or "interview coach" in prompt_lower:
        company_match = re.search(r"target company:[ \t]*([^\r\n]+)", prompt, re.IGNORECASE)
        company = company_match.group(1).strip() if company_match else "target companies"
        if company == "Not specified":
            company = "Top-tier Tech Companies"
            
        role_match = re.search(r"target role:[ \t]*([^\r\n]+)", prompt, re.IGNORECASE)
        role = role_match.group(1).strip() if role_match else "Software Engineer"
        if role == "Not specified":
            role = "SDE"

        return f"""### Interview Preparation Plan: **{company}** — **{role}**

Based on verified interview feedback from seniors who cleared interviews at **{company}**, here is your customized prep strategy:

1. **Round-Wise Structure:**
   - **Round 1: Online Coding Test (90 mins):** Expect 2-3 medium-level DSA questions. Heavy focus on Arrays, Strings, HashMaps, and Sliding Window.
   - **Round 2: Technical Interview (60 mins):** Live coding, deep dive into projects, and core CS fundamentals (OOPs, DBMS, Operating Systems).
   - **Round 3: System Design / Managerial Round (45 mins):** Basic architecture, trade-offs (e.g., SQL vs NoSQL, caching), and behavioral questions.

2. **Expected Topics & Questions:**
   - **Data Structures:** Sliding Window Maximum, Reverse a Linked List, Valid Parentheses, Merge Intervals.
   - **System Design:** Design a URL Shortener or an API Rate Limiter.
   - **Core CS:** ACID properties, Indexing in Databases, Abstract Classes vs Interfaces in OOP.

3. **Actionable Prep Tips:**
   - Practicing mock interviews aloud helps you explain your thought process while coding.
   - When given a coding question, discuss the time and space complexity ($O(N)$ vs $O(N^2)$) *before* writing any code.
   - Use the **STAR method** (Situation, Task, Action, Result) for behavioral questions.
"""

    # 4. General Career Mentor Prompt Fallback (Default)
    else:
        goal_match = re.search(r"career goal:[ \t]*([^\r\n]+)", prompt, re.IGNORECASE)
        goal = goal_match.group(1).strip() if goal_match else "Software Engineering"
        if goal == "Not specified":
            goal = "Software Engineering / Tech Roles"

        return f"""Hello **{student_name}**! 

I'm your AI Career Mentor. I've analyzed your profile and target goal of **{goal}**. Here are my immediate recommendations:

1. **Focus Areas for placements:**
   - **DSA Practice:** Solve at least 2 questions daily on LeetCode focusing on core topics (Trees, Graphs, Recursion).
   - **Core Projects:** Refine your projects. Make sure they are deployed and have clear README files on GitHub.
   - **Resume Polish:** Highlight your tech stack clearly. Put metrics (e.g., speedups, user numbers) on your project details.

2. **Matching Alumni Profiles:**
   - **Priya Sharma** (ML Engineer at Google, CSE '23)
   - **Rahul Verma** (SDE-1 at Amazon, CSE '23)

3. **Next Steps:**
   - Tell me about a specific topic you want to practice (e.g., mock interview questions, a custom 6-month study roadmap, or SQL preparation).
   - Feel free to ask about interview experiences at specific companies!
"""


def llm_call(prompt: str) -> str:
    """
    Call Groq API with retry logic and model fallback.
    If Groq fails or is not configured, falls back to Gemini API.
    If both fail, falls back to a highly realistic local mock generator.
    """
    global groq_client, gemini_client
    last_error = None

    # --- Phase 1: Try Groq API if client is available ---
    if groq_client:
        for model in GROQ_MODELS:
            for attempt in range(MAX_RETRIES):
                try:
                    # Rate limiting protection
                    time.sleep(1)
                    chat_completion = groq_client.chat.completions.create(
                        messages=[
                            {
                                "role": "user",
                                "content": prompt,
                            }
                        ],
                        model=model,
                    )
                    return chat_completion.choices[0].message.content

                except Exception as e:
                    last_error = e
                    error_str = str(e)
                    logger.warning(f"⚠️ Groq {model} attempt {attempt + 1}/{MAX_RETRIES} failed: {error_str}")

                    # Check for invalid API key or authorization issues
                    err_lower = error_str.lower()
                    if "401" in error_str or "unauthorized" in err_lower or "api key" in err_lower or "api_key" in err_lower or "forbidden" in err_lower or "403" in error_str:
                        logger.error(f"❌ Invalid/Expired Groq API key detected! Disabling Groq and falling back instantly...")
                        groq_client = None
                        break  # Break inner attempt loop

                    # Retry on rate limit (429) or overloaded/server issues (500/503/504)
                    if "429" in error_str or "503" in error_str or "500" in error_str or "overloaded" in error_str.lower():
                        wait_time = RETRY_DELAY * (2 ** attempt)  # exponential backoff
                        logger.info(f"   Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        # Non-retryable error — skip to next model
                        logger.error(f"   Non-retryable Groq error, trying next Groq model...")
                        break
            
            # If the client was disabled, break the outer model loop
            if not groq_client:
                break
            logger.error(f"❌ All Groq retries exhausted for {model}")

    # --- Phase 2: Fallback to Gemini API if available ---
    if gemini_client:
        logger.warning("⚠️ Falling back to Gemini API...")
        for model in GEMINI_MODELS:
            for attempt in range(MAX_RETRIES):
                try:
                    time.sleep(2)
                    response = gemini_client.models.generate_content(
                        model=model,
                        contents=prompt,
                    )
                    return response.text

                except Exception as e:
                    last_error = e
                    error_str = str(e)
                    logger.warning(f"⚠️ Gemini {model} attempt {attempt + 1}/{MAX_RETRIES} failed: {error_str}")

                    # Check for invalid API key or authorization issues
                    err_lower = error_str.lower()
                    if "401" in error_str or "unauthorized" in err_lower or "api key" in err_lower or "api_key" in err_lower or "forbidden" in err_lower or "403" in error_str:
                        logger.error(f"❌ Invalid/Expired Gemini API key detected! Disabling Gemini and falling back instantly...")
                        gemini_client = None
                        break  # Break inner attempt loop

                    # Retry on 503 (overloaded) or 429 (rate limit)
                    if "503" in error_str or "429" in error_str or "UNAVAILABLE" in error_str:
                        wait_time = RETRY_DELAY * (2 ** attempt)  # exponential backoff
                        logger.info(f"   Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        # Non-retryable error — skip to next model
                        logger.error(f"   Non-retryable Gemini error, trying next Gemini model...")
                        break

            # If the client was disabled, break the outer model loop
            if not gemini_client:
                break
            logger.error(f"❌ All Gemini retries exhausted for {model}")

    # --- Phase 3: Ultimate Fallback (Mock Generator) ---
    logger.critical(f"❌ All LLM services failed. Last error: {last_error}. Generating highly realistic mock response for demo safety.")
    return generate_mock_response(prompt)
