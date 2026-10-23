"""All the maths of the app lives here.

Nothing in this file calls an AI model. Every number shown in the interface
(experience years, resume strength, match %, screening score, skill-gap roadmap...)
is computed from the resume text with transparent rules, so results are
repeatable and explainable. The AI agents only add the written commentary.
"""

import re
from collections import Counter
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from utils.skills import (
    ALIAS_TO_CANONICAL,
    CATEGORY_OF,
    categorize,
    detect_skills,
)

TODAY = date.today()

# ---------------------------------------------------------------------------
# Levels
# ---------------------------------------------------------------------------
LEVEL_NAMES = ["Junior", "Mid-level", "Senior", "Lead"]
LEVEL_INDEX = {
    "entry-level": 0, "entry": 0, "intern": 0, "junior": 0,
    "mid-level": 1, "mid": 1, "intermediate": 1,
    "senior": 2, "lead": 3, "principal": 3, "staff": 3,
}
DEFAULT_MIN_YEARS = {0: 0, 1: 3, 2: 5, 3: 8}


def level_index(name: str) -> int:
    return LEVEL_INDEX.get(str(name or "").strip().lower(), 1)


def infer_seniority(years: float, titles_text: str = "") -> str:
    if years < 2:
        idx = 0
    elif years < 5:
        idx = 1
    elif years < 10:
        idx = 2
    else:
        idx = 3
    t = (titles_text or "").lower()
    if idx < 2 and years >= 4 and re.search(r"\b(senior|sr\.?|lead|principal|head|director|manager)\b", t):
        idx = 2
    if idx >= 2 and years < 3 and re.search(r"\b(intern|trainee|junior|graduate|assistant)\b", t):
        idx = 1
    if idx == 3 and not re.search(r"\b(lead|principal|head|director|manager|architect|vp|chief)\b", t):
        idx = 2  # 10+ years but no leadership title: still Senior
    return LEVEL_NAMES[idx]


# ---------------------------------------------------------------------------
# Dates & experience
# ---------------------------------------------------------------------------
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_MON = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_DATE = rf"(?:{_MON}\.?,?\s+(?:19|20)\d{{2}}|(?:0?[1-9]|1[0-2])/(?:19|20)\d{{2}}|(?:19|20)\d{{2}}-(?:0?[1-9]|1[0-2])(?!\d)|(?:19|20)\d{{2}})"
_PRESENT = r"(?:present|current|currently|now|ongoing|today|till\s+date|to\s+date|date)"
RANGE_RE = re.compile(rf"({_DATE})\s*(?:–|—|-|to|until|till)\s*({_DATE}|{_PRESENT})", re.IGNORECASE)
EDU_WORDS = re.compile(
    r"\b(university|college|school|institute|bachelor|master|b\.?sc|m\.?sc|b\.?a\b|m\.?a\b|bba|mba|degree|diploma|hsc|ssc|gpa|cgpa|graduat|academy|a-levels?|gcse)\b",
    re.IGNORECASE)


def parse_date(text: Any, is_end: bool = False) -> Optional[date]:
    """Turn 'Mar 2021', '2021-03', '03/2021', '2021' or 'Present' into a date."""
    if text is None:
        return None
    t = str(text).strip().lower()
    if not t:
        return None
    if re.fullmatch(_PRESENT, t) or t in ("present", "current", "now"):
        return TODAY
    m = re.fullmatch(rf"({_MON})\.?,?\s+((?:19|20)\d{{2}})", t)
    if m:
        return date(int(m.group(2)), _MONTHS[m.group(1)[:3]], 1)
    m = re.fullmatch(r"(0?[1-9]|1[0-2])/((?:19|20)\d{2})", t)
    if m:
        return date(int(m.group(2)), int(m.group(1)), 1)
    m = re.fullmatch(r"((?:19|20)\d{2})-(0?[1-9]|1[0-2])", t)
    if m:
        return date(int(m.group(1)), int(m.group(2)), 1)
    m = re.fullmatch(r"((?:19|20)\d{2})", t)
    if m:  # year only: assume mid-year so "2018-2021" is about 3 years
        return date(int(m.group(1)), 6 if is_end else 7, 1)
    return None


def _months_between(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)


def ranges_from_entries(entries: List[Dict[str, Any]]) -> List[Tuple[date, date]]:
    out = []
    for e in entries or []:
        if not isinstance(e, dict):
            continue
        s = parse_date(e.get("start"), False)
        en = parse_date(e.get("end"), True)
        if s and en and en >= s:
            out.append((s, min(en, TODAY)))
    return out


