"""
Reviewer Agent for RepoWise.
Simple logic: receives architecture_docs from Documenter,
outputs structured code quality review with strengths, issues, and recommendations.
"""

import os
import re
import logging
from typing import Any, Dict, List, Tuple

from .base import AgentResponse, BaseAgent

# Extensions considered as core source code
_CODE_EXTENSIONS = {
    '.py', '.ts', '.tsx', '.js', '.jsx', '.go', '.rs', '.java', '.kt',
    '.rb', '.php', '.cs', '.cpp', '.c', '.h', '.hpp', '.swift', '.scala',
    '.lua', '.r', '.dart', '.vue', '.svelte',
}

# Low-value extensions to deprioritize
_LOW_VALUE_EXTENSIONS = {
    '.md', '.txt', '.lock', '.json', '.yaml', '.yml', '.toml', '.ini',
    '.cfg', '.csv', '.svg', '.png', '.jpg', '.gif', '.ico',
}

# Path segments that indicate non-core code
_SKIP_SEGMENTS = {
    'node_modules', '__pycache__', '.git', 'vendor', 'dist', 'build',
    '.next', '.venv', 'venv', '.tox', 'site-packages',
}


class ReviewerAgent(BaseAgent):
    """
    Takes architecture_docs (file path → summary dict) and produces:
      - review: { strengths: string[], issues: string[], recommendations: string[] }
      - quality_score: integer 0–100
      - quality_score_label: "excellent" / "good" / "needs improvement" / "poor"
    """

    def __init__(self):
        super().__init__(name="Reviewer")

    async def process(self, context: Dict[str, Any]) -> AgentResponse:
        repo_name: str = context.get("repository_name", "Unknown")
        architecture_docs: Dict[str, str] = context.get("architecture_docs", {})

        logging.info(f"[Reviewer] Starting review for '{repo_name}' ({len(architecture_docs)} docs)")

        # ── Guard: nothing to review ──
        if not architecture_docs:
            logging.warning("[Reviewer] No architecture_docs — skipping.")
            return AgentResponse(
                status="success",
                agent_name=self.name,
                data={
                    **context,
                    "review": {
                        "strengths": [],
                        "issues": ["No files were documented — cannot perform code review."],
                        "recommendations": [],
                    },
                    "quality_score": 0,
                    "quality_score_label": "unscored",
                },
                message="No architecture docs to review.",
            )

        # ── Smart file selection: prioritize important files ──
        selected_files = self._prioritize_files(architecture_docs)

        logging.info(
            f"[Reviewer] Selected {len(selected_files)}/{len(architecture_docs)} files for review"
        )

        # ── Build context block from prioritized files ──
        docs_block = ""
        for path, summary in selected_files:
            truncated = str(summary)[:600] + ("..." if len(str(summary)) > 600 else "")
            docs_block += f"\n\n### {path}\n{truncated}"
        docs_block = docs_block[:6000]

        system_prompt = (
            "You are a strict senior software engineer performing a code quality review. "
            "Be concise and actionable. Write in English. "
            "Use - for bullet points. Never use + as bullet points. "
            "Be critical — do NOT give inflated scores."
        )

        user_prompt = (
            f"Review the code quality of repository '{repo_name}' based on these file summaries.\n\n"
            f"## Scoring Rubric (use this strictly):\n"
            f"- 90-100: Exceptional codebase. Clean architecture, comprehensive tests, "
            f"excellent error handling, consistent style, well-documented.\n"
            f"- 70-89: Good but has gaps. Decent structure but missing tests, "
            f"inconsistent patterns, or limited error handling.\n"
            f"- 50-69: Needs work. Significant issues in architecture, error handling, "
            f"or code organization. Some anti-patterns present.\n"
            f"- 30-49: Poor quality. Major structural problems, missing error handling, "
            f"no tests, inconsistent conventions.\n"
            f"- 0-29: Critical issues. Unmaintainable code, security vulnerabilities, "
            f"or essentially non-functional.\n\n"
            f"IMPORTANT: Most repos are NOT 90+. Deduct points for:\n"
            f"- Missing or incomplete tests (-10 to -20)\n"
            f"- Limited error handling (-5 to -15)\n"
            f"- No documentation or poor docs (-5 to -10)\n"
            f"- Inconsistent code style (-5 to -10)\n"
            f"- Hardcoded values, magic numbers (-5 to -10)\n"
            f"- Missing type safety or input validation (-5 to -15)\n\n"
            f"Respond in EXACTLY this format:\n\n"
            f"STRENGTHS\n"
            f"- <strength 1>\n"
            f"- <strength 2>\n"
            f"- <strength 3>\n\n"
            f"ISSUES\n"
            f"- <issue 1>\n"
            f"- <issue 2>\n"
            f"- <issue 3>\n\n"
            f"RECOMMENDATIONS\n"
            f"- <suggestion 1>\n"
            f"- <suggestion 2>\n"
            f"- <suggestion 3>\n\n"
            f"SCORE: <integer 0-100>/100\n\n"
            f"File summaries:\n{docs_block}"
        )

        # ── LLM call (Qwen handles larger context well) ──
        raw_output = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=1200,
            temperature=0.3,
        )

        # ── Parse into structured review ──
        if raw_output:
            review = self._parse_review(raw_output)
            score = self._extract_score(raw_output)
        else:
            review = self._fallback_review(architecture_docs)
            score = 50

        label = (
            "excellent" if score >= 80
            else "good" if score >= 60
            else "needs improvement" if score >= 40
            else "poor" if score > 0
            else "unscored"
        )

        logging.info(f"[Reviewer] Done. Score: {score}/100 ({label})")

        return AgentResponse(
            status="success",
            agent_name=self.name,
            data={
                **context,
                "review": review,
                "quality_score": score,
                "quality_score_label": label,
            },
            message=f"Code review complete. Score: {score}/100 ({label}).",
        )

    # ------------------------------------------------------------------ #
    #  File prioritization                                                 #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _prioritize_files(docs: Dict[str, str]) -> List[Tuple[str, str]]:
        """Score and rank files by importance for code review.

        Scoring:
          +10  code extension (.py, .ts, .go, etc.)
          +8   root-level or one-level-deep file (not nested in test/vendor)
          +5   medium size summary (50-500 chars — has substance but not bloated)
          +3   known important filenames (main, app, index, config, server, routes, etc.)
          -5   inside skip segments (node_modules, __pycache__, .git, vendor, dist, build)
          -3   low-value extension (.md, .json, .lock, .yaml, etc.)
          -2   very short summary (<30 chars — likely empty/trivial file)
        """
        scored: List[Tuple[float, str, str]] = []

        for path, summary in docs.items():
            score = 0.0
            parts = path.replace("\\", "/").split("/")
            ext = os.path.splitext(parts[-1])[1].lower()
            depth = len(parts) - 1
            filename = parts[-1].lower()

            # Extension value
            if ext in _CODE_EXTENSIONS:
                score += 10
            elif ext in _LOW_VALUE_EXTENSIONS:
                score -= 3

            # Depth: root/1-level files are most important
            if depth <= 1:
                score += 8
            elif depth <= 2:
                score += 4

            # Skip segments penalty
            if any(seg in _SKIP_SEGMENTS for seg in parts):
                score -= 5

            # Important filenames
            important_names = {
                'main', 'app', 'index', 'config', 'server', 'routes',
                'handler', 'service', 'client', 'api', 'model', 'schema',
                'middleware', 'auth', 'utils', 'helpers', 'core', 'base',
                'settings', 'constants', 'types', 'exceptions',
            }
            name_no_ext = os.path.splitext(filename)[0]
            if name_no_ext in important_names:
                score += 3

            # Summary substance
            summary_len = len(str(summary))
            if summary_len < 30:
                score -= 2
            elif 50 <= summary_len <= 500:
                score += 5
            elif summary_len > 500:
                score += 3  # long but still useful

            scored.append((score, path, summary))

        # Sort descending by score, return top 20
        scored.sort(key=lambda x: x[0], reverse=True)
        return [(path, summary) for _, path, summary in scored[:20]]

    # ------------------------------------------------------------------ #
    #  Parsing helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_review(raw: str) -> Dict[str, List[str]]:
        """Parse LLM output into structured sections."""
        section_map = {
            "STRENGTHS": "strengths",
            "CODE QUALITY NOTES": "strengths",
            "ISSUES": "issues",
            "POTENTIAL ISSUES": "issues",
            "RECOMMENDATIONS": "recommendations",
            "IMPROVEMENT SUGGESTIONS": "recommendations",
        }

        result: Dict[str, List[str]] = {"strengths": [], "issues": [], "recommendations": []}
        current_key: str | None = None

        for line in raw.splitlines():
            stripped = line.strip()
            upper = stripped.upper().lstrip("#").strip()

            # Check if this line is a section header
            matched = None
            for header, key in section_map.items():
                if upper.startswith(header):
                    matched = key
                    break

            if matched:
                current_key = matched
                # Check for inline content after header (e.g. "STRENGTHS - item")
                remainder = stripped
                for header in section_map:
                    if upper.startswith(header):
                        remainder = stripped[len(header):].lstrip(":- ").strip()
                        break
                if remainder and current_key and not remainder.startswith("#"):
                    result[current_key].append(remainder.lstrip("-•* ").strip())
                continue

            # Skip SCORE lines
            if upper.startswith("SCORE"):
                current_key = None
                continue

            # Collect bullet items
            if current_key and stripped.startswith(("-", "•", "*")):
                item = stripped.lstrip("-•* ").strip()
                if item:
                    result[current_key].append(item)

        return result

    @staticmethod
    def _extract_score(text: str) -> int:
        """Extract the first integer that looks like a score (0-100) from text."""
        m = re.search(r"(\d{1,3})\s*/\s*100", text)
        if m:
            return min(100, max(0, int(m.group(1))))
        m = re.search(r"[Ss]core[:\s]*(\d{1,3})", text)
        if m:
            val = int(m.group(1))
            if val <= 10:
                val *= 10
            return min(100, max(0, val))
        return 0

    @staticmethod
    def _fallback_review(docs: Dict[str, str]) -> Dict[str, List[str]]:
        """Generate a static review when LLM is unavailable."""
        return {
            "strengths": [
                f"Repository has {len(docs)} documented source files",
            ],
            "issues": [
                "Could not perform deep LLM-based review (API unavailable)",
                "Could not verify error handling patterns",
                "Could not verify test coverage",
            ],
            "recommendations": [
                "Ensure all public functions have docstrings",
                "Add unit tests for core logic",
                "Review error handling in async code paths",
            ],
        }
