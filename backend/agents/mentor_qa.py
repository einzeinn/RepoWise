"""
Q&A handler for Mentor Agent - implements real conversation capability.
Processes follow-up questions with context from architecture docs.
"""

import os
import re
import httpx
import asyncio
import logging
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

class MentorQAHandler:
    """Handles Q&A for the Mentor agent with context awareness."""

    def __init__(self):
        raw_groq = os.getenv("GROQ_API_KEY", "")
        self.groq_api_key = raw_groq if raw_groq and "your_" not in raw_groq and "_here" not in raw_groq else None

        raw_featherless = os.getenv("FEATHERLESS_API_KEY", "")
        self.featherless_api_key = raw_featherless if raw_featherless and "your_" not in raw_featherless and "_here" not in raw_featherless else None

        raw_qwen = os.getenv("QWEN_API_KEY", "")
        self.qwen_api_key = raw_qwen if raw_qwen and "your_" not in raw_qwen and "_here" not in raw_qwen else None

    def _get_fallback_answer(self, question: str, docs: Dict[str, str]) -> str:
        """Fallback answer when no API key is available."""
        q = question.lower()

        if any(w in q for w in ["start", "begin", "first", "mulai", "where", "mana"]):
            return "To get started, read README.md and follow the setup instructions. Start from the main entry point (main.py, app.py, or index.js) to understand the overall structure."

        if any(w in q for w in ["how", "work", "function", "purpose", "cara", "fungsi"]):
            return "This project is organized into modules with specific responsibilities. Check the architecture documentation to understand how each module works and interacts."

        if any(w in q for w in ["file", "code", "module"]):
            if docs:
                files_list = "\n".join([f"- `{path}`" for path in list(docs.keys())[:5]])
                return f"Main files in this project:\n{files_list}\n\nEach file has a specific function. Check the architecture docs for more details."
            return "The project has several modules. Check the architecture docs for details."

        if any(w in q for w in ["setup", "install", "run", "configure", "jalankan", "pasang"]):
            return "Follow the setup instructions in README.md. Install dependencies first, configure environment variables, and run the application as instructed."

        if any(w in q for w in ["contribute", "help", "task", "issue", "kontribusi", "tugas"]):
            return "Check the 'Suggested Tasks' section for good first issues. Start with documentation improvements or small bug fixes to get familiar with the codebase."

        return "Good question! Based on the project structure and docs, I suggest reviewing the architecture guide and relevant module documentation. For specific details, check the individual file documentation."

    async def _call_llm_messages(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 500
    ) -> Optional[str]:
        """
        Call LLM with conversation history.
        Uses global_llm_semaphore for queueing with other agents.
        """
        from .base import global_llm_semaphore

        async with global_llm_semaphore:
            # Use 1.5s delay to avoid API rate limit bursts
            await asyncio.sleep(1.5)

            # ── Featherless (Primary) ───────────────────────────────
            if self.featherless_api_key:
                url = "https://api.featherless.ai/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {self.featherless_api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": "Qwen/Qwen2.5-Coder-32B-Instruct",
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.4,
                }
                
                for attempt in range(3):
                    try:
                        logging.info(f"[MentorQA] Featherless call attempt {attempt + 1}/3")
                        async with httpx.AsyncClient(timeout=60.0) as client:
                            resp = await client.post(url, headers=headers, json=payload)
                        
                        if resp.status_code == 200:
                            answer = resp.json()["choices"][0]["message"]["content"].strip()
                            logging.info("[MentorQA] Featherless OK")
                            return answer
                        
                        elif resp.status_code == 429:
                            if self.qwen_api_key or self.groq_api_key:
                                logging.warning("[MentorQA] Featherless 429 — switching to fallback.")
                                break
                            
                            retry_after = 8.0 * (attempt + 1)
                            try:
                                msg = resp.json().get("error", {}).get("message", "")
                                m = re.search(r"try again in (\d+\.?\d*)s", msg)
                                if m:
                                    retry_after = float(m.group(1)) + 0.5
                            except Exception:
                                pass
                            logging.warning(f"[MentorQA] Featherless 429 — waiting {retry_after:.1f}s")
                            await asyncio.sleep(retry_after)
                        else:
                            logging.error(f"[MentorQA] Featherless {resp.status_code}: {resp.text[:200]}")
                            break
                    except Exception as e:
                        logging.error(f"[MentorQA] Featherless exception: {e}")
                        break

            # ── Qwen (Secondary) ────────────────────────────────────
            if self.qwen_api_key:
                url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {self.qwen_api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": "qwen-plus",
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.4,
                }

                for attempt in range(2):
                    try:
                        logging.info(f"[MentorQA] Qwen call attempt {attempt + 1}/2")
                        async with httpx.AsyncClient(timeout=60.0) as client:
                            resp = await client.post(url, headers=headers, json=payload)

                        if resp.status_code == 200:
                            answer = resp.json()["choices"][0]["message"]["content"].strip()
                            logging.info("[MentorQA] Qwen OK")
                            return answer

                        elif resp.status_code == 429:
                            if self.groq_api_key:
                                logging.warning("[MentorQA] Qwen 429 — switching to Groq fallback.")
                                break
                            retry_after = 5.0 * (attempt + 1)
                            logging.warning(f"[MentorQA] Qwen 429 — waiting {retry_after:.1f}s")
                            await asyncio.sleep(retry_after)

                        else:
                            logging.error(f"[MentorQA] Qwen {resp.status_code}: {resp.text[:200]}")
                            break

                    except Exception as e:
                        logging.error(f"[MentorQA] Qwen exception: {e}")
                        break

            # ── Groq (Last Fallback) ────────────────────────────────
            if self.groq_api_key:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {self.groq_api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": "llama-3.1-8b-instant",
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.4,
                }
                try:
                    logging.info("[MentorQA] Groq fallback call...")
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        answer = resp.json()["choices"][0]["message"]["content"].strip()
                        logging.info("[MentorQA] Groq OK")
                        return answer
                    else:
                        logging.error(f"[MentorQA] Groq {resp.status_code}: {resp.text[:200]}")
                except Exception as e:
                    logging.error(f"[MentorQA] Groq exception: {e}")

            logging.warning("[MentorQA] All LLM providers failed.")
            return None

    async def answer_question(self, question: str, context: Dict[str, Any]) -> str:
        """Answer a single question based on project context."""
        architecture_docs = context.get("architecture_docs", {})
        repo_name = context.get("repository_name", "the project")

        if not self.groq_api_key and not self.featherless_api_key and not self.qwen_api_key:
            return self._get_fallback_answer(question, architecture_docs)

        docs_context = "\n\n".join([
            f"File: {path}\nDocumentation: {doc[:400]}"
            for path, doc in list(architecture_docs.items())[:5]
        ])
        docs_context = docs_context[:3000]

        onboarding = context.get("onboarding_guide", "Not available.")

        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a helpful technical mentor for the '{repo_name}' project. "
                    "Answer questions concisely based on the project documentation. "
                    "Use standard markdown: - for bullets, ** for bold. "
                    "Never use + as bullet points. Answer in English. Max 250 words."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Project documentation:\n{docs_context}\n\n"
                    f"Onboarding guide:\n{onboarding}\n\n"
                    f"Question: {question}"
                ),
            },
        ]

        answer = await self._call_llm_messages(messages, max_tokens=500)
        return answer if answer else self._get_fallback_answer(question, architecture_docs)

    async def chat(
        self,
        question: str,
        context: Dict[str, Any],
        chat_history: List[Dict[str, str]]
    ) -> str:
        """Conduct a chat with conversation history."""
        architecture_docs = context.get("architecture_docs", {})
        repo_name = context.get("repository_name", "the project")

        if not self.groq_api_key and not self.featherless_api_key and not self.qwen_api_key:
            return self._get_fallback_answer(question, architecture_docs)

        # Build project context for the system prompt
        docs_context = "\n\n".join([
            f"File: {path}\nDocumentation: {doc[:300]}"
            for path, doc in list(architecture_docs.items())[:8]
        ])[:2500]

        onboarding = context.get("onboarding_guide", "")
        onboarding_snippet = onboarding[:800] if onboarding else "Not available."

        code_review = context.get("code_review", {})
        quality_score = context.get("quality_score", 0)
        quality_label = context.get("quality_score_label", "")
        review_summary = ""
        if code_review:
            strengths = code_review.get("strengths", [])
            issues = code_review.get("issues", [])
            recs = code_review.get("recommendations", [])
            parts = []
            if strengths:
                parts.append(f"Strengths: {'; '.join(strengths[:3])}")
            if issues:
                parts.append(f"Issues: {'; '.join(issues[:3])}")
            if recs:
                parts.append(f"Recommendations: {'; '.join(recs[:3])}")
            review_summary = "\n".join(parts)

        suggested_tasks = context.get("suggested_tasks", "")
        tasks_snippet = suggested_tasks[:500] if suggested_tasks else ""

        system_content = (
            f"You are a helpful technical mentor for the '{repo_name}' project. "
            "Answer questions concisely and accurately based on the codebase context below. "
            "Use standard markdown: - for bullets, ** for bold. "
            "Never use + as bullet points. Answer in English. Max 250 words.\n\n"
            f"## Project Documentation\n{docs_context}\n\n"
            f"## Onboarding Guide\n{onboarding_snippet}"
        )
        if review_summary:
            system_content += f"\n\n## Code Review (Score: {quality_score}/100 — {quality_label})\n{review_summary}"
        if tasks_snippet:
            system_content += f"\n\n## Suggested Tasks\n{tasks_snippet}"

        messages = [
            {"role": "system", "content": system_content}
        ]

        for msg in chat_history[-6:]:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })

        messages.append({"role": "user", "content": question})

        answer = await self._call_llm_messages(messages, max_tokens=500)
        return answer if answer else self._get_fallback_answer(question, architecture_docs)