def ranges_from_text(text: str) -> List[Tuple[date, date]]:
    out = []
    for line in (text or "").splitlines():
        if EDU_WORDS.search(line):
            continue  # study dates are not work experience
        for m in RANGE_RE.finditer(line):
            s = parse_date(m.group(1), False)
            en = parse_date(m.group(2), True)
            if s and en and en >= s and s <= TODAY:
                out.append((s, min(en, TODAY)))
    return out


def experience_metrics(ranges: List[Tuple[date, date]]) -> Dict[str, Any]:
    """Years of experience (overlaps counted once), tenure, gaps and job hopping."""
    ranges = [(s, e) for s, e in ranges if 0 <= _months_between(s, e) <= 12 * 50]
    if not ranges:
        return {"years": 0.0, "roles": 0, "avg_tenure": 0.0, "longest_tenure": 0.0,
                "gaps": [], "job_hopping": False}
    ordered = sorted(ranges)
    merged = [list(ordered[0])]
    for s, e in ordered[1:]:
        if s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    total_months = sum(_months_between(s, e) for s, e in merged)
    gaps = []
    for (_, e1), (s2, _) in zip(merged, merged[1:]):
        gap = _months_between(e1, s2)
        if gap > 6:
            gaps.append({"from": e1.strftime("%b %Y"), "to": s2.strftime("%b %Y"), "months": gap})
    tenures = [_months_between(s, e) / 12 for s, e in ordered]
    return {
        "years": round(total_months / 12, 1),
        "roles": len(ordered),
        "avg_tenure": round(sum(tenures) / len(tenures), 1),
        "longest_tenure": round(max(tenures), 1),
        "gaps": gaps,
        "job_hopping": len(ordered) >= 3 and (sum(tenures) / len(tenures)) < 1.0,
    }


def stated_years(text: str) -> float:
    """'8+ years of experience' style claims, used only when no dates can be read."""
    vals = [int(m) for m in re.findall(r"(\d{1,2})\s*\+?\s*(?:years?|yrs?)(?:\s+of)?\s+(?:professional\s+|relevant\s+|work\s+|industry\s+)?experience", text or "", re.I)]
    return float(max(vals)) if vals else 0.0


# ---------------------------------------------------------------------------
# Sections, contact details, education
# ---------------------------------------------------------------------------
SECTION_KEYS = {
    "summary": {"summary", "professional summary", "profile", "objective", "career objective", "about me", "about", "personal statement", "professional profile"},
    "experience": {"experience", "work experience", "professional experience", "employment history", "work history", "employment", "career history", "relevant experience", "professional background"},
    "education": {"education", "academic background", "academic qualifications", "education & training", "education and training", "qualifications", "academic"},
    "skills": {"skills", "technical skills", "core competencies", "key skills", "skills & tools", "competencies", "tools & technologies", "technologies", "skills and tools", "areas of expertise", "expertise"},
    "projects": {"projects", "personal projects", "key projects", "selected projects"},
    "certifications": {"certifications", "certificates", "licenses", "certifications & licenses", "courses", "training"},
    "achievements": {"achievements", "awards", "honors", "accomplishments", "awards & achievements", "awards and achievements"},
    "languages": {"languages"},
}


def split_sections(text: str) -> Dict[str, str]:
    sections: Dict[str, List[str]] = {}
    current = "header"
    for line in (text or "").splitlines():
        norm = re.sub(r"[^a-z& ]", "", line.lower()).strip()
        norm = re.sub(r"\s+", " ", norm)
        hit = next((k for k, names in SECTION_KEYS.items() if norm in names), None) if 0 < len(line.split()) <= 5 else None
        if hit:
            current = hit
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?<!\d)(\+?\d[\d\s().-]{7,}\d)(?!\d)")
URL_RE = re.compile(r"(?:https?://|www\.)[^\s,;)\]]+|(?:linkedin|github|behance|dribbble|medium)\.com/[^\s,;)\]]+", re.I)


def find_contacts(text: str) -> Dict[str, str]:
    text = text or ""
    m_email = EMAIL_RE.search(text)
    email = m_email.group(0) if m_email else ""
    phone = ""
    for m in PHONE_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group(1))
        if 9 <= len(digits) <= 15 and not RANGE_RE.search(m.group(1)):
            phone = m.group(1).strip()
            break
    urls = URL_RE.findall(text)
    linkedin = next((u for u in urls if "linkedin" in u.lower()), "")
    github = next((u for u in urls if "github" in u.lower()), "")
    other = next((u for u in urls if u not in (linkedin, github)), "")
    return {"email": email, "phone": phone, "linkedin": linkedin, "github": github, "website": other}


