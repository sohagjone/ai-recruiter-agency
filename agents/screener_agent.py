from datetime import datetime
from typing import Any, Dict, List

from utils.scoring import screen_candidate
from .base_agent import BaseAgent


def _facts(profile: Dict[str, Any], analysis: Dict[str, Any], screening: Dict[str, Any], ranked: List[Dict[str, Any]]) -> str:
    """A short fact sheet for the AI (keeps prompts small and numbers consistent)."""
    top = "; ".join(
        f"{r['job']['title']} at {r['job']['company']} {r['score']}% (missing: {', '.join(r['missing'][:3]) or 'nothing'})"
        for r in ranked[:3]
    )
    parts = ", ".join(f"{b['label']} {b['score']}/100" for b in screening["breakdown"])
    flags = "; ".join(f["text"] for f in screening["flags"]) or "none"
    return (
        f"Candidate: {profile.get('name') or 'Unknown'} ({profile.get('headline') or 'no headline'})\n"
        f"Seniority: {analysis['experience_level']}, {analysis['years_of_experience']:g} years, "
        f"education: {analysis['education']['level']}\n"
        f"Skills: {', '.join(analysis['skills'][:18])}\n"
        f"Resume strength {analysis['resume_strength']}/100. Screening score {screening['screening_score']}/100 "
        f"({screening['verdict']}).\nBreakdown: {parts}\n"
        f"Top job matches: {top}\nFlags: {flags}"
    )


def _fallback_narrative(profile: Dict[str, Any], analysis: Dict[str, Any], screening: Dict[str, Any], ranked: List[Dict[str, Any]]) -> Dict[str, Any]:
    name = profile.get("name") or "The candidate"
    best = ranked[0] if ranked else None
    strengths = [f["text"] for f in screening["flags"] if f["type"] == "green"][:4]
    concerns = [f["text"] for f in screening["flags"] if f["type"] in ("amber", "red")][:4]
    top_skills = ", ".join(analysis["skills"][:5]) or "limited detected skills"
    summary = (
        f"{name} is a {analysis['experience_level'].lower()} profile with {analysis['years_of_experience']:g} years of "
        f"experience and a screening score of {screening['screening_score']}/100 ({screening['verdict'].lower()}). "
        f"Key skills: {top_skills}."
    )
    if best:
        summary += f" Closest role in the database: {best['job']['title']} ({best['score']}% match)."
    questions = []
    if best and best["missing"]:
        questions.append(f"How would you get up to speed on {best['missing'][0]}?")
    questions += [
        "Walk me through the project you are most proud of and the measurable result.",
        "Describe a time you had to learn a new tool quickly.",
    ]
    return {"summary": summary, "strengths": strengths, "concerns": concerns, "interview_questions": questions[:4]}


class ScreenerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Screener",
            instructions=(
                "You are a senior recruiter writing a short screening note. Use ONLY the facts provided; never invent "
                "employers, numbers or skills. Return ONLY a JSON object: "
                '{"summary": "2-3 sentences", "strengths": ["3-4 short bullets"], '
                '"concerns": ["2-4 short bullets"], "interview_questions": ["3-4 targeted questions"]}'
            ),
        )

    async def run(self, messages: list) -> Dict[str, Any]:
        """Screen the candidate: a calculated score plus a written note."""
        print("👥 Screener: Conducting initial screening")
        ctx = messages[-1]["content"]
        if not isinstance(ctx, dict):
            ctx = self._load_payload(ctx)
        profile, analysis, ranked = ctx["profile"], ctx["analysis"], ctx["ranked"]

        screening = screen_candidate(analysis, ranked)
        narrative, source = _fallback_narrative(profile, analysis, screening, ranked), "rules"
        try:
            parsed = self._parse_json_safely(self._query_llm(_facts(profile, analysis, screening, ranked)))
            if "error" not in parsed and parsed.get("summary"):
                narrative = {
                    "summary": str(parsed.get("summary", "")).strip(),
                    "strengths": [str(x) for x in parsed.get("strengths", []) if x][:5] or narrative["strengths"],
                    "concerns": [str(x) for x in parsed.get("concerns", []) if x][:5] or narrative["concerns"],
                    "interview_questions": [str(x) for x in parsed.get("interview_questions", []) if x][:5] or narrative["interview_questions"],
                }
                source = "ai"
        except Exception as e:
            print(f"Screener AI note unavailable: {e}")

        return {
            **screening,
            "narrative": narrative,
            "narrative_source": source,
            "screening_timestamp": datetime.now().isoformat(timespec="seconds"),
        }
