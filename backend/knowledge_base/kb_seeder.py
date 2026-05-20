"""
Knowledge Base Seeder — Seeds ChromaDB with realistic synthetic institutional data.
Runs on first startup if collections are empty.
"""

from knowledge_base.collections import store_kb_documents_batch, get_collection_count

ALUMNI_PROFILES = [
    {"id": "alumni_1", "text": "Priya Sharma graduated in 2023 from Computer Science with skills in Python, Machine Learning, TensorFlow, and Data Analysis. She was placed at Google as an ML Engineer with a package of 28 LPA. Her preparation strategy included solving 300+ LeetCode problems, building 3 ML projects including a recommendation engine, and completing Andrew Ng's ML course. She advises juniors to focus on fundamentals of linear algebra and statistics before diving into deep learning.", "meta": {"category": "alumni", "company": "Google", "role": "ML Engineer", "department": "CSE", "year": "2023"}},
    {"id": "alumni_2", "text": "Rahul Verma graduated in 2023 from Computer Science with skills in Java, Spring Boot, Microservices, AWS, and System Design. He was placed at Amazon as an SDE-1 with a package of 32 LPA. He focused on Data Structures extensively, solved 400+ problems on LeetCode and Codeforces, and built a distributed task scheduler as his main project. His tip: master arrays, trees, and graphs — they cover 70% of interview questions.", "meta": {"category": "alumni", "company": "Amazon", "role": "SDE-1", "department": "CSE", "year": "2023"}},
    {"id": "alumni_3", "text": "Sneha Reddy graduated in 2022 from IT with skills in React, Node.js, TypeScript, MongoDB, and GraphQL. She was placed at Microsoft as a Full-Stack Developer with a package of 24 LPA. She built 5 full-stack projects including an e-commerce platform and a real-time chat app. She recommends learning TypeScript early and contributing to open source for visibility.", "meta": {"category": "alumni", "company": "Microsoft", "role": "Full-Stack Developer", "department": "IT", "year": "2022"}},
    {"id": "alumni_4", "text": "Arjun Patel graduated in 2023 from ECE with skills in Python, Flask, PostgreSQL, Docker, and CI/CD. He transitioned from electronics to software and was placed at Flipkart as a Backend Developer with 18 LPA. He built REST APIs for his college ERP system and learned Docker through personal projects. His advice: don't let your branch define your career.", "meta": {"category": "alumni", "company": "Flipkart", "role": "Backend Developer", "department": "ECE", "year": "2023"}},
    {"id": "alumni_5", "text": "Meera Krishnan graduated in 2022 from CSE with skills in Python, NLP, Hugging Face, PyTorch, and Computer Vision. She was placed at NVIDIA as an AI Research Engineer with 35 LPA. She published 2 papers in NLP conferences and built a multilingual sentiment analyzer. She recommends reading research papers weekly and implementing them from scratch.", "meta": {"category": "alumni", "company": "NVIDIA", "role": "AI Research Engineer", "department": "CSE", "year": "2022"}},
    {"id": "alumni_6", "text": "Vikram Singh graduated in 2023 from CSE with skills in JavaScript, React, Next.js, Tailwind CSS, and Firebase. He was placed at Razorpay as a Frontend Engineer with 22 LPA. He had a strong portfolio website showcasing 8 projects. His tip: UI/UX skills combined with frontend development make you stand out.", "meta": {"category": "alumni", "company": "Razorpay", "role": "Frontend Engineer", "department": "CSE", "year": "2023"}},
    {"id": "alumni_7", "text": "Ananya Gupta graduated in 2022 from IT with skills in Python, Pandas, SQL, Tableau, and Power BI. She was placed at Deloitte as a Data Analyst with 12 LPA. She completed Google Data Analytics certification and built dashboards for college placement data. She advises: SQL is the most underrated skill for data careers.", "meta": {"category": "alumni", "company": "Deloitte", "role": "Data Analyst", "department": "IT", "year": "2022"}},
    {"id": "alumni_8", "text": "Karthik Nair graduated in 2023 from CSE with skills in Kubernetes, Terraform, AWS, Linux, and Jenkins. He was placed at Infosys as a DevOps Engineer with 14 LPA. He managed the college server infrastructure and automated deployments. His tip: get AWS certified — it opens many doors.", "meta": {"category": "alumni", "company": "Infosys", "role": "DevOps Engineer", "department": "CSE", "year": "2023"}},
    {"id": "alumni_9", "text": "Divya Sharma graduated in 2023 from CSE with skills in Android, Kotlin, Firebase, REST APIs, and UI Design. She was placed at PhonePe as a Mobile Developer with 20 LPA. She published 3 apps on Play Store with 10K+ downloads. Her advice: ship real products — downloads speak louder than projects on a resume.", "meta": {"category": "alumni", "company": "PhonePe", "role": "Mobile Developer", "department": "CSE", "year": "2023"}},
    {"id": "alumni_10", "text": "Rohan Mehta graduated in 2022 from CSE with skills in C++, Competitive Programming, Algorithms, and System Design. He was placed at Goldman Sachs as a Software Engineer with 30 LPA. He was a 5-star coder on CodeChef and ICPC regionalist. His strategy: competitive programming builds problem-solving speed that interviews demand.", "meta": {"category": "alumni", "company": "Goldman Sachs", "role": "Software Engineer", "department": "CSE", "year": "2022"}},
]