EDU_LEVELS = [  # (label, score 0-1, regex) checked from highest to lowest
    ("PhD", 1.0, r"\b(ph\.?d|doctorate|doctoral|d\.?phil)"),
    ("Master's", 0.9, r"\b(master'?s?\b|m\.sc\.?|msc|m\.s\.|m\.a\.|mba\b|m\.?tech|m\.?eng\b|m\.?phil|post-?graduate)"),
    ("Bachelor's", 0.75, r"\b(bachelor'?s?\b|b\.sc\.?|bsc|b\.s\.|b\.a\.|bba\b|b\.?tech|b\.e\.|b\.?eng\b|undergraduate|llb|b\.com|bcom)"),
    ("Diploma / Associate", 0.55, r"\b(associate'?s? degree|diploma|hnd\b|polytechnic)"),
    ("High School", 0.4, r"\b(high school|hsc\b|ssc\b|a-levels?|gcse|secondary school)"),
]


def education_level(entries: List[Dict[str, Any]], text: str) -> Tuple[str, float]:
    blob = " ".join(
        " ".join(str(v) for v in e.values()) for e in (entries or []) if isinstance(e, dict)
    )
    for source in (blob, text or ""):
        for label, score, rx in EDU_LEVELS:
            if re.search(rx, source, re.I):
                return label, score
    return "Not detected", 0.3


# ---------------------------------------------------------------------------
# Resume writing quality
# ---------------------------------------------------------------------------
ACTION_VERBS = set("""achieved administered analyzed analysed architected automated built championed collaborated completed
configured conducted consolidated coordinated created cut decreased delivered deployed designed developed directed drove earned
enabled engineered established evaluated executed expanded facilitated generated grew guided identified implemented improved
increased initiated integrated introduced launched led maintained managed mentored migrated modernized negotiated optimized
orchestrated organized oversaw owned partnered performed pioneered planned presented produced reduced refactored researched
resolved restructured revamped saved scaled scraped secured shipped simplified solved spearheaded standardized streamlined
strengthened supervised supported tested trained transformed upgraded utilized validated visualized wrote compiled curated sourced
collected cleaned compared prepared reviewed monitored identified contacted generated""".split())

_BULLET = re.compile(r"^[\s•\-\*▪●◦–·‣>\d.)]+")
_NUM_PATTERN = re.compile(r"(\d[\d,]*(?:\.\d+)?\s?(?:%|k\b|m\b|x\b|\+)|[$€£]\s?\d|\b\d{2,}\b)", re.I)


def _content_lines(text: str) -> List[str]:
    return [l.strip() for l in (text or "").splitlines() if len(l.split()) >= 4]


def impact_metrics(text: str) -> Dict[str, Any]:
    quantified, action_starts = 0, 0
    lines = _content_lines(text)
    for line in lines:
        body = RANGE_RE.sub(" ", line)
        body = re.sub(r"\b(?:19|20)\d{2}\b", " ", body)  # years are not metrics
        body = re.sub(EMAIL_RE.pattern, " ", body)
        body = re.sub(PHONE_RE.pattern, " ", body)
        if _NUM_PATTERN.search(body):
            quantified += 1
        first = _BULLET.sub("", line).split(" ")[0].lower().strip(".,:;")
        if first in ACTION_VERBS:
            action_starts += 1
    return {"quantified": quantified, "action_verbs": action_starts, "lines": len(lines)}


def readability_score(text: str) -> Tuple[int, float]:
    lines = _content_lines(text)
    if not lines:
        return 0, 0.0
    avg = sum(len(l.split()) for l in lines) / len(lines)
    if 8 <= avg <= 22:
        score = 100
    elif avg < 8:
        score = avg / 8 * 100
    else:
        score = max(0, 100 - (avg - 22) * 5)
    return int(round(score)), round(avg, 1)


