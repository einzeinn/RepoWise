"""
Band SDK Integration for REPOWISE Multi-Agent Coordination.
Chain: explorer → documenter → mentor → reviewer → task-suggester

When Band is enabled, agents run as WebSocket daemons that collaborate
through Band chat rooms. Analysis is triggered via REST API and results
are streamed back via a progress queue.
"""

import os
import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Callable, Awaitable
from datetime import datetime

try:
    from thenvoi import Agent
    from thenvoi.core.simple_adapter import SimpleAdapter
    from thenvoi.core.protocols import AgentToolsProtocol
    from thenvoi.core.types import PlatformMessage
    from thenvoi.config import load_agent_config
    from thenvoi.client.rest import (
        AsyncRestClient,
        ChatMessageRequest,
        ChatMessageRequestMentionsItem,
        ChatRoomRequest,
        ParticipantRequest,
        DEFAULT_REQUEST_OPTIONS,
    )
    BAND_SDK_AVAILABLE = True
except ImportError:
    BAND_SDK_AVAILABLE = False
    SimpleAdapter = object
    AgentToolsProtocol = Any
    PlatformMessage = Any


# Production Band platform URL (SDK defaults to dev environment!)
BAND_REST_URL = "https://app.thenvoi.com"

# ─── Agent chain definition ───────────────────────────────────────────
AGENT_CHAIN: List[Dict[str, str]] = [
    {"key": "explorer",       "handle": "@quiiplle/explorer",       "label": "Explorer"},
    {"key": "documenter",     "handle": "@quiiplle/documenter",     "label": "Documenter"},
    {"key": "mentor",         "handle": "@quiiplle/mentor",         "label": "Mentor"},
    {"key": "reviewer",       "handle": "@quiiplle/reviewer",       "label": "Reviewer"},
    {"key": "task_suggester", "handle": "@quiiplle/task-suggester", "label": "Task Suggester"},
]


