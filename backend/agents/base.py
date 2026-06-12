import os
import re
import httpx
import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel
from dotenv import load_dotenv

_base_dir = os.path.dirname(os.path.abspath(__file__))
_env_path = os.path.join(_base_dir, "..", ".env")
if os.path.exists(_env_path):
    load_dotenv(dotenv_path=_env_path)

# Keep semaphore at 1 — reduce sleep to avoid rate limit bursts
global_llm_semaphore = asyncio.Semaphore(1)

class AgentResponse(BaseModel):
    status: str
    agent_name: str
    data: Dict[str, Any]
    message: str

class BaseAgent(ABC):
    def __init__(self, name: str):
        self.name = name

        raw_groq = os.getenv("GROQ_API_KEY", "")
        self.groq_api_key = raw_groq if raw_groq and "your_" not in raw_groq and "_here" not in raw_groq else None

        raw_featherless = os.getenv("FEATHERLESS_API_KEY", "")
        self.featherless_api_key = raw_featherless if raw_featherless and "your_" not in raw_featherless and "_here" not in raw_featherless else None

        raw_qwen = os.getenv("QWEN_API_KEY", "")
        self.qwen_api_key = raw_qwen if raw_qwen and "your_" not in raw_qwen and "_here" not in raw_qwen else None

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 300,
        temperature: float = 0.4
    ) -> Optional[str]:
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
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }

                for attempt in range(3):
                    try:
                        logging.info(f"[{self.name}] Featherless call attempt {attempt + 1}/3")
                        async with httpx.AsyncClient(timeout=60.0) as client:
                            resp = await client.post(url, headers=headers, json=payload)

                        if resp.status_code == 200:
                            answer = resp.json()["choices"][0]["message"]["content"].strip()
                            logging.info(f"[{self.name}] Featherless OK")
                            return answer

                        elif resp.status_code == 429:
                            if self.qwen_api_key or self.groq_api_key:
                                logging.warning(f"[{self.name}] Featherless 429 — switching to fallback.")
                                break

                            retry_after = 8.0 * (attempt + 1)
                            try:
                                msg = resp.json().get("error", {}).get("message", "")
                                m = re.search(r"try again in (\d+\.?\d*)s", msg)
                                if m:
                                    retry_after = float(m.group(1)) + 0.5
                            except Exception:
                                pass
                            logging.warning(f"[{self.name}] Featherless 429 — waiting {retry_after:.1f}s")
                            await asyncio.sleep(retry_after)

                        else:
                            logging.error(f"[{self.name}] Featherless {resp.status_code}: {resp.text[:200]}")
                            break

                    except Exception as e:
                        logging.error(f"[{self.name}] Featherless exception: {e}")
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
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }

                for attempt in range(2):
                    try:
                        logging.info(f"[{self.name}] Qwen call attempt {attempt + 1}/2")
                        async with httpx.AsyncClient(timeout=60.0) as client:
                            resp = await client.post(url, headers=headers, json=payload)

                        if resp.status_code == 200:
                            answer = resp.json()["choices"][0]["message"]["content"].strip()
                            logging.info(f"[{self.name}] Qwen OK")
                            return answer

                        elif resp.status_code == 429:
                            if self.groq_api_key:
                                logging.warning(f"[{self.name}] Qwen 429 — switching to Groq fallback.")
                                break
                            retry_after = 5.0 * (attempt + 1)
                            logging.warning(f"[{self.name}] Qwen 429 — waiting {retry_after:.1f}s")
                            await asyncio.sleep(retry_after)

                        else:
                            logging.error(f"[{self.name}] Qwen {resp.status_code}: {resp.text[:200]}")
                            break

                    except Exception as e:
                        logging.error(f"[{self.name}] Qwen exception: {e}")
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
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }
                try:
                    logging.info(f"[{self.name}] Groq fallback call...")
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        answer = resp.json()["choices"][0]["message"]["content"].strip()
                        logging.info(f"[{self.name}] Groq OK")
                        return answer
                    else:
                        logging.error(f"[{self.name}] Groq {resp.status_code}: {resp.text[:200]}")
                except Exception as e:
                    logging.error(f"[{self.name}] Groq exception: {e}")

            logging.warning(f"[{self.name}] All LLM providers failed.")
            return None

    @abstractmethod
    async def process(self, context: Dict[str, Any]) -> AgentResponse:
        pass