def ats_checks(text: str, contacts: Dict[str, str], sections: Dict[str, str], impact: Dict[str, Any], words: int) -> List[Dict[str, Any]]:
    def has(sec: str) -> bool:
        return len((sections.get(sec) or "").split()) >= 3

    return [
        {"label": "Email address", "passed": bool(contacts.get("email")), "weight": 10, "tip": "Add a professional email address in the header."},
        {"label": "Phone number", "passed": bool(contacts.get("phone")), "weight": 8, "tip": "Add a phone number so recruiters can reach you quickly."},
        {"label": "LinkedIn / portfolio link", "passed": bool(contacts.get("linkedin") or contacts.get("github") or contacts.get("website")), "weight": 6, "tip": "Link your LinkedIn, GitHub or portfolio."},
        {"label": "Professional summary", "passed": has("summary"), "weight": 8, "tip": "Open with a 2-3 line summary of who you are and what you offer."},
        {"label": "Work experience section", "passed": has("experience"), "weight": 14, "tip": "Use a clear 'Experience' heading so ATS software can find your jobs."},
        {"label": "Education section", "passed": has("education"), "weight": 10, "tip": "Add an 'Education' section with your degree and institution."},
        {"label": "Skills section", "passed": has("skills"), "weight": 10, "tip": "Add a dedicated 'Skills' section listing your tools and technologies."},
        {"label": "Ideal length (250-1,000 words)", "passed": 250 <= words <= 1000, "weight": 10, "tip": "Aim for one to two pages (roughly 400-800 words)."},
        {"label": "3+ quantified achievements", "passed": impact["quantified"] >= 3, "weight": 14, "tip": "Add numbers: %, $, volumes or team sizes to show impact."},
        {"label": "Strong action verbs (6+ bullets)", "passed": impact["action_verbs"] >= 6, "weight": 10, "tip": "Start bullets with verbs such as Built, Led, Reduced, Delivered."},
    ]


# ---------------------------------------------------------------------------
# Profile analysis (Analysis tab)
# ---------------------------------------------------------------------------
def years_score(years: float) -> float:
    pts = [(0, 0), (1, 25), (2, 40), (3, 55), (5, 78), (8, 92), (12, 100)]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if years <= x2:
            return y1 + (y2 - y1) * (years - x1) / (x2 - x1)
    return 100.0


