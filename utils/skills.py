"""Skill taxonomy: canonical names, aliases, categories and text detection.

Everything here is plain Python (no AI calls), so skill detection is fast,
free and gives the same answer every time.
"""

import re
from typing import Dict, Iterable, List, Set

# category -> canonical skill -> aliases (case-insensitive unless listed below)
TAXONOMY: Dict[str, Dict[str, List[str]]] = {
    "Programming": {
        "Python": ["python3", "python 3"],
        "JavaScript": ["js", "ecmascript", "es6"],
        "TypeScript": ["ts"],
        "Java": [],
        "C++": ["cpp"],
        "C#": ["csharp", "c sharp"],
        "Go": ["golang"],
        "Rust": [],
        "PHP": [],
        "Ruby": ["ruby on rails", "rails"],
        "Swift": [],
        "Kotlin": [],
        "R": ["r programming", "rstudio", "ggplot", "ggplot2"],
        "MATLAB": [],
        "Scala": [],
        "Bash": ["shell scripting", "shell script", "powershell"],
    },
    "Web & Mobile": {
        "React": ["reactjs", "react.js"],
        "Angular": ["angularjs"],
        "Vue": ["vuejs", "vue.js"],
        "Node.js": ["nodejs", "node js", "express.js", "expressjs"],
        "Next.js": ["nextjs"],
        "Django": [],
        "Flask": [],
        "FastAPI": [],
        "HTML": ["html5"],
        "CSS": ["css3", "sass", "scss"],
        "Tailwind": ["tailwind css", "tailwindcss"],
        "REST API": ["rest apis", "restful", "restful api", "restful apis", "rest", "api development", "apis"],
        "GraphQL": [],
        "React Native": [],
        "Flutter": [],
        "Android": ["android development"],
        "iOS": ["ios development"],
    },
    "Data & Analytics": {
        "SQL": ["t-sql", "pl/sql", "sql queries"],
        "Excel": ["microsoft excel", "ms excel", "advanced excel", "pivot table", "pivot tables", "vlookup", "xlookup", "spreadsheets", "google sheets"],
        "Power BI": ["powerbi", "power-bi"],
        "Tableau": [],
        "Data Analysis": ["data analytics", "analytics", "data analyst", "analyzing data", "analysing data", "data-driven"],
        "Data Visualization": ["data visualisation", "dashboards", "dashboard", "data viz", "visualization", "visualisation"],
        "Statistics": ["statistical analysis", "statistical", "hypothesis testing", "regression analysis"],
        "ETL": ["data pipelines", "data pipeline", "etl pipelines"],
        "Pandas": [],
        "NumPy": [],
        "Apache Spark": ["spark", "pyspark"],
        "Hadoop": [],
        "Google Analytics": ["ga4", "google analytics 4"],
        "Market Research": ["market analysis", "market study", "market studies", "market sizing", "industry research", "primary research", "secondary research"],
        "Competitive Analysis": ["competitor analysis", "competitive intelligence", "competitive research", "competitor research", "benchmarking"],
        "Web Scraping": ["scraping", "web crawler", "beautifulsoup", "scrapy", "selenium scraping"],
        "Data Cleaning": ["data cleansing", "data wrangling", "data preparation", "data cleansing"],
        "A/B Testing": ["ab testing", "a/b tests", "split testing"],
        "Financial Modeling": ["financial models", "financial model", "dcf", "valuation"],
        "Report writing": ["report writing", "reporting", "research reports", "written reports"],
    },
    "AI & Machine Learning": {
        "Machine Learning": ["ml", "predictive modeling", "predictive modelling", "supervised learning"],
        "Deep Learning": ["neural networks", "neural network", "cnn", "rnn", "lstm"],
        "NLP": ["natural language processing", "text mining", "nlp"],
        "Computer Vision": ["image classification", "object detection", "image processing"],
        "TensorFlow": ["keras"],
        "PyTorch": [],
        "scikit-learn": ["sklearn", "scikit learn"],
        "OpenCV": [],
        "LLMs": ["llm", "large language models", "generative ai", "gen ai", "prompt engineering", "openai", "langchain", "rag"],
    },
    "Cloud & DevOps": {
        "AWS": ["amazon web services", "ec2", "s3 bucket", "lambda functions"],
        "Azure": ["microsoft azure"],
        "GCP": ["google cloud", "google cloud platform"],
        "Docker": ["containerization", "containers"],
        "Kubernetes": ["k8s"],
        "CI/CD": ["cicd", "ci cd", "continuous integration", "continuous deployment", "github actions", "jenkins", "gitlab ci"],
        "Terraform": ["infrastructure as code", "iac"],
        "Linux": ["ubuntu", "unix"],
        "Git": ["github", "gitlab", "version control", "bitbucket"],
    },
    "Databases": {
        "PostgreSQL": ["postgres"],
        "MySQL": [],
        "MongoDB": ["nosql"],
        "Redis": [],
        "SQLite": [],
        "Oracle": ["oracle db", "oracle database"],
        "Firebase": [],
        "Snowflake": [],
    },
    "Design & Creative": {
        "Figma": [],
        "Sketch": [],
        "Adobe Creative Suite": ["adobe creative cloud", "adobe cc", "photoshop", "illustrator", "indesign", "premiere pro", "after effects", "adobe xd"],
        "UX Design": ["ux", "user experience", "ux/ui", "ui/ux", "ui design", "ux research"],
        "User research methods": ["user research", "usability testing", "user interviews", "user-centered design", "user centred design", "user-centered design principles"],
        "Wireframing": ["wireframes", "prototyping", "prototypes"],
        "Illustration skills": ["illustration"],
        "Video Editing": ["video production", "motion graphics"],
    },
    "Marketing & Sales": {
        "SEO": ["search engine optimization", "search engine optimisation", "on-page seo", "keyword research"],
        "Google Ads": ["adwords", "ppc", "sem", "paid search", "paid media", "paid advertising"],
        "Social Media": ["social media marketing", "social media management", "instagram", "facebook ads", "linkedin ads"],
        "Email Marketing": ["mailchimp", "email campaigns", "newsletter", "klaviyo"],
        "Content marketing": ["content strategy", "content creation", "blogging", "content writing"],
        "Copywriting": ["copy writing", "ad copy"],
        "CRM": ["salesforce", "hubspot", "zoho", "pipedrive", "customer relationship management"],
        "Lead Generation": ["lead gen", "prospecting", "outbound sales", "cold outreach", "cold emailing", "sales outreach", "contact database", "contact databases", "lead sourcing"],
        "Sales": ["business development", "account management", "b2b sales", "closing deals"],
        "Brand Strategy": ["branding", "brand management", "go-to-market", "gtm"],
    },
    "Business & Management": {
        "Project management": ["project manager", "project planning", "pmp", "prince2", "project coordination"],
        "Agile": ["scrum", "kanban", "sprint planning", "agile methodologies", "agile methodology"],
        "Product Management": ["product manager", "product roadmap", "product strategy", "product owner"],
        "Stakeholder Management": ["stakeholder engagement", "stakeholder communication", "client management", "client relations", "client communication"],
        "Business Analysis": ["business analyst", "requirements gathering", "business requirements", "process improvement", "process mapping"],
        "Financial Analysis": ["financial analyst", "financial reporting", "budgeting", "variance analysis"],
        "Accounting": ["bookkeeping", "quickbooks", "accounts payable", "accounts receivable", "gaap", "ifrs"],
        "Leadership": ["team lead", "team leadership", "led a team", "managed a team", "people management", "mentoring", "mentorship"],
        "Strategic Planning": ["strategy", "strategic analysis", "business strategy"],
        "Operations": ["operations management", "supply chain", "logistics", "procurement"],
        "Risk Management": ["risk assessment", "compliance"],
    },
    "Security": {
        "Cybersecurity": ["cyber security", "information security", "infosec", "cybersecurity certifications (cissp, ceh)"],
        "Network security": ["network defense", "firewalls", "firewall", "vpn"],
        "Penetration Testing": ["pentesting", "pen testing", "ethical hacking", "ceh", "vulnerability assessment"],
        "CISSP": [],
        "SIEM": ["splunk", "security monitoring"],
    },
    "Engineering & Trades": {
        "CAD software": ["cad", "autocad", "solidworks", "catia", "fusion 360", "creo"],
        "Mechanical design": ["mechanical engineering", "mechanical systems", "product design engineering"],
        "Manufacturing experience": ["manufacturing", "production line", "lean manufacturing", "six sigma", "quality control"],
        "Electrical systems": ["electrical installation", "electrical wiring", "wiring", "plc", "circuit design"],
        "Electrician license": ["licensed electrician", "journeyman electrician"],
        "Software Testing": ["qa", "quality assurance", "test automation", "unit testing", "manual testing", "automated testing", "pytest", "junit"],
        "Selenium": ["cypress", "playwright"],
    },
    "Customer & People": {
        "Customer Service": ["customer support", "customer care", "client support", "help desk", "helpdesk", "customer experience", "customer service skills"],
        "Technical Troubleshooting": ["troubleshooting", "basic technical troubleshooting", "technical support", "it support"],
        "HR": ["human resources", "hr experience", "recruiting", "recruitment", "talent acquisition", "onboarding", "hr coordinator"],
        "Interviewing skills": ["interviewing", "conducting interviews"],
        "Barista experience": ["barista", "coffee", "espresso"],
    },
    "Soft Skills": {
        "Communication skills": ["communication", "strong communication", "written communication", "verbal communication", "communicating", "excellent communication"],
        "Presentation skills": ["presentations", "presentation", "public speaking", "presenting", "presented to"],
        "Teamwork": ["collaboration", "cross-functional", "team player", "collaborative"],
        "Problem Solving": ["problem-solving", "analytical thinking", "troubleshoot", "critical thinking", "analytical skills"],
        "Time Management": ["prioritization", "multitasking", "deadline", "deadlines"],
        "Organizational skills": ["organization skills", "organisational skills", "organised", "organized", "attention to organization"],
        "Attention to detail": ["detail-oriented", "detail oriented", "meticulous", "accuracy"],
        "Creativity": ["creative", "creative thinking", "innovative"],
        "Negotiation": ["negotiating", "contract negotiation", "negotiated"],
        "Research skills": ["research", "desk research", "researching", "literature review"],
        "Adaptability": ["flexible", "fast learner", "quick learner", "adaptable"],
        "Positive attitude": ["positive", "enthusiastic", "motivated", "self-motivated"],
    },
}

