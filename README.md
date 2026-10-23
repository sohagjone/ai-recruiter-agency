# AI Recruiter Agency

Upload a PDF resume and get four reports, all built from calculated numbers:

| Tab | What it shows |
|---|---|
| 📊 Analysis | Resume strength score + radar chart, skills by category, ATS health check (10 checks), career timeline, employment gaps |
| 💼 Job Matches | Weighted match % for every job (skills 60 / experience 20 / level 10 / title 10), skill gaps, salary band, filters, job-posting fit checker |
| 🎯 Screening | Transparent 100-point screening score, red/green flags, shortlist-threshold check, interview questions |
| 💡 Recommendation | Skill priorities ranked by impact, learning roadmap, what-if simulator, market coverage, resume fixes, report download |

Scores are calculated with fixed rules in `utils/scoring.py` (same resume, same result).
The AI (Gemini / Groq) reads the resume and writes the commentary; if it is unavailable the app still works.

## Run locally
```
pip install -r requirements.txt
# .env  ->  GEMINI_API_KEY=...   and/or   GROQ_API_KEY=...
streamlit run app.py
```
On Streamlit Cloud add the same keys under *Manage app -> Settings -> Secrets*.

## Project layout
- `app.py` - interface (4 tabs)
- `utils/scoring.py` - all calculations · `utils/skills.py` - skill taxonomy · `utils/ui.py` - design system
- `agents/` - extractor, analyzer, matcher, screener, recommender, orchestrator
- `db/job_catalog.py` - the 33 sample jobs (add more here; they sync into SQLite on start)
