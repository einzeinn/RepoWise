import os
from typing import Any, Dict
from dotenv import load_dotenv

from .base import BaseAgent, AgentResponse
from .fallback_responses import get_fallback_suggested_tasks

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

class TaskSuggesterAgent(BaseAgent):
    """
    Agen yang menganalisis arsitektur dan mengusulkan
    3 good first issues untuk developer baru.
    """
    def __init__(self):
        super().__init__(name="Task_Suggester_Agent")

    async def process(self, context: Dict[str, Any]) -> AgentResponse:
        docs = context.get("architecture_docs", {})
        quality_score: int = context.get("quality_score", 0)
        quality_label: str = context.get("quality_score_label", "unknown")
        review: Dict[str, Any] = context.get("review", {})

        if not docs:
            file_tree = context.get("file_tree", [])
            if file_tree:
                suggested_tasks = get_fallback_suggested_tasks()
                context["suggested_tasks"] = suggested_tasks
                return AgentResponse(
                    status="success",
                    agent_name=self.name,
                    data=context,
                    message="Suggested tasks created from file tree (fallback mode)."
                )
            return AgentResponse(
                status="error",
                agent_name=self.name,
                data=context,
                message="No documentation available for Task Suggester to analyze."
            )

        if not self.groq_api_key and not self.featherless_api_key and not self.qwen_api_key:
            suggested_tasks = get_fallback_suggested_tasks()
        else:
            combined_docs = "\n\n".join([
                f"File: {path}\nSummary: {summary[:500]}"
                for path, summary in docs.items()
            ])
            combined_docs = combined_docs[:3000]

            # Build reviewer context summary
            review_context = ""
            if isinstance(review, dict):
                issues = review.get("issues", [])
                recs = review.get("recommendations", [])
                if issues:
                    review_context += "\n\nCODE REVIEW ISSUES FOUND:\n" + "\n".join([f"- {i}" for i in issues[:3]])
                if recs:
                    review_context += "\n\nREVIEWER RECOMMENDATIONS:\n" + "\n".join([f"- {r}" for r in recs[:3]])

            if quality_score > 0:
                review_context += f"\n\nCODE QUALITY SCORE: {quality_score}/100 ({quality_label})"
                if quality_score >= 70:
                    review_context += " — Code quality is decent, suggest tasks that improve it further (optimization, refactoring, advanced features)."
                elif quality_score >= 40:
                    review_context += " — Code has room for improvement, suggest tasks addressing the issues found above."
                else:
                    review_context += " — Code quality is poor, prioritize fixing critical issues, adding error handling, and basic cleanup tasks."

            system_prompt = (
                "You are a pragmatic Engineering Manager assigning initial tasks "
                "to a new developer joining the team. "
                "Use standard markdown only: - for bullets, ** for bold. "
                "Never use + as bullet points. Keep each task concise and actionable."
            )
            user_prompt = (
                f"Based on the following codebase file summary and code review results, suggest exactly 3 initial tasks "
                f"or 'good first issues' that are safe for a new developer to work on. "
                f"IMPORTANT: Let the code review findings influence your suggestions — "
                f"if there are issues flagged, suggest tasks that address them. "
                f"(e.g., minor refactoring, unit tests, code cleanup, error handling).\n\n"
                f"Format EACH task EXACTLY like this:\n\n"
                f"**Task 1: <task name>**\n"
                f"- Goal: <one clear sentence>\n"
                f"- Steps:\n"
                f"  - <step 1>\n"
                f"  - <step 2>\n"
                f"  - <step 3>\n\n"
                f"**Task 2: <task name>**\n"
                f"- Goal: <one clear sentence>\n"
                f"- Steps:\n"
                f"  - <step 1>\n"
                f"  - <step 2>\n"
                f"  - <step 3>\n\n"
                f"**Task 3: <task name>**\n"
                f"- Goal: <one clear sentence>\n"
                f"- Steps:\n"
                f"  - <step 1>\n"
                f"  - <step 2>\n"
                f"  - <step 3>\n\n"
                f"Codebase:\n{combined_docs}\n{review_context}"
            )

            response = await self._call_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=800,
                temperature=0.5
            )

            suggested_tasks = response if response else get_fallback_suggested_tasks()

        context["suggested_tasks"] = suggested_tasks
        return AgentResponse(
            status="success",
            agent_name=self.name,
            data=context,
            message="Initial task suggestions successfully created."
        )