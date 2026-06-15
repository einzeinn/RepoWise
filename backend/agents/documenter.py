import os
import base64
import httpx
import asyncio
import logging
from typing import Any, Dict, List
from dotenv import load_dotenv

from .base import BaseAgent, AgentResponse
from .fallback_responses import get_fallback_documentation

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

class DocumenterAgent(BaseAgent):
    """
    Fetch all files in parallel (GitHub API safe),
    then analyze ALL files in 1 LLM call — saves quota significantly.
    Before: N calls (1 per file). Now: 1 call total.
    """
    def __init__(self):
        super().__init__(name="Documenter_Agent")
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.github_headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "REPOWISE-Documenter",
        }
        if self.github_token:
            self.github_headers["Authorization"] = f"Bearer {self.github_token}"

    async def _fetch_file_content(self, owner: str, repo: str, file_path: str) -> str:
        """Fetch file content from GitHub (parallel, GitHub API safe)."""
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
                resp = await client.get(url, headers=self.github_headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if "content" in data:
                        return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        except Exception:
            pass
        return ""

    async def _analyze_all_files_batch(self, files_content: Dict[str, str], reviewer_feedback: str = "") -> Dict[str, str]:
        """
        BATCH: Send all files to LLM in 1 call.
        Much more efficient vs 1 call per file.
        If reviewer_feedback is provided, focus on addressing the reviewer's concerns.
        Returns dict {file_path: summary}.
        """
        if not files_content:
            return {}

        # Build prompt with all files at once
        files_block = ""
        for path, content in files_content.items():
            # Truncate per file: 1500 chars (~375 tokens) — with 5 files = ~1875 tokens total
            truncated = content[:1500] + ("\n...[TRUNCATED]" if len(content) > 1500 else "")
            files_block += f"\n\n=== FILE: {path} ===\n{truncated}"

        system_prompt = (
            "You are a technical documentation writer. "
            "Analyze each file separately and provide a concise technical summary. "
            "Write in English. Be brief — max 2 short paragraphs per file."
        )

        user_prompt = (
            f"Analyze these {len(files_content)} files from a GitHub repository "
            f"and provide a technical summary for EACH file.\n"
            f"Format your response EXACTLY like this for each file:\n\n"
            f"### FILE: <file_path>\n<summary here>\n\n"
            f"Files to analyze:{files_block}"
        )

        # If reviewer sent feedback, inject as SUPPLEMENTARY context — not a replacement
        if reviewer_feedback:
            system_prompt += (
                " IMPORTANT: This is a RE-ANALYSIS pass. Your PRIMARY task is still to "
                "analyze each file based on its ACTUAL CODE content. Maintain accurate "
                "technical summaries of what each file does. The reviewer feedback below "
                "is SUPPLEMENTARY — use it to ADD observations about error handling, "
                "edge cases, or code quality issues you may have missed. "
                "Do NOT let the feedback override or distort your core file analysis."
            )
            user_prompt += (
                f"\n\n=== REVIEWER FEEDBACK (supplementary — enhance your analysis with these points) ===\n"
                f"{reviewer_feedback}\n"
                f"=== END FEEDBACK ===\n"
                f"REMEMBER: Your summaries must reflect the ACTUAL code in each file above. "
                f"The feedback is additional context only — do not invent issues that are not in the code."
            )

        # 1 LLM call for all files — with retry on connection error
        MAX_RETRIES = 3
        raw_response = None
        for attempt in range(MAX_RETRIES):
            try:
                raw_response = await self._call_llm(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=800,  # larger for multi-file
                    temperature=0.3,
                )
                if raw_response:
                    break
            except Exception as e:
                logging.warning(f"[{self.name}] LLM call attempt {attempt + 1} failed: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** attempt)  # exponential backoff: 1s, 2s
                else:
                    logging.error(f"[{self.name}] All {MAX_RETRIES} LLM attempts failed")

        if not raw_response:
            return {}

        # Parse response per file
        result: Dict[str, str] = {}
        current_path = None
        current_lines: List[str] = []

        for line in raw_response.splitlines():
            if line.startswith("### FILE:"):
                # Save previous file
                if current_path and current_lines:
                    result[current_path] = "\n".join(current_lines).strip()
                # Try exact path match, fallback to partial match
                mentioned_path = line.replace("### FILE:", "").strip()
                matched = next(
                    (p for p in files_content if p == mentioned_path or p.endswith(mentioned_path) or mentioned_path.endswith(p.split("/")[-1])),
                    mentioned_path  # fallback: use what LLM wrote
                )
                current_path = matched
                current_lines = []
            elif current_path is not None:
                current_lines.append(line)

        # Save last file
        if current_path and current_lines:
            result[current_path] = "\n".join(current_lines).strip()

        # Fallback: if any file wasn't parsed, add placeholder
        for path in files_content:
            if path not in result:
                result[path] = f"Summary not available for `{path}`."

        return result

    async def process(self, context: Dict[str, Any]) -> AgentResponse:
        files = context.get("files", []) or context.get("file_tree", [])
        owner = context.get("repository_owner", "")
        repo  = context.get("repository_name", "")

        if not files or not owner or not repo:
            return AgentResponse(
                status="error",
                agent_name=self.name,
                data=context,
                message="Incomplete data from Explorer Agent",
            )

        # Filter to source code files only
        important_ext = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".cpp", ".c", ".rb"}
        important_files = [
            f for f in files
            if any((f.get("path", "") or f.get("name", "")).endswith(ext) for ext in important_ext)
        ][:5]  # max 5 file

        if not important_files:
            return AgentResponse(
                status="error",
                agent_name=self.name,
                data=context,
                message="No source code files found",
            )

        # 1. Fetch all files in PARALLEL (GitHub API safe)
        fetch_tasks = {
            (f.get("path", "") or f.get("name", "")): self._fetch_file_content(owner, repo, f.get("path", "") or f.get("name", ""))
            for f in important_files
        }
        results = await asyncio.gather(*fetch_tasks.values(), return_exceptions=True)
        fetched: Dict[str, str] = {
            path: content
            for path, content in zip(fetch_tasks.keys(), results)
            if isinstance(content, str) and content.strip()
        }

        if not fetched:
            fallback_docs = get_fallback_documentation(repo, files)
            return AgentResponse(
                status="success",
                agent_name=self.name,
                data={**context, "architecture_docs": fallback_docs},
                message="Failed to fetch files — using fallback documentation",
            )

        # 2. Analyze ALL files in 1 LLM call (with optional reviewer feedback)
        feedback = context.get("reviewer_feedback", "")
        logging.info(f"[{self.name}] Batch analyzing {len(fetched)} files in 1 LLM call{' (with reviewer feedback)' if feedback else ''}...")
        architecture_docs = await self._analyze_all_files_batch(fetched, reviewer_feedback=feedback)

        if not architecture_docs:
            architecture_docs = get_fallback_documentation(repo, files)

        return AgentResponse(
            status="success",
            agent_name=self.name,
            data={**context, "architecture_docs": architecture_docs},
            message=f"Successfully documented {len(architecture_docs)} files (1 LLM call, batch mode)",
        )