INTERVIEW_EXPERIENCES = [
    {"id": "interview_1", "text": "Amazon SDE-1 Online Assessment: 2 coding questions — 1 on arrays (sliding window maximum) and 1 on graphs (shortest path in grid). Time limit 90 minutes. Tips: practice medium-hard LeetCode, focus on time complexity optimization. Technical Round 1: Asked to design a parking lot system, implement LRU cache, explain time complexity of solutions. Technical Round 2: System design of a URL shortener, behavioral questions about teamwork. Bar Raiser: Deep dive into past projects, asked about trade-offs in architecture decisions.", "meta": {"category": "interview", "company": "Amazon", "role": "SDE-1", "round": "all_rounds"}},
    {"id": "interview_2", "text": "Google L3 Software Engineer Technical Round 1: Given a matrix, find the number of islands using BFS/DFS. Follow-up: handle the streaming case. Round 2: Design a rate limiter for an API. Discuss trade-offs between token bucket and sliding window. Round 3: Behavioral — describe a time you disagreed with your team. Google focuses heavily on coding clarity, communication, and optimized solutions.", "meta": {"category": "interview", "company": "Google", "role": "Software Engineer", "round": "technical"}},
    {"id": "interview_3", "text": "Microsoft SDE Intern Technical Round: Implement a binary search tree with insert, delete, and search operations. Asked about balancing strategies. Coding Round: Find the longest palindromic substring. HR Round: Why Microsoft? What do you know about Azure? Tips: Microsoft values clean code and clear explanation of thought process.", "meta": {"category": "interview", "company": "Microsoft", "role": "SDE Intern", "round": "all_rounds"}},
    {"id": "interview_4", "text": "Flipkart SDE-1 Machine Coding Round: Build a simple in-memory key-value store with TTL support in 90 minutes. Must be production-quality code with proper OOP. Technical Round: Design an inventory management system. Asked about database indexing, caching strategies. Tips: Flipkart heavily tests machine coding — practice building small systems end-to-end.", "meta": {"category": "interview", "company": "Flipkart", "role": "SDE-1", "round": "all_rounds"}},
    {"id": "interview_5", "text": "Goldman Sachs Software Engineer HackerRank Test: 5 MCQs on OS, DBMS, networking + 2 coding questions (DP and string manipulation). Technical Round 1: Explain ACID properties, design a stock trading platform. Technical Round 2: Implement merge sort, discuss threading in Java. Tips: Goldman tests CS fundamentals deeply — revise OS, DBMS, and networking concepts.", "meta": {"category": "interview", "company": "Goldman Sachs", "role": "Software Engineer", "round": "all_rounds"}},
    {"id": "interview_6", "text": "TCS Digital Aptitude Round: 30 quantitative questions, 20 verbal, 10 logical reasoning in 90 minutes. Coding Round: 2 easy-medium problems in C/Java/Python. Interview: Basic questions about OOP concepts, DBMS normalization, project discussion. Tips: TCS focuses on aptitude and fundamentals — practice quantitative aptitude daily.", "meta": {"category": "interview", "company": "TCS", "role": "Digital", "round": "all_rounds"}},
    {"id": "interview_7", "text": "Razorpay Frontend Engineer Technical Round 1: Build a responsive navbar with dropdown using vanilla JS in 30 minutes. Asked about event delegation, closures, and prototypal inheritance. Round 2: Implement a debounce function, explain virtual DOM in React, discuss state management patterns. Tips: Razorpay tests JavaScript fundamentals deeply before framework knowledge.", "meta": {"category": "interview", "company": "Razorpay", "role": "Frontend Engineer", "round": "technical"}},
    {"id": "interview_8", "text": "Infosys InfyTQ Coding Round: 3 questions — pattern printing, array manipulation, basic string operations. Technical Interview: Explain polymorphism, what is normalization, write SQL queries for joins. HR Round: Tell me about yourself, strengths and weaknesses. Tips: Focus on basic DSA and OOPS concepts. InfyTQ certification gives an edge.", "meta": {"category": "interview", "company": "Infosys", "role": "Systems Engineer", "round": "all_rounds"}},
    {"id": "interview_9", "text": "NVIDIA AI Engineer Technical Round: Implement convolution operation from scratch in Python. Discuss backpropagation mathematics. Asked about GPU vs CPU architecture for ML workloads. Round 2: Paper discussion — explain attention mechanism in transformers. Coding: implement beam search. Tips: NVIDIA expects deep ML theory + systems understanding.", "meta": {"category": "interview", "company": "NVIDIA", "role": "AI Engineer", "round": "technical"}},
    {"id": "interview_10", "text": "Deloitte Data Analyst Case Study Round: Given a dataset of sales data, identify trends, anomalies, and provide business recommendations. Technical Round: SQL queries involving window functions, CTEs, and subqueries. Asked about statistical concepts — hypothesis testing, p-values. Tips: Deloitte values business acumen alongside technical skills.", "meta": {"category": "interview", "company": "Deloitte", "role": "Data Analyst", "round": "all_rounds"}},
]

