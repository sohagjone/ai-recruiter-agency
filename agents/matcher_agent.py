from typing import Any, Dict

from db.database import JobDatabase
from utils.scoring import make_candidate, rank_jobs, salary_estimate, top_avg
from .base_agent import BaseAgent

MIN_SCORE_TO_COUNT = 30


class MatcherAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Matcher",
            instructions="Match candidate profiles with job positions using skills, experience and level.",
        )
        self.db = JobDatabase()

    async def run(self, messages: list) -> Dict[str, Any]:
        """Score the candidate against every job in the database."""
        print("🎯 Matcher: Finding suitable job matches")
        ctx = messages[-1]["content"]
        if not isinstance(ctx, dict):
            ctx = self._load_payload(ctx)

        jobs = self.db.get_unique_jobs()
        cand = make_candidate(ctx["profile"], ctx["analysis"], ctx["raw_text"])
        ranked = rank_jobs(jobs, cand)

        return {
            # every job, best first; the interface filters and sorts them
            "matched_jobs": ranked,
            "number_of_jobs_scored": len(ranked),
            "number_of_matches": sum(1 for r in ranked if r["score"] >= MIN_SCORE_TO_COUNT),
            "best_score": ranked[0]["score"] if ranked else 0,
            "top5_average": top_avg(ranked),
            "salary_estimate": salary_estimate(ranked),
        }
