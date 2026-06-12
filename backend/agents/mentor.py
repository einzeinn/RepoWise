import os
from typing import Any, Dict
from dotenv import load_dotenv

from .base import BaseAgent, AgentResponse
from .fallback_responses import get_fallback_onboarding

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

class MentorAgent(BaseAgent):
    """
    Agen mentor teknis — membaca arsitektur dan membuat
    panduan onboarding ringkas untuk developer baru.
    """
    def __init__(self):
        super().__init__(name="Mentor_Agent")

    async def process(self, context: Dict[str, Any]) -> AgentResponse:
        docs = context.get("architecture_docs", {})
        repo_name = context.get("repository_name", "Unknown")

        if not docs:
            file_tree = context.get("file_tree", [])
            if file_tree:
                onboarding_guide = get_fallback_onboarding(repo_name, {})
                context["onboarding_guide"] = onboarding_guide
                return AgentResponse(
                    status="success",
                    agent_name=self.name,
                    data=context,
                    message="Onboarding guide generated from file tree (fallback mode)."
                )
            return AgentResponse(
                status="error",
                agent_name=self.name,
                data=context,
                message="No documentation available for Mentor to analyze."
            )

        if not self.groq_api_key and not self.featherless_api_key and not self.qwen_api_key:
            onboarding_guide = get_fallback_onboarding(repo_name, docs)
        else:
            combined_docs = "\n\n".join([
                f"File: {path}\nSummary: {summary[:500]}"
                for path, summary in docs.items()
            ])
            combined_docs = combined_docs[:3000]

            system_prompt = (
                "You are a senior software engineer mentoring a new developer. "
                "Write a clear, friendly onboarding guide in English. "
                "Use standard markdown only: - for bullets, ** for bold, # for headings. "
                "Never use + as bullet points. Be concise and practical."
            )
            user_prompt = (
                f"Based on the following architecture summary of repository '{repo_name}', "
                f"create a brief onboarding guide for a new developer.\n\n"
                f"Format the guide EXACTLY like this:\n"
                f"**Welcome to {repo_name}**\n"
                f"<1-2 sentences project description>\n\n"
                f"**Module Architecture**\n"
                f"- <explain how modules interact with each other>\n\n"
                f"**Getting Started Steps**\n"
                f"- Step 1: ...\n"
                f"- Step 2: ...\n"
                f"- Step 3: ...\n\n"
                f"**Important Files to Understand First**\n"
                f"- `<filename>`: <why this file is important>\n\n"
                f"Architecture summary:\n{combined_docs}"
            )

            response = await self._call_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=600,
                temperature=0.4
            )

            onboarding_guide = response if response else get_fallback_onboarding(repo_name, docs)

        context["onboarding_guide"] = onboarding_guide
        return AgentResponse(
            status="success",
            agent_name=self.name,
            data=context,
            message="Onboarding guide successfully created."
        )