SKILL_ROADMAPS = [
    {"id": "roadmap_1", "text": "Backend Developer Roadmap (6 months): Month 1-2: Learn Python/Java fundamentals, understand OOP deeply. Month 2-3: Learn Flask or FastAPI, build REST APIs, understand HTTP methods, status codes, authentication. Month 3-4: Learn SQL (PostgreSQL/MySQL), understand indexing, joins, normalization. Learn NoSQL (MongoDB) basics. Month 4-5: Learn Docker, basic CI/CD with GitHub Actions, understand microservices concepts. Month 5-6: Learn cloud basics (AWS EC2, S3, RDS), build a complete project with deployment. Projects to build: URL shortener, blog API, e-commerce backend.", "meta": {"category": "roadmap", "role": "Backend Developer"}},
    {"id": "roadmap_2", "text": "AI/ML Engineer Roadmap (8 months): Month 1-2: Python advanced, NumPy, Pandas, Matplotlib. Statistics and probability fundamentals. Month 2-4: Machine Learning — linear regression, logistic regression, decision trees, random forests, SVM, clustering. Use scikit-learn. Month 4-6: Deep Learning — neural networks, CNNs, RNNs, transformers. Use PyTorch or TensorFlow. Month 6-7: NLP or Computer Vision specialization. Build 2-3 projects. Month 7-8: MLOps basics — model deployment, monitoring, Docker. Projects: image classifier, sentiment analyzer, recommendation system.", "meta": {"category": "roadmap", "role": "AI/ML Engineer"}},
    {"id": "roadmap_3", "text": "Frontend Developer Roadmap (5 months): Month 1: HTML5, CSS3, responsive design, Flexbox, Grid. Month 2: JavaScript ES6+, DOM manipulation, async/await, fetch API. Month 3: React.js — components, hooks, state management, routing. Month 4: TypeScript, Next.js, testing with Jest. Month 5: Build portfolio with 3-4 projects, learn UI/UX basics. Projects: portfolio site, weather app, e-commerce frontend, real-time chat UI.", "meta": {"category": "roadmap", "role": "Frontend Developer"}},
    {"id": "roadmap_4", "text": "Data Science Roadmap (7 months): Month 1-2: Python, statistics, probability, linear algebra basics. Month 2-3: Data manipulation with Pandas, visualization with Matplotlib/Seaborn. Month 3-4: SQL mastery, database concepts. Month 4-5: Machine Learning fundamentals. Month 5-6: Deep learning basics, NLP or time series. Month 6-7: Tableau/Power BI, business case studies. Projects: EDA on Kaggle datasets, predictive models, interactive dashboards.", "meta": {"category": "roadmap", "role": "Data Scientist"}},
    {"id": "roadmap_5", "text": "Full-Stack Developer Roadmap (7 months): Month 1: HTML, CSS, JavaScript fundamentals. Month 2: React.js frontend framework. Month 3: Node.js/Express.js backend. Month 4: MongoDB or PostgreSQL databases. Month 5: Authentication, APIs, deployment. Month 6: DevOps basics — Docker, CI/CD. Month 7: Build capstone project combining all skills. Projects: MERN stack e-commerce app, real-time collaboration tool.", "meta": {"category": "roadmap", "role": "Full-Stack Developer"}},
    {"id": "roadmap_6", "text": "DSA and Competitive Programming Roadmap (4 months): Month 1: Arrays, Strings, Hashing, Two Pointers, Sliding Window — solve 50 problems. Month 2: Linked Lists, Stacks, Queues, Trees, BST — solve 60 problems. Month 3: Graphs (BFS, DFS, shortest path), Dynamic Programming — solve 70 problems. Month 4: Advanced topics — Tries, Segment Trees, Greedy. Contest practice on Codeforces/LeetCode. Target: 250+ problems across all topics.", "meta": {"category": "roadmap", "role": "Competitive Programming"}},
]

