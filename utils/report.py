"""Plain-text (Markdown) report built from an analysis result."""

from datetime import datetime
from typing import Any, Dict

from utils.ui import money, salary_text


def build_markdown_report(res: Dict[str, Any]) -> str:
    profile = res["extracted_data"]["profile"]
    a = res["analysis_results"]
    m = res["job_matches"]
    s = res["screening_results"]
    rec = res["final_recommendation"]
    ranked = m["matched_jobs"]

    L = []
    L.append(f"# Candidate Report - {profile.get('name') or 'Unknown candidate'}")
    L.append(f"_Generated {datetime.now():%Y-%m-%d %H:%M} by AI Recruiter Agency_\n")
    L.append("## Scorecard")
    L.append(f"- **Resume strength:** {a['resume_strength']}/100")
    L.append(f"- **Screening score:** {s['screening_score']}/100 - {s['verdict']} ({s['action']})")
    L.append(f"- **Best job match:** {m['best_score']}% | **Top-5 average:** {m['top5_average']}%")
    est = m.get("salary_estimate")
    if est:
        L.append(f"- **Indicative salary band (matched listings):** {money(est['min'])} - {money(est['max'])}")
    L.append("")
    L.append("## Profile")
    L.append(f"- Seniority: {a['experience_level']} | Experience: {a['years_of_experience']:g} years | Education: {a['education']['level']}")
    L.append(f"- Skills ({len(a['skills'])}): {', '.join(a['skills'])}")
    L.append(f"- Quantified achievements: {a['impact']['quantified']} | ATS score: {a['ats_score']}/100\n")
    L.append("## Top job matches")
    L.append("| Rank | Role | Company | Match | Salary | Missing skills |")
    L.append("|---|---|---|---|---|---|")
    for i, r in enumerate(ranked[:8], 1):
        j = r["job"]
        L.append(f"| {i} | {j['title']} | {j['company']} | {r['score']}% | {salary_text(r['salary'])} | {', '.join(r['missing']) or '-'} |")
    L.append("\n## Screening breakdown")
    L.append("| Factor | Weight | Score | Points |")
    L.append("|---|---|---|---|")
    for b in s["breakdown"]:
        L.append(f"| {b['label']} | {b['weight']} | {b['score']}/100 | {b['points']} |")
    L.append(f"\n**Total: {s['screening_score']}/100**\n")
    for f in s["flags"]:
        icon = {"green": "[+]", "amber": "[!]", "red": "[x]"}[f["type"]]
        L.append(f"- {icon} {f['text']}")
    note = s["narrative"]
    L.append(f"\n### Recruiter note\n{note['summary']}")
    if note["interview_questions"]:
        L.append("\n**Suggested interview questions**")
        L += [f"{i}. {q}" for i, q in enumerate(note["interview_questions"], 1)]
    L.append("\n## Recommendation")
    n = rec["narrative"]
    L.append(f"**{n['headline']}**\n")
    L += [f"{i}. {step}" for i, step in enumerate(n["next_steps"], 1)]
    if rec["roadmap"]:
        L.append("\n**Learning roadmap**")
        L += [f"- Add {r['skill']}: top-5 average {r['avg_before']:g}% -> {r['avg_after']:g}%" for r in rec["roadmap"]]
    L.append("\n---\n_Scores are decision-support estimates calculated from the resume text and sample job listings; they are not a hiring decision._")
    return "\n".join(L)