# ─── Adapter ──────────────────────────────────────────────────────────
class RepowiseNativeAdapter(SimpleAdapter):
    """Band adapter that wraps our local agents.

    Each agent processes incoming Band messages, runs its local logic,
    then sends results to the room and mentions the next agent in the chain.
    Progress events are pushed to a shared queue for frontend streaming.
    """

    def __init__(
        self,
        agent_name: str,
        local_agent_instance: Any,
        next_agent_handle: Optional[str],
        next_agent_id: Optional[str],
        shared_state: Dict[str, dict],
        progress_queues: Dict[str, asyncio.Queue],
    ):
        super().__init__(history_converter=None)
        self.agent_name = agent_name
        self.local_agent = local_agent_instance
        self.next_agent_handle = next_agent_handle
        self.next_agent_id = next_agent_id
        self.shared_state = shared_state
        self.progress_queues = progress_queues

    async def _push_progress(self, room_id: str, event: dict):
        """Push a progress event to the frontend queue for this room."""
        queue = self.progress_queues.get(room_id)
        if queue:
            event.setdefault("timestamp", datetime.now().isoformat())
            await queue.put(event)

    async def on_message(
        self,
        msg: PlatformMessage,
        tools: AgentToolsProtocol,
        history: Any,
        participants_msg: Optional[str] = None,
        contacts_msg: Optional[str] = None,
        *,
        is_session_bootstrap: bool = False,
        room_id: str = "",
    ) -> None:
        # Ignore bounce/error messages to prevent loops
        _BOUNCE_MARKERS = (
            "Session Memory Lost",
            "system error",
            "Memori Sesi Hilang",
            "mengalami kendala sistem",
        )
        if any(marker in msg.content for marker in _BOUNCE_MARKERS):
            logging.info(f"[BAND] {self.agent_name} ignoring bounce message.")
            return

        # Ignore messages from ourselves
        agent_key = self.agent_name.lower().replace(" ", "_")
        my_info = next((a for a in AGENT_CHAIN if a["key"] == agent_key), None)
        if my_info and msg.sender_name and my_info["label"].lower() in (msg.sender_name or "").lower():
            return

        logging.info(f"[BAND] {self.agent_name} received message from {msg.sender_name}")
        await self._push_progress(room_id, {
            "type": "agent_start",
            "agent": self.agent_name,
            "message": f"{self.agent_name} started processing...",
        })

        await tools.send_event(content=f"Analyzing request…", message_type="thought")

        current_state: dict = {}
        try:
            if room_id not in self.shared_state:
                self.shared_state[room_id] = {}
            current_state = self.shared_state[room_id]

            url_match = re.search(
                r"https?://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+", msg.content
            )
            if url_match:
                current_state.clear()
                current_state["repo_url"] = url_match.group(0)
                current_state["original_sender"] = msg.sender_name

            if not current_state:
                await tools.send_message(
                    content=(
                        "⚠️ **Session Memory Lost** — the server may have restarted "
                        "or no GitHub URL was detected.\n"
                        "Please resend the GitHub URL to restart the analysis pipeline."
                    ),
                    mentions=[msg.sender_name],
                )
                return

            result = await self.local_agent.process(current_state)
            status = getattr(result, "status", "unknown")
            if status == "success":
                current_state.update(getattr(result, "data", {}))

            # Build response message
            response_text = f"✅ **{self.agent_name}** finished processing.\n"

            if agent_key == "explorer":
                owner = current_state.get("repository_owner", "")
                name = current_state.get("repository_name", "")
                total = current_state.get("total_files", 0)
                if owner and name:
                    response_text += f"📦 Repository: `{owner}/{name}` ({total} files mapped)\n"

            elif agent_key == "reviewer":
                score = current_state.get("quality_score")
                label = current_state.get("quality_score_label", "")
                if score is not None:
                    response_text += f"🔍 Code quality score: **{score}/100** ({label})\n"

            message_info = getattr(result, "message", "")
            if message_info:
                response_text += f"📝 {message_info}\n"

            # Push progress to frontend queue
            await self._push_progress(room_id, {
                "type": "agent_done",
                "agent": self.agent_name,
                "status": status,
                "message": message_info,
                "data_summary": self._build_data_summary(agent_key, current_state),
            })

            # Routing: mention next agent or notify original sender
            mentions = []
            mention_items = []

            if status == "success" and self.next_agent_handle and self.next_agent_id:
                mentions.append(self.next_agent_handle)
                mention_items.append(
                    ChatMessageRequestMentionsItem(
                        id=self.next_agent_id,
                        handle=self.next_agent_handle,
                        name=self.next_agent_handle.lstrip("@"),
                    )
                )
                response_text += f"\nHanding off to {self.next_agent_handle}."
                await self._push_progress(room_id, {
                    "type": "handoff",
                    "from": self.agent_name,
                    "to": self.next_agent_handle,
                    "message": f"Handoff: {self.agent_name} → {self.next_agent_handle}",
                })
            else:
                original_human = current_state.get("original_sender", msg.sender_name)
                mentions.append(original_human)
                await self._push_progress(room_id, {
                    "type": "pipeline_complete",
                    "agent": self.agent_name,
                    "message": "Pipeline complete — all agents finished.",
                    "final_context_keys": list(current_state.keys()),
                })

            await tools.send_message(content=response_text, mentions=mentions)
            await tools.send_event(
                content="Success" if status == "success" else "Failed",
                message_type="tool_result",
                metadata={"is_error": status != "success"},
            )

        except Exception as e:
            error_msg = f"Infrastructure error in agent {self.agent_name}: {str(e)}"
            logging.error(f"[BAND] {error_msg}")
            original_human = current_state.get("original_sender", msg.sender_name)
            await tools.send_event(content=error_msg, message_type="error")
            await tools.send_message(
                content=f"Sorry, I encountered a system error: {str(e)}",
                mentions=[original_human],
            )
            await self._push_progress(room_id, {
                "type": "error",
                "agent": self.agent_name,
                "message": error_msg,
            })

    @staticmethod
    def _build_data_summary(agent_key: str, state: dict) -> dict:
        """Build a lightweight summary of agent output for the frontend."""
        if agent_key == "explorer":
            return {
                "repository": f"{state.get('repository_owner', '')}/{state.get('repository_name', '')}",
                "total_files": state.get("total_files", 0),
            }
        elif agent_key == "documenter":
            docs = state.get("architecture_docs", {})
            return {"files_documented": len(docs)}
        elif agent_key == "mentor":
            guide = state.get("onboarding_guide", "")
            return {"guide_length": len(guide)}
        elif agent_key == "reviewer":
            return {
                "quality_score": state.get("quality_score", 0),
                "quality_score_label": state.get("quality_score_label", ""),
            }
        elif agent_key == "task_suggester":
            tasks = state.get("suggested_tasks", "")
            return {"tasks_generated": len(tasks) > 0}
        return {}


