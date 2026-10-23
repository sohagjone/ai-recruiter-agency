from datetime import datetime
from typing import Any, Dict

from utils.scoring import analyse_profile
from .base_agent import BaseAgent


class AnalyzerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Analyzer",
            instructions="Analyze candidate profiles: skills, experience, education, impact and resume quality.",
        )

    async def run(self, messages: list) -> Dict[str, Any]:
        """Compute the candidate analysis (pure calculation, no AI call needed)."""
        print("🔍 Analyzer: Analyzing candidate profile")
        extracted = messages[-1]["content"]
        if not isinstance(extracted, dict):
            extracted = self._load_payload(extracted)

        analysis = analyse_profile(extracted["profile"], extracted["raw_text"])
        analysis["analysis_timestamp"] = datetime.now().isoformat(timespec="seconds")
        return analysis
