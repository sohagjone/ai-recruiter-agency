import io
import re
from typing import Any, Dict, List

from pdfminer.high_level import extract_text

from utils.exceptions import ExtractionError
from utils.skills import detect_skills, merge_skills
from .base_agent import BaseAgent

SCHEMA = """{
  "name": "full name",
  "headline": "current or most recent job title",
  "location": "city, country",
  "summary": "1-2 sentence professional summary",
  "skills": ["short skill names only"],
  "experience": [{"title": "", "company": "", "start": "YYYY-MM or YYYY", "end": "YYYY-MM, YYYY or Present", "description": ""}],
  "education": [{"degree": "", "field": "", "institution": "", "year": ""}],
  "certifications": [""],
  "achievements": ["bullets that contain a result or number"],
  "languages": [""]
}"""

_NOT_NAMES = {
    "resume", "curriculum", "vitae", "cv", "profile", "summary", "experience", "education",
    "skills", "contact", "objective", "references", "projects", "name",
}


def clean_resume_text(text: str) -> str:
    """Tidy PDF text: remove form feeds, page markers, blank lines and repeated spaces."""
    lines = []
    for line in (text or "").replace("\x0c", "\n").splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if not line or re.fullmatch(r"(?i)page \d+( of \d+)?", line):
            continue
        lines.append(line)
    return "\n".join(lines)


def guess_name(text: str) -> str:
    for line in text.splitlines()[:8]:
        line = re.sub(r"(?i)^(resume|curriculum vitae|cv|name)\s*[:\-–—]\s*", "", line).strip()
        if re.fullmatch(r"[A-Za-z][A-Za-z.'\-]+(?: [A-Za-z][A-Za-z.'\-]+){1,3}", line):
            if not any(w.lower() in _NOT_NAMES for w in line.split()):
                return line
    return ""


def guess_headline(text: str, name: str) -> str:
    lines = text.splitlines()[:8]
    for i, line in enumerate(lines):
        if name and name.lower() in line.lower() and i + 1 < len(lines):
            nxt = lines[i + 1]
            if len(nxt.split()) <= 6 and not re.search(r"[\d@:]", nxt) and nxt.lower() not in _NOT_NAMES:
                return nxt
    return ""


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _strings(value: Any, limit: int) -> List[str]:
    return [str(v).strip() for v in _as_list(value) if str(v).strip()][:limit]


class ExtractorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Extractor",
            instructions=(
                "You are a precise resume parser. Return ONLY one JSON object (no markdown, no commentary) "
                "with exactly this structure:\n" + SCHEMA + "\n"
                "Rules: copy facts from the resume only, never invent anything. Use \"\" or [] when something "
                "is missing. Skills must be short names (max 3 words): tools, technologies, methods and soft skills."
            ),
        )

    async def run(self, messages: list) -> Dict[str, Any]:
        """Read the PDF, then structure it (AI first, rule-based as a safety net)."""
        print("📄 Extractor: Processing resume")
        payload = messages[-1]["content"]
        if not isinstance(payload, dict):
            payload = self._load_payload(payload)

        if payload.get("text"):
            raw_text = payload["text"]
        else:
            try:
                source = io.BytesIO(payload["file_bytes"]) if payload.get("file_bytes") else payload["file_path"]
                raw_text = extract_text(source)
            except Exception as e:
                raise ExtractionError(f"Could not read this PDF: {e}") from e
        raw_text = clean_resume_text(raw_text)
        if len(raw_text.split()) < 20:
            raise ExtractionError(
                "Almost no text could be read from this PDF. It may be a scanned image - "
                "please upload a text-based PDF (export it from Word or Google Docs)."
            )

        warnings: List[str] = []
        parsed: Dict[str, Any] = {}
        mode = "ai"
        try:
            parsed = self._parse_json_safely(self._query_llm(raw_text))
            if "error" in parsed:
                raise ValueError(parsed["error"])
        except Exception as e:  # AI unavailable or answered badly: keep going with rules
            mode = "rules"
            parsed = {}
            warnings.append(f"AI extraction was unavailable, so the resume was read with built-in rules ({str(e)[:160]}).")

        name = str(parsed.get("name") or "").strip() or guess_name(raw_text)
        profile = {
            "name": name,
            "headline": str(parsed.get("headline") or "").strip() or guess_headline(raw_text, name),
            "location": str(parsed.get("location") or "").strip(),
            "summary": str(parsed.get("summary") or "").strip(),
            "skills": merge_skills(_strings(parsed.get("skills"), 40), detect_skills(raw_text))[:45],
            "experience": [e for e in _as_list(parsed.get("experience")) if isinstance(e, dict)][:15],
            "education": [e for e in _as_list(parsed.get("education")) if isinstance(e, dict)][:6],
            "certifications": _strings(parsed.get("certifications"), 10),
            "achievements": _strings(parsed.get("achievements"), 10),
            "languages": _strings(parsed.get("languages"), 6),
        }
        return {
            "raw_text": raw_text,
            "profile": profile,
            "extraction_mode": mode,
            "warnings": warnings,
            "extraction_status": "completed",
        }