# ─── Band Coordinator ─────────────────────────────────────────────────
class BandCoordinator:
    def __init__(self):
        self.config: Dict[str, Dict[str, str]] = {}
        self.active_tasks: list = []
        self.room_states: Dict[str, dict] = {}
        self.progress_queues: Dict[str, asyncio.Queue] = {}
        self.is_band_enabled = False
        self._agents_started = False

        self._load_config()

    def _load_config(self):
        if not BAND_SDK_AVAILABLE:
            logging.warning("[BAND FALLBACK] 'band-sdk' not found. Running in local mode.")
            return

        # Find agent_config.yaml
        current_dir = os.path.dirname(os.path.abspath(__file__))
        backend_dir = os.path.dirname(current_dir)
        root_dir = os.path.dirname(backend_dir)

        possible_paths = [
            os.path.join(root_dir, "agent_config.yaml"),
            os.path.join(backend_dir, "agent_config.yaml"),
            os.path.join(os.getcwd(), "agent_config.yaml"),
        ]

        config_path = None
        for path in possible_paths:
            if os.path.exists(path):
                config_path = path
                break

        if not config_path:
            logging.warning("[BAND FALLBACK] agent_config.yaml not found.")
            return

        # Load all agent configs
        import yaml
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
            if raw:
                for agent_key in AGENT_CHAIN:
                    key = agent_key["key"]
                    if key in raw:
                        self.config[key] = raw[key]

                if len(self.config) >= 3:  # At least 3 agents configured
                    self.is_band_enabled = True
                    logging.info(
                        f"[BAND] Config loaded: {len(self.config)} agents from {config_path}"
                    )
                else:
                    logging.warning(
                        f"[BAND FALLBACK] Only {len(self.config)} agents configured (need ≥3)."
                    )
        except Exception as e:
            logging.error(f"[BAND FALLBACK] Failed to read config: {e}")

    async def start_remote_agents(
        self,
        explorer_agent,
        documenter_agent,
        mentor_agent,
        reviewer_agent,
        task_suggester_agent,
    ):
        """Spin up all Band remote agents as long-lived WebSocket daemons."""
        if not self.is_band_enabled:
            logging.warning("[BAND] Skipping remote agent startup — Band not enabled.")
            return

        local_agents = {
            "explorer": explorer_agent,
            "documenter": documenter_agent,
            "mentor": mentor_agent,
            "reviewer": reviewer_agent,
            "task_suggester": task_suggester_agent,
        }

        for i, agent_info in enumerate(AGENT_CHAIN):
            key = agent_info["key"]
            if key not in self.config:
                logging.warning(f"[BAND] '{key}' not in config — skipping.")
                continue

            creds = self.config[key]
            if not creds or "agent_id" not in creds or "api_key" not in creds:
                logging.warning(f"[BAND] '{key}' has incomplete credentials — skipping.")
                continue

            # Determine next agent in chain
            next_handle = None
            next_id = None
            if i + 1 < len(AGENT_CHAIN):
                next_key = AGENT_CHAIN[i + 1]["key"]
                if next_key in self.config:
                    next_handle = AGENT_CHAIN[i + 1]["handle"]
                    next_id = self.config[next_key]["agent_id"]

            adapter = RepowiseNativeAdapter(
                agent_name=agent_info["label"],
                local_agent_instance=local_agents[key],
                next_agent_handle=next_handle,
                next_agent_id=next_id,
                shared_state=self.room_states,
                progress_queues=self.progress_queues,
            )

            agent = Agent.create(
                adapter=adapter,
                agent_id=creds["agent_id"],
                api_key=creds["api_key"],
            )

            task = asyncio.create_task(agent.run())
            self.active_tasks.append(task)
            logging.info(f"[BAND] Remote agent connected: {key} ({creds['agent_id'][:8]}...)")

        self._agents_started = True
        logging.info(f"[BAND] {len(self.active_tasks)} agents started as WebSocket daemons.")

    # ─── Band-mode analysis ───────────────────────────────────────────

    async def run_band_analysis(
        self,
        repo_url: str,
        on_progress: Callable[[dict], Awaitable[None]],
        timeout: float = 300.0,
    ) -> dict:
        """Trigger a full analysis pipeline through Band.

        1. Create a chat room
        2. Add all agents as participants
        3. Send initial message mentioning Explorer
        4. Listen for progress events from the adapter
        5. Return final results when pipeline completes

        Args:
            repo_url: GitHub repository URL
            on_progress: Async callback for streaming progress to frontend
            timeout: Max seconds to wait for completion
        """
        if not self.is_band_enabled:
            raise RuntimeError("Band is not enabled. Install band-sdk and configure agent_config.yaml.")

        # Get the first agent's REST client for room management
        # IMPORTANT: Must set base_url — SDK defaults to dev environment!
        explorer_creds = self.config.get("explorer", {})
        explorer_id = explorer_creds["agent_id"]
        rest_client = AsyncRestClient(
            api_key=explorer_creds["api_key"],
            base_url=BAND_REST_URL,
        )

        # 1. Create chat room
        logging.info("[BAND] Creating analysis chat room...")
        try:
            room_resp = await rest_client.agent_api_chats.create_agent_chat(
                chat=ChatRoomRequest(),
                request_options=DEFAULT_REQUEST_OPTIONS,
            )
        except Exception as e:
            logging.error(f"[BAND] Failed to create chat room: {e}")
            raise

        # Extract room ID from response wrapper (.data)
        room_data = room_resp.data if hasattr(room_resp, 'data') else room_resp
        room_id = room_data.id if hasattr(room_data, 'id') else str(room_data)
        logging.info(f"[BAND] Room created: {room_id}")

        # Register progress queue for this room
        self.progress_queues[room_id] = asyncio.Queue()

        # 2. Add all other agents as participants
        for agent_info in AGENT_CHAIN[1:]:  # Skip explorer (room owner)
            key = agent_info["key"]
            if key not in self.config:
                continue
            try:
                await rest_client.agent_api_participants.add_agent_chat_participant(
                    chat_id=room_id,
                    participant=ParticipantRequest(
                        participant_id=self.config[key]["agent_id"],
                    ),
                    request_options=DEFAULT_REQUEST_OPTIONS,
                )
                logging.info(f"[BAND] Added {key} to room {room_id}")
            except Exception as e:
                logging.warning(f"[BAND] Failed to add {key}: {e}")

        # Small delay to let agents register in the room
        await asyncio.sleep(2)

        # 3. Send initial message mentioning Explorer
        # IMPORTANT: Cannot use Explorer's own key to mention itself (platform rejects self-mention).
        # Use the last agent's key to send the initial message.
        sender_key = AGENT_CHAIN[-1]["key"]
        sender_creds = self.config.get(sender_key, explorer_creds)
        sender_client = AsyncRestClient(
            api_key=sender_creds["api_key"],
            base_url=BAND_REST_URL,
        )
        explorer_handle = AGENT_CHAIN[0]["handle"]

        initial_content = (
            f"{explorer_handle} Please analyze this repository: {repo_url}\n\n"
            f"Map the file structure, identify key modules, and prepare the codebase "
            f"for documentation and review."
        )

        try:
            await sender_client.agent_api_messages.create_agent_chat_message(
                chat_id=room_id,
                message=ChatMessageRequest(
                    content=initial_content,
                    mentions=[
                        ChatMessageRequestMentionsItem(
                            id=explorer_id,
                            handle=explorer_handle,
                            name="Explorer",
                        )
                    ],
                ),
                request_options=DEFAULT_REQUEST_OPTIONS,
            )
        except Exception as e:
            logging.error(f"[BAND] Failed to send initial message: {e}")
            raise
        logging.info(f"[BAND] Initial message sent to room {room_id}, mentioning Explorer.")

        # 4. Listen for progress events
        completed_agents = set()
        final_context = {}
        start_time = asyncio.get_event_loop().time()

        while len(completed_agents) < len(AGENT_CHAIN):
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                logging.warning(f"[BAND] Analysis timed out after {timeout}s")
                break

            try:
                event = await asyncio.wait_for(
                    self.progress_queues[room_id].get(),
                    timeout=60.0,  # 60s between events max
                )
            except asyncio.TimeoutError:
                logging.warning("[BAND] No progress event for 60s, checking status...")
                continue

            # Forward event to frontend
            await on_progress(event)

            # Track completion
            if event.get("type") == "agent_done":
                agent = event.get("agent", "")
                completed_agents.add(agent)
                logging.info(f"[BAND] Agent done: {agent} ({len(completed_agents)}/{len(AGENT_CHAIN)})")

            elif event.get("type") == "pipeline_complete":
                break

            elif event.get("type") == "error":
                logging.error(f"[BAND] Agent error: {event.get('message')}")
                break

        # 5. Collect final results from shared state
        room_state = self.room_states.get(room_id, {})
        final_context = {
            "repository_owner": room_state.get("repository_owner"),
            "repository_name": room_state.get("repository_name"),
            "total_files": room_state.get("total_files"),
            "architecture_docs": room_state.get("architecture_docs"),
            "onboarding_guide": room_state.get("onboarding_guide"),
            "review": room_state.get("review"),
            "quality_score": room_state.get("quality_score"),
            "quality_score_label": room_state.get("quality_score_label"),
            "suggested_tasks": room_state.get("suggested_tasks"),
            "band_room_id": room_id,
            "band_mode": True,
        }

        # Cleanup
        self.progress_queues.pop(room_id, None)

        return final_context

    # ─── Helpers ──────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        return {
            "band_enabled": self.is_band_enabled,
            "sdk_available": BAND_SDK_AVAILABLE,
            "status": "ready" if self.is_band_enabled else "fallback_mode",
            "active_daemons": len(self.active_tasks),
            "agents_configured": list(self.config.keys()),
            "chain": " → ".join([a["label"] for a in AGENT_CHAIN]),
        }


band_coordinator = BandCoordinator()
