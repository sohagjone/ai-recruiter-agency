from typing import Any, Callable, Dict, Optional

from .analyzer_agent import AnalyzerAgent
from .base_agent import BaseAgent
from .extractor_agent import ExtractorAgent
from .matcher_agent import MatcherAgent
from .recommender_agent import RecommenderAgent
from .screener_agent import ScreenerAgent

STAGES = ["extraction", "analysis", "matching", "screening", "recommendation"]


class OrchestratorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Orchestrator",
            instructions="Coordinate the recruitment workflow and pass results between the specialised agents.",
        )
        self._setup_agents()

    def _setup_agents(self):
        """Initialize all specialized agents"""
        self.extractor = ExtractorAgent()
        self.analyzer = AnalyzerAgent()
        self.matcher = MatcherAgent()
        self.screener = ScreenerAgent()
        self.recommender = RecommenderAgent()

    async def run(self, messages: list) -> Dict[str, Any]:
        """Process a single message through the agent"""
        response = self._query_llm(messages[-1]["content"])
        return self._parse_json_safely(response)

    async def process_application(
        self,
        resume_data: Dict[str, Any],
        progress: Optional[Callable[[str, str], None]] = None,
    ) -> Dict[str, Any]:
        """Main workflow: extract -> analyse -> match -> screen -> recommend.

        `progress(stage, state)` is called with state "running" or "done" so the
        interface can show live status. Agents pass real Python dicts to each other
        (no string round-trips, no eval()).
        """
        print("🎯 Orchestrator: Starting application process")
        notify = progress or (lambda stage, state: None)

        context: Dict[str, Any] = {
            "resume_data": {k: v for k, v in resume_data.items() if k != "file_bytes"},
            "status": "initiated",
            "current_stage": "extraction",
            "warnings": [],
        }

        try:
            notify("extraction", "running")
            extracted = await self.extractor.run([{"role": "user", "content": resume_data}])
            context.update(extracted_data=extracted, current_stage="analysis")
            context["warnings"] += extracted.get("warnings", [])
            notify("extraction", "done")
            profile, raw_text = extracted["profile"], extracted["raw_text"]

            notify("analysis", "running")
            analysis = await self.analyzer.run([{"role": "user", "content": extracted}])
            context.update(analysis_results=analysis, current_stage="matching")
            notify("analysis", "done")

            notify("matching", "running")
            matches = await self.matcher.run(
                [{"role": "user", "content": {"profile": profile, "analysis": analysis, "raw_text": raw_text}}]
            )
            context.update(job_matches=matches, current_stage="screening")
            notify("matching", "done")
            ranked = matches["matched_jobs"]

            notify("screening", "running")
            screening = await self.screener.run(
                [{"role": "user", "content": {"profile": profile, "analysis": analysis, "ranked": ranked}}]
            )
            context.update(screening_results=screening, current_stage="recommendation")
            notify("screening", "done")

            notify("recommendation", "running")
            recommendation = await self.recommender.run(
                [{"role": "user", "content": {
                    "profile": profile, "analysis": analysis, "raw_text": raw_text,
                    "ranked": ranked, "screening": screening,
                }}]
            )
            context.update(final_recommendation=recommendation, status="completed")
            notify("recommendation", "done")

            if "rules" in (screening["narrative_source"], recommendation["narrative_source"]):
                context["warnings"].append(
                    "The written AI commentary was unavailable for part of this run (rate limit or missing key). "
                    "All scores and charts are still fully calculated."
                )
            return context

        except Exception as e:
            context.update({"status": "failed", "error": str(e)})
            e.stage = context["current_stage"]  # lets the interface say where it stopped
            raise
