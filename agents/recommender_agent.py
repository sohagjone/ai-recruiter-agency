from datetime import datetime
from typing import Any, Dict, List

from utils.scoring import learning_roadmap, market_coverage, skill_priorities, make_candidate
from .base_agent import BaseAgent


def _fallback_narrative(profile: Dict[str, Any], analysis: Dict[str, Any], screening: Dict[str, Any], ranked: List[Dict[str, Any]], roadmap: List[Dict[str, Any]], fixes: List[Dict[str, Any]]) -> Dict[str, Any]:
    best = ranked[0] if ranked else None
    steps = []
    ready = [r for r in ranked if r["score"] >= 60][:3]
    if ready:
        steps.append("Apply now to: " + ", ".join(r["job"]["title"] for r in ready) + ".")
    if roadmap:
        steps.append("Learn next: " + ", then ".join(s["skill"] for s in roadmap[:3]) + ".")
    steps += [f["tip"] for f in fixes[:2]]
    headline = (
        f"Best current fit is {best['job']['title']} ({best['score']}%)." if best
        else "No close match found in the database yet."
    )
    path = ""
    if analysis["experience_level"] in ("Junior", "Mid-level") and analysis["years_of_experience"] > 0:
        path = f"With {analysis['years_of_experience']:g} years behind you, deepening the skills above is the quickest route to the next seniority level."
    return {"headline": headline, "next_steps": steps[:5], "resume_tips": [f["tip"] for f in fixes[:4]], "career_path": path}


class RecommenderAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Recommender",
            instructions=(
                "You are a career coach. Use ONLY the facts provided; never invent employers, numbers or skills. "
                "Return ONLY a JSON object: "
                '{"headline": "one sentence verdict", "next_steps": ["3-5 concrete actions"], '
                '"resume_tips": ["2-4 specific resume fixes"], "career_path": "1-2 sentences"}'
            ),
        )

    async def run(self, messages: list) -> Dict[str, Any]:
        """Turn the numbers into a plan: skill priorities, a learning roadmap and next steps."""
        print("💡 Recommender: Generating final recommendations")
        ctx = messages[-1]["content"]
        if not isinstance(ctx, dict):
            ctx = self._load_payload(ctx)
        profile, analysis, raw_text = ctx["profile"], ctx["analysis"], ctx["raw_text"]
        ranked, screening = ctx["ranked"], ctx["screening"]
        jobs = [r["job"] for r in ranked]
        cand = make_candidate(profile, analysis, raw_text)

        priorities = skill_priorities(jobs, ranked, cand)
        roadmap = learning_roadmap(jobs, cand, priorities)
        market = market_coverage([r["job"] for r in ranked[:8]], cand)  # demand across the best-matched roles
        fixes = sorted(
            [{"label": c["label"], "tip": c["tip"], "weight": c["weight"]} for c in analysis["ats_checks"] if not c["passed"]],
            key=lambda f: -f["weight"],
        )

        narrative = _fallback_narrative(profile, analysis, screening, ranked, roadmap, fixes)
        source = "rules"
        facts = (
            f"Candidate: {profile.get('name') or 'Unknown'}, {analysis['experience_level']}, {analysis['years_of_experience']:g} years.\n"
            f"Screening {screening['screening_score']}/100 ({screening['verdict']}). Resume strength {analysis['resume_strength']}/100.\n"
            f"Best matches: " + "; ".join(f"{r['job']['title']} {r['score']}%" for r in ranked[:3]) + "\n"
            f"Skills to learn (biggest impact first): {', '.join(p['skill'] for p in priorities[:5]) or 'none'}\n"
            f"Learning roadmap: " + " -> ".join(f"{s['skill']} (top-5 avg {s['avg_before']:g}->{s['avg_after']:g})" for s in roadmap) + "\n"
            f"Resume gaps: {', '.join(f['label'] for f in fixes[:4]) or 'none'}"
        )
        try:
            parsed = self._parse_json_safely(self._query_llm(facts))
            if "error" not in parsed and parsed.get("headline"):
                narrative = {
                    "headline": str(parsed["headline"]).strip(),
                    "next_steps": [str(x) for x in parsed.get("next_steps", []) if x][:6] or narrative["next_steps"],
                    "resume_tips": [str(x) for x in parsed.get("resume_tips", []) if x][:5] or narrative["resume_tips"],
                    "career_path": str(parsed.get("career_path", "")).strip() or narrative["career_path"],
                }
                source = "ai"
        except Exception as e:
            print(f"Recommender AI plan unavailable: {e}")

        return {
            "priorities": priorities,
            "roadmap": roadmap,
            "market": market,
            "resume_fixes": fixes,
            "narrative": narrative,
            "narrative_source": source,
            "recommendation_timestamp": datetime.now().isoformat(timespec="seconds"),
        }