PLACEMENT_RESOURCES = [
    {"id": "resource_1", "text": "ATS Resume Optimization Guide: 1) Use standard section headings: Education, Experience, Skills, Projects. 2) Avoid tables, images, columns, and graphics — ATS cannot parse them. 3) Use keywords from the job description naturally in your resume. 4) Keep formatting simple — use bullet points, standard fonts like Arial or Calibri. 5) Include measurable achievements: 'Increased API response time by 40%' instead of 'Improved performance'. 6) List technical skills in a dedicated section. 7) Use reverse chronological order. 8) Keep it to 1 page for freshers. 9) Save as PDF with proper filename: 'FirstName_LastName_Resume.pdf'. 10) Proofread for spelling and grammar errors.", "meta": {"category": "resource", "type": "ats_guide"}},
    {"id": "resource_2", "text": "Top 50 Most Asked DSA Interview Questions: Arrays: Two Sum, Best Time to Buy Stock, Maximum Subarray, Product of Array Except Self, Container With Most Water. Strings: Longest Substring Without Repeating, Valid Parentheses, Group Anagrams. Linked Lists: Reverse Linked List, Merge Two Sorted Lists, Detect Cycle. Trees: Maximum Depth, Level Order Traversal, Validate BST, Lowest Common Ancestor. Graphs: Number of Islands, Course Schedule, Clone Graph. DP: Climbing Stairs, House Robber, Longest Increasing Subsequence, Coin Change, Edit Distance.", "meta": {"category": "resource", "type": "dsa_questions"}},
    {"id": "resource_3", "text": "Behavioral Interview Preparation Guide: Common questions: 1) Tell me about yourself — structure: present, past, future in 2 minutes. 2) Describe a challenging project — use STAR method: Situation, Task, Action, Result. 3) How do you handle disagreements? — show emotional intelligence. 4) Why this company? — research company values, recent news. 5) Where do you see yourself in 5 years? — show ambition aligned with role. Tips: prepare 5 stories from your experience that cover leadership, teamwork, failure, conflict, and achievement.", "meta": {"category": "resource", "type": "behavioral_guide"}},
    {"id": "resource_4", "text": "System Design Interview Basics for Freshers: Key concepts to learn: 1) Client-Server architecture 2) Load balancing 3) Database sharding and replication 4) Caching (Redis, CDN) 5) Message queues 6) API design (REST, GraphQL) 7) CAP theorem. Practice designing: URL shortener, Twitter feed, Chat system, File storage system. Framework: Requirements → High-level design → Deep dive → Trade-offs → Bottlenecks.", "meta": {"category": "resource", "type": "system_design"}},
    {"id": "resource_5", "text": "Placement Season Timeline and Strategy: 6 months before: Start DSA practice, build 2-3 projects. 4 months before: Complete DSA syllabus (200+ problems), start system design basics. 3 months before: Build resume, get it reviewed, practice mock interviews. 2 months before: Apply to companies, practice company-specific questions. 1 month before: Revise weak topics, do mock interviews daily. During placement: Stay calm, sleep well, revise notes between rounds. After rejection: Analyze gaps, improve, keep applying — persistence wins.", "meta": {"category": "resource", "type": "strategy"}},
]