def analyse_profile(profile: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
    """Compute every Analysis-tab number from the extracted profile + raw resume text."""
    text = raw_text or ""
    sections = split_sections(text)
    words = len(text.split())

    # skills
    skills = profile.get("skills", [])
    groups = categorize(skills)
    skill_score = min(1, len(skills) / 14) * 70 + min(1, len(groups) / 4) * 30

    # experience
    ranges = ranges_from_entries(profile.get("experience", []))
    source = "extracted work history"
    if not ranges:
        exp_text = sections.get("experience") or "\n".join(v for k, v in sections.items() if k != "education")
        ranges = ranges_from_text(exp_text)
        source = "dates found in the resume text"
    exp = experience_metrics(ranges)
    if exp["years"] == 0:
        claimed = stated_years(text)
        if claimed:
            exp["years"], source = claimed, "years stated in the resume"
        else:
            source = "no dates found"
    titles_text = " ".join(
        str(e.get("title", "")) for e in profile.get("experience", []) if isinstance(e, dict)
    ) + " " + str(profile.get("headline", ""))
    seniority = infer_seniority(exp["years"], titles_text)

    # education
    edu_label, edu_val = education_level(profile.get("education", []), text)

    # impact + quality
    impact = impact_metrics(text)
    contacts = find_contacts(text)
    for k, v in contacts.items():
        if v and not profile.get(k):
            profile[k] = v
    checks = ats_checks(text, contacts, sections, impact, words)
    ats = sum(c["weight"] for c in checks if c["passed"])
    read, avg_len = readability_score(text)
    impact_score = min(1, impact["quantified"] / 5) * 60 + min(1, impact["action_verbs"] / 10) * 40

    dims = {
        "Skills": round(skill_score),
        "Experience": round(years_score(exp["years"])),
        "Education": round(edu_val * 100),
        "Impact": round(impact_score),
        "ATS Readiness": ats,
        "Readability": read,
    }
    weights = {"Skills": 0.25, "Experience": 0.20, "Education": 0.10, "Impact": 0.20, "ATS Readiness": 0.15, "Readability": 0.10}
    strength = round(sum(dims[k] * weights[k] for k in dims))

    # extraction confidence: how many key fields could be read
    found = [
        bool(profile.get("name")), bool(contacts.get("email")), bool(contacts.get("phone")),
        len(skills) >= 3, bool(ranges) or bool(profile.get("experience")),
        edu_label != "Not detected", words >= 120,
    ]
    confidence = round(sum(found) / len(found), 2)

    top_cat = sorted(groups.items(), key=lambda kv: -len(kv[1]))
    return {
        "skills": skills,
        "skill_groups": groups,
        "category_counts": [(c, len(v)) for c, v in top_cat],
        "domain_expertise": [c for c, v in top_cat if c not in ("Soft Skills", "Other") and len(v) >= 2][:4]
                            or [c for c, _ in top_cat[:2] if c != "Other"],
        "years_of_experience": exp["years"],
        "experience_source": source,
        "experience": exp,
        "experience_level": seniority,
        "education": {"level": edu_label, "score": round(edu_val * 100)},
        "impact": impact,
        "ats_checks": checks,
        "ats_score": ats,
        "readability": {"score": read, "avg_words_per_line": avg_len},
        "word_count": words,
        "dimensions": dims,
        "dimension_weights": weights,
        "resume_strength": strength,
        "confidence_score": confidence,
        "contacts": contacts,
    }


# ---------------------------------------------------------------------------
# Job matching (Job Matches tab)
# ---------------------------------------------------------------------------
_FILLER = {"skills", "skill", "experience", "knowledge", "of", "basic", "strong", "with", "in", "and", "the", "a", "an",
           "preferred", "methods", "methodologies", "principles", "proficiency", "understanding", "excellent", "good",
           "ability", "to", "working", "familiarity", "license", "licence", "certified", "certification"}
_GENERIC_TITLE = {"senior", "junior", "lead", "sr", "jr", "i", "ii", "iii", "and", "of", "the", "at", "associate", "python"}


def _stem(word: str) -> str:
    w = word.lower()
    for suf in ("ations", "ation", "ings", "ing", "ers", "er", "ed", "es", "al", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def parse_requirement(req: str) -> Dict[str, Any]:
    r = str(req).strip()
    low = r.lower()
    m = re.search(r"(\d+)\s*\+?\s*(?:years?|yrs?)", low)
    if m:
        return {"kind": "experience", "years": int(m.group(1)), "text": r}
    if low in ALIAS_TO_CANONICAL:
        canon = ALIAS_TO_CANONICAL[low]
        return {"kind": "skill", "key": canon.lower(), "display": canon, "known": True}
    core = re.sub(r"\(.*?\)", " ", low)
    core_words = [w for w in re.findall(r"[a-z0-9+#.\-/]+", core) if w not in _FILLER]
    core_phrase = " ".join(core_words)
    if core_phrase in ALIAS_TO_CANONICAL:
        canon = ALIAS_TO_CANONICAL[core_phrase]
        return {"kind": "skill", "key": canon.lower(), "display": canon, "known": True}
    no_paren = re.sub(r"\(.*?\)", "", low).strip()  # "Barista experience (preferred)" -> "barista experience"
    if no_paren in ALIAS_TO_CANONICAL:
        canon = ALIAS_TO_CANONICAL[no_paren]
        return {"kind": "skill", "key": canon.lower(), "display": canon, "known": True}
    display = re.sub(r"\s+", " ", re.sub(r"\(.*?\)", "", r)).strip().title() or r
    return {"kind": "skill", "key": core_phrase or low, "display": display, "known": False, "words": core_words}


def requirement_credit(req: Dict[str, Any], cand: Dict[str, Any]) -> float:
    key = req["key"]
    if key in cand["skills_l"]:
        return 1.0
    if req.get("known"):
        return 0.0  # taxonomy skills are detected when the resume is analysed
    words = req.get("words") or []
    if not words:
        return 0.0
    text = cand["text_l"]
    stems = [_stem(w) for w in words]
    phrase = r"\W+".join(r"\b" + re.escape(s) + r"\w*" for s in stems)
    if re.search(phrase, text):
        return 1.0
    present = sum(1 for s in stems if re.search(r"\b" + re.escape(s), text))
    if len(stems) >= 2 and present / len(stems) >= 0.67:
        return 0.5
    return 0.0


def make_candidate(profile: Dict[str, Any], analysis: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
    titles = " ".join(str(e.get("title", "")) for e in profile.get("experience", []) if isinstance(e, dict))
    titles += " " + str(profile.get("headline", ""))
    return {
        "skills": list(analysis["skills"]),
        "skills_l": {s.lower() for s in analysis["skills"]},
        "text_l": (raw_text or "").lower(),
        "titles_l": titles.lower(),
        "years": float(analysis["years_of_experience"]),
        "level_idx": level_index(analysis["experience_level"]),
    }


def fit_label(score: int) -> str:
    if score >= 75:
        return "Excellent fit"
    if score >= 60:
        return "Strong fit"
    if score >= 45:
        return "Good potential"
    if score >= 30:
        return "Stretch role"
    return "Low fit"


def score_job(job: Dict[str, Any], cand: Dict[str, Any]) -> Dict[str, Any]:
    reqs = [parse_requirement(r) for r in job.get("requirements", [])]
    skill_reqs = [r for r in reqs if r["kind"] == "skill"]
    exp_reqs = [r for r in reqs if r["kind"] == "experience"]

    matched, partial, missing = [], [], []
    credit_sum = 0.0
    for r in skill_reqs:
        c = requirement_credit(r, cand)
        credit_sum += c
        (matched if c >= 1 else partial if c > 0 else missing).append(r)
    skills_ratio = credit_sum / len(skill_reqs) if skill_reqs else 0.5

    job_level = level_index(job.get("experience_level"))
    min_years = exp_reqs[0]["years"] if exp_reqs else DEFAULT_MIN_YEARS.get(job_level, 0)
    exp_ratio = 1.0 if min_years <= 0 else min(1.0, cand["years"] / min_years)

    dist = abs(cand["level_idx"] - job_level)
    level_ratio = {0: 1.0, 1: 0.6, 2: 0.25}.get(dist, 0.1)

    title_words = [w for w in re.findall(r"[a-z]+", job.get("title", "").lower()) if w not in _GENERIC_TITLE]
    pool = cand["titles_l"] + " " + cand["text_l"][:1500]
    title_ratio = (sum(1 for w in title_words if re.search(r"\b" + re.escape(_stem(w)), pool)) / len(title_words)) if title_words else 0.5

    gate = min(1.0, skills_ratio * 2)  # experience/level only count once some skills match
    score = 100 * (0.60 * skills_ratio + gate * (0.20 * exp_ratio + 0.10 * level_ratio + 0.10 * title_ratio))
    score = int(round(max(0, min(100, score))))

    flags = []
    if cand["level_idx"] - job_level >= 2:
        flags.append("May be overqualified")
    if min_years and cand["years"] < min_years:
        flags.append(f"Needs {min_years}+ yrs (you have {cand['years']:g})")

    return {
        "job": job,
        "score": score,
        "label": fit_label(score),
        "components": {
            "Skills": round(skills_ratio * 100),
            "Experience": round(exp_ratio * 100),
            "Level": round(level_ratio * 100),
            "Title": round(title_ratio * 100),
        },
        "matched": [r["display"] for r in matched],
        "partial": [r["display"] for r in partial],
        "missing": [r["display"] for r in missing],
        "missing_keys": [r["key"] for r in missing + partial],
        "min_years": min_years,
        "flags": flags,
        "salary": parse_salary(job.get("salary_range", "")),
    }


def rank_jobs(jobs: List[Dict[str, Any]], cand: Dict[str, Any]) -> List[Dict[str, Any]]:
    scored = [score_job(j, cand) for j in jobs]
    return sorted(scored, key=lambda s: (-s["score"], s["job"]["title"]))


def parse_salary(text: str) -> Optional[Dict[str, float]]:
    if not text:
        return None
    t = str(text).lower()
    nums = [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*\.?\d*", t) if n.replace(",", "").replace(".", "").isdigit()]
    if not nums:
        return None
    lo, hi = nums[0], nums[1] if len(nums) > 1 else nums[0]
    if re.search(r"hour|/hr|per hr", t) or hi < 500:
        lo, hi = lo * 2080, hi * 2080
    elif "k" in t and hi < 1000:
        lo, hi = lo * 1000, hi * 1000
    return {"min": lo, "max": hi, "mid": (lo + hi) / 2}


def salary_estimate(ranked: List[Dict[str, Any]], k: int = 5, min_score: int = 35) -> Optional[Dict[str, float]]:
    pool = [r for r in ranked[:k] if r["score"] >= min_score and r["salary"]]
    if not pool:
        return None
    w = sum(r["score"] for r in pool)
    return {
        "min": sum(r["salary"]["min"] * r["score"] for r in pool) / w,
        "max": sum(r["salary"]["max"] * r["score"] for r in pool) / w,
        "mid": sum(r["salary"]["mid"] * r["score"] for r in pool) / w,
        "based_on": len(pool),
    }


def top_avg(ranked: List[Dict[str, Any]], k: int = 5) -> float:
    top = [r["score"] for r in ranked[:k]]
    return round(sum(top) / len(top), 1) if top else 0.0


# ---------------------------------------------------------------------------
# Skill gaps & what-if (Recommendation tab)
# ---------------------------------------------------------------------------
def with_skills(cand: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    clone = dict(cand)
    clone["skills_l"] = set(cand["skills_l"]) | set(keys)
    return clone


def skill_demand(jobs: List[Dict[str, Any]]) -> Counter:
    counter: Counter = Counter()
    for j in jobs:
        for r in (parse_requirement(x) for x in j.get("requirements", [])):
            if r["kind"] == "skill":
                counter[(r["key"], r["display"])] += 1
    return counter


def market_coverage(jobs: List[Dict[str, Any]], cand: Dict[str, Any]) -> Dict[str, Any]:
    demand = skill_demand(jobs)
    total = sum(demand.values()) or 1
    have = sum(n for (key, _), n in demand.items() if key in cand["skills_l"])
    top = [{"skill": d, "count": n, "have": k in cand["skills_l"]} for (k, d), n in demand.most_common(12)]
    return {"coverage": round(have / total * 100), "top_demand": top}


def skill_priorities(jobs: List[Dict[str, Any]], ranked: List[Dict[str, Any]], cand: Dict[str, Any], pool_size: int = 10) -> List[Dict[str, Any]]:
    """Rank the missing skills by how much each one lifts the candidate's best matches."""
    base_avg = top_avg(ranked)
    base_best = ranked[0]["score"] if ranked else 0
    candidates: Dict[str, str] = {}
    for r in ranked[:pool_size]:
        for key, disp in zip(r["missing_keys"], r["missing"] + r["partial"]):
            candidates.setdefault(key, disp)
    demand = skill_demand(jobs)
    out = []
    for key, disp in candidates.items():
        after = rank_jobs(jobs, with_skills(cand, [key]))
        sal = [parse_salary(j.get("salary_range", "")) for j in jobs
               if any(parse_requirement(x).get("key") == key for x in j.get("requirements", []))]
        sal = [s["mid"] for s in sal if s]
        before_by_job = {(x["job"]["title"], x["job"]["company"]): x["score"] for x in ranked}
        unlocked = sum(1 for a in after if before_by_job.get((a["job"]["title"], a["job"]["company"]), 0) < 60 <= a["score"])
        out.append({
            "skill": disp, "key": key,
            "impact": round(top_avg(after) - base_avg, 1),
            "best_gain": after[0]["score"] - base_best,
            "demand": demand.get((key, disp), sum(n for (k, _), n in demand.items() if k == key)),
            "avg_salary": round(sum(sal) / len(sal)) if sal else None,
            "unlocked": unlocked,
        })
    return sorted(out, key=lambda d: (-d["impact"], -d["demand"], d["skill"]))


def learning_roadmap(jobs: List[Dict[str, Any]], cand: Dict[str, Any], priorities: List[Dict[str, Any]], steps: int = 4) -> List[Dict[str, Any]]:
    """Greedy plan: add the skill with the biggest gain, re-rank, repeat."""
    current = dict(cand)
    ranked = rank_jobs(jobs, current)
    base = top_avg(ranked)
    plan, available = [], {p["key"]: p["skill"] for p in priorities}
    for _ in range(steps):
        best = None
        for key, disp in available.items():
            avg = top_avg(rank_jobs(jobs, with_skills(current, [key])))
            if best is None or avg > best[2]:
                best = (key, disp, avg)
        if not best or best[2] <= base:
            break
        key, disp, avg = best
        current = with_skills(current, [key])
        plan.append({"skill": disp, "key": key, "avg_before": base, "avg_after": avg})
        base = avg
        available.pop(key)
    return plan


# ---------------------------------------------------------------------------
# Target job description fit (optional)
# ---------------------------------------------------------------------------
_STOP = set("""the and for with that this from will have has are you our your their they them who what when where which while about into over
under more most such than then also able across within including include includes using use used work works working team teams role roles
job position candidate candidates company looking seeking join must should would could can may well good great strong excellent
required requirements preferred plus years year experience skills skill knowledge ability responsibilities responsible duties
opportunity ensure support help make like need needs new one two three being been other related relevant etc per both each
""".split())


def jd_fit(jd_text: str, cand: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    jd = (jd_text or "").strip()
    if len(jd.split()) < 15:
        return None
    jd_skills = detect_skills(jd)
    matched = [s for s in jd_skills if s.lower() in cand["skills_l"]]
    missing = [s for s in jd_skills if s.lower() not in cand["skills_l"]]
    tokens = re.findall(r"[a-z][a-z+#.\-]{3,}", jd.lower())
    counts = Counter(t for t in tokens if t not in _STOP and t not in {s.lower() for s in jd_skills})
    keywords = [w for w, n in counts.most_common(40) if n >= 2][:15]
    kw_hit = [w for w in keywords if re.search(r"\b" + re.escape(_stem(w)), cand["text_l"])]
    kw_miss = [w for w in keywords if w not in kw_hit]
    skill_cov = len(matched) / len(jd_skills) if jd_skills else None
    kw_cov = len(kw_hit) / len(keywords) if keywords else None
    parts = [(skill_cov, 0.7), (kw_cov, 0.3)]
    parts = [(v, w) for v, w in parts if v is not None]
    if not parts:
        return None
    score = round(100 * sum(v * w for v, w in parts) / sum(w for _, w in parts))
    years_req = [int(x) for x in re.findall(r"(\d{1,2})\s*\+?\s*(?:years?|yrs?)", jd.lower())]
    need = max(years_req) if years_req else None
    return {
        "score": score, "label": fit_label(score),
        "matched": matched, "missing": missing,
        "keywords_hit": kw_hit, "keywords_missing": kw_miss,
        "required_years": need,
        "years_ok": (cand["years"] >= need) if need else None,
    }


# ---------------------------------------------------------------------------
# Screening (Screening tab)
# ---------------------------------------------------------------------------
SCREEN_WEIGHTS = [
    ("Role alignment", 35),
    ("Experience depth", 20),
    ("Impact & achievements", 15),
    ("Education", 10),
    ("Skills breadth", 10),
    ("Resume quality (ATS)", 10),
]


def verdict_for(score: int) -> Tuple[str, str]:
    if score >= 80:
        return "Strong shortlist", "Move straight to interview"
    if score >= 65:
        return "Good candidate", "Recommend a screening call"
    if score >= 50:
        return "Potential fit", "Review manually before deciding"
    return "Weak fit for current openings", "Hold unless requirements change"


def screen_candidate(analysis: Dict[str, Any], ranked: List[Dict[str, Any]]) -> Dict[str, Any]:
    top3 = [r["score"] for r in ranked[:3]] or [0]
    role = 0.6 * top3[0] + 0.4 * (sum(top3) / len(top3))
    exp = analysis["experience"]
    skills = analysis["skills"]
    parts = {
        "Role alignment": (role, f"Best match {top3[0]}%, top-3 average {round(sum(top3) / len(top3))}%"),
        "Experience depth": (years_score(analysis["years_of_experience"]), f"{analysis['years_of_experience']:g} years across {exp['roles']} role(s)"),
        "Impact & achievements": (analysis["dimensions"]["Impact"], f"{analysis['impact']['quantified']} quantified bullets, {analysis['impact']['action_verbs']} action-verb bullets"),
        "Education": (analysis["education"]["score"], analysis["education"]["level"]),
        "Skills breadth": (analysis["dimensions"]["Skills"], f"{len(skills)} skills in {len(analysis['skill_groups'])} categories"),
        "Resume quality (ATS)": (analysis["ats_score"], f"{sum(c['passed'] for c in analysis['ats_checks'])}/{len(analysis['ats_checks'])} ATS checks passed"),
    }
    breakdown, total = [], 0.0
    for label, weight in SCREEN_WEIGHTS:
        val, detail = parts[label]
        pts = val * weight / 100
        total += pts
        breakdown.append({"label": label, "weight": weight, "score": round(val), "points": round(pts, 1), "detail": detail})
    score = int(round(total))
    verdict, action = verdict_for(score)

    flags: List[Dict[str, str]] = []
    best = ranked[0] if ranked else None
    if best and best["score"] >= 70:
        flags.append({"type": "green", "text": f"Strong skill overlap with {best['job']['title']} ({best['score']}% match)"})
    if analysis["years_of_experience"] >= 5:
        flags.append({"type": "green", "text": f"{analysis['years_of_experience']:g} years of experience"})
    if analysis["education"]["score"] >= 90:
        flags.append({"type": "green", "text": f"Advanced degree ({analysis['education']['level']})"})
    if analysis["impact"]["quantified"] >= 4:
        flags.append({"type": "green", "text": f"{analysis['impact']['quantified']} bullets with measurable results"})
    if len(skills) >= 15:
        flags.append({"type": "green", "text": f"Broad toolkit: {len(skills)} skills detected"})
    for g in exp["gaps"][:2]:
        flags.append({"type": "amber", "text": f"Employment gap of {g['months']} months ({g['from']} to {g['to']})"})
    if exp["job_hopping"]:
        flags.append({"type": "amber", "text": f"Short tenures: average {exp['avg_tenure']:g} years per role"})
    if analysis["impact"]["quantified"] < 2:
        flags.append({"type": "amber", "text": "Few or no measurable achievements"})
    if len(skills) < 5:
        flags.append({"type": "red", "text": f"Only {len(skills)} skills detected - profile looks thin"})
    if analysis["word_count"] < 150:
        flags.append({"type": "red", "text": f"Very short resume ({analysis['word_count']} words)"})
    elif analysis["word_count"] > 1200:
        flags.append({"type": "amber", "text": f"Long resume ({analysis['word_count']} words) - consider trimming"})
    if analysis["years_of_experience"] == 0:
        flags.append({"type": "amber", "text": "Work history dates could not be read"})
    if not (analysis["contacts"].get("email") or analysis["contacts"].get("phone")):
        flags.append({"type": "red", "text": "No contact details found"})
    return {
        "screening_score": score,
        "verdict": verdict,
        "action": action,
        "breakdown": breakdown,
        "flags": flags,
    }