# Short or ambiguous aliases that must match with exact capitalisation.
CASE_SENSITIVE = {"Swift", "Sketch", "Rust", "Ruby", "Oracle", "R", "Go", "ML", "CAD", "CRM", "HR", "QA", "IaC", "RAG", "CNN", "RNN", "LSTM", "GA4", "JS", "TS", "NLP", "SEM", "PPC", "DCF", "REST", "AWS", "SQL", "ETL"}
# Aliases that are too generic to trust on their own, matched only as exact words in their original form
WEAK_ALIASES = {"rest", "apis", "research", "strategy", "positive", "creative", "coffee", "analytics", "compliance", "reporting", "flexible", "organized", "organised", "deadline", "deadlines", "presentation", "presentations", "containers", "benchmarking", "wiring", "rails", "spark", "sketch"}

# Build lookup tables once at import time -----------------------------------
CATEGORY_OF: Dict[str, str] = {}
ALIAS_TO_CANONICAL: Dict[str, str] = {}
for _cat, _skills in TAXONOMY.items():
    for _canon, _aliases in _skills.items():
        CATEGORY_OF[_canon] = _cat
        ALIAS_TO_CANONICAL[_canon.lower()] = _canon
        for _a in _aliases:
            ALIAS_TO_CANONICAL.setdefault(_a.lower(), _canon)