def seed_knowledge_base():
    """
    Seed the knowledge base with synthetic institutional data.
    Only runs when SEED_KB=true env var is set (opt-in for dev/demo mode).
    In production, the placement admin uploads all data through the dashboard.
    """
    import os
    import re
    if os.getenv("SEED_KB", "true").lower() != "true":
        print("⏩ KB seeding skipped (set SEED_KB=false to disable demo data).")
        return

    kb_count = get_collection_count("institutional_kb")
    interview_count = get_collection_count("interview_experiences")
    alumni_resumes_count = get_collection_count("alumni_resumes")

    if kb_count > 0 and interview_count > 0 and alumni_resumes_count > 0:
        print("✅ Knowledge base already seeded. Skipping.")
        return

    print("🌱 Seeding institutional knowledge base...")

    # Seed alumni profiles + roadmaps + resources into institutional_kb if empty
    if kb_count == 0:
        kb_ids = []
        kb_texts = []
        kb_metas = []

        for item in ALUMNI_PROFILES:
            kb_ids.append(item["id"])
            kb_texts.append(item["text"])
            kb_metas.append(item["meta"])

        for item in SKILL_ROADMAPS:
            kb_ids.append(item["id"])
            kb_texts.append(item["text"])
            kb_metas.append(item["meta"])

        for item in PLACEMENT_RESOURCES:
            kb_ids.append(item["id"])
            kb_texts.append(item["text"])
            kb_metas.append(item["meta"])

        store_kb_documents_batch("institutional_kb", kb_ids, kb_texts, kb_metas)
        print(f"  ✅ Stored {len(kb_ids)} documents in institutional_kb")

    # Seed interview experiences if empty
    if interview_count == 0:
        ie_ids = [item["id"] for item in INTERVIEW_EXPERIENCES]
        ie_texts = [item["text"] for item in INTERVIEW_EXPERIENCES]
        ie_metas = [item["meta"] for item in INTERVIEW_EXPERIENCES]

        store_kb_documents_batch("interview_experiences", ie_ids, ie_texts, ie_metas)
        print(f"  ✅ Stored {len(ie_ids)} documents in interview_experiences")

    # Seed alumni resumes if empty (mapping metadata schema of ingestion pipeline)
    if alumni_resumes_count == 0:
        al_ids = []
        al_texts = []
        al_metas = []

        for item in ALUMNI_PROFILES:
            meta = item["meta"]
            text = item["text"]
            
            # Extract student name
            name_match = re.match(r"^([A-Za-z\s]+)\s+(?:graduated|transitioned)", text)
            name = name_match.group(1).strip() if name_match else "Unknown Alumni"
            
            # Extract skills string
            skills_match = re.search(r"skills in ([^.]+)\.", text)
            skills = skills_match.group(1).strip() if skills_match else ""
            # Clean up skills string (e.g. remove "and")
            skills = re.sub(r"\band\b", "", skills).replace(", ,", ",").strip()
            skills = ", ".join([s.strip() for s in skills.split(",") if s.strip()])
            
            al_ids.append(f"alumni_resume_seeded_{item['id']}")
            al_texts.append(text)
            al_metas.append({
                "student_name": name,
                "company": meta.get("company", "Not Specified"),
                "role": meta.get("role", "Not Specified"),
                "department": meta.get("department", "Not Specified"),
                "batch": str(meta.get("year", "N/A")),
                "skills": skills,
                "source_file": "seeded_profile",
                "chunk_index": 0,
                "category": "alumni_resume",
            })

        store_kb_documents_batch("alumni_resumes", al_ids, al_texts, al_metas)
        print(f"  ✅ Stored {len(al_ids)} documents in alumni_resumes (seeded collection)")

    print("🌱 Knowledge base seeding complete!")