ALL_SKILLS = list(CATEGORY_OF.keys())


def _pattern_for(term: str, case_sensitive: bool) -> re.Pattern:
    body = re.escape(term).replace(r"\ ", r"[\s\-]+")
    return re.compile(
        r"(?<![A-Za-z0-9+#])" + body + r"(?![A-Za-z0-9+#]|\.[A-Za-z])",
        0 if case_sensitive else re.IGNORECASE,
    )


# canonical -> list of compiled patterns (name first, then aliases)
_PATTERNS: Dict[str, List[re.Pattern]] = {}
for _cat, _skills in TAXONOMY.items():
    for _canon, _aliases in _skills.items():
        # "Go" and "R" are ordinary words/letters, so only their longer aliases are trusted
        pats = [] if _canon in ("Go", "R") else [_pattern_for(_canon, _canon in CASE_SENSITIVE or len(_canon) <= 1)]
        for _a in _aliases:
            if _a.lower() in WEAK_ALIASES:
                continue  # skip: too many false positives in free text
            pats.append(_pattern_for(_a, _a in CASE_SENSITIVE))
        _PATTERNS[_canon] = pats


def normalize_skill(raw: str) -> str:
    """Map any spelling of a skill to its canonical name (or a tidy version of itself)."""
    if not raw:
        return ""
    cleaned = re.sub(r"\s+", " ", str(raw)).strip(" -•·*,;:.\t\n")
    if not cleaned:
        return ""
    return ALIAS_TO_CANONICAL.get(cleaned.lower(), cleaned)


def detect_skills(text: str) -> List[str]:
    """Find every taxonomy skill mentioned in free text, in taxonomy order."""
    if not text:
        return []
    found = []
    for canon, pats in _PATTERNS.items():
        if any(p.search(text) for p in pats):
            found.append(canon)
    return found


def merge_skills(*groups: Iterable[str]) -> List[str]:
    """Normalise and de-duplicate skills from several sources, keeping first-seen order."""
    seen: Set[str] = set()
    merged: List[str] = []
    for group in groups:
        for raw in group or []:
            skill = normalize_skill(raw)
            key = skill.lower()
            if skill and key not in seen and len(skill) <= 40:
                seen.add(key)
                merged.append(skill)
    return merged


def categorize(skills: Iterable[str]) -> Dict[str, List[str]]:
    """Group skills by category; unknown skills go to 'Other'."""
    groups: Dict[str, List[str]] = {}
    for s in skills:
        groups.setdefault(CATEGORY_OF.get(s, "Other"), []).append(s)
    return groups
