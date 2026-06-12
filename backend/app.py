import os
import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from agents.explorer import ExplorerAgent
from agents.documenter import DocumenterAgent
from agents.mentor import MentorAgent
from agents.reviewer import ReviewerAgent
from agents.task_suggester import TaskSuggesterAgent
from agents.session_manager import session_manager
from agents.mentor_qa import MentorQAHandler
from agents.handoff_log import handoff_log_manager
from agents.band_coordinator import band_coordinator

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    explorer = ExplorerAgent()
    documenter = DocumenterAgent()
    mentor = MentorAgent()
    reviewer = ReviewerAgent()
    task_suggester = TaskSuggesterAgent()

    await band_coordinator.start_remote_agents(
        explorer,
        documenter,
        mentor,
        reviewer,
        task_suggester
    )
    yield


app = FastAPI(
    title="REPOWISE Multi-Agent API",
    description="Backend for REPOWISE Multi-Agent System using Band framework",
    version="1.0.0",
    lifespan=lifespan,
)

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mentor_qa = MentorQAHandler()


@app.get("/")
async def root():
    return {
        "message": "REPOWISE API is running",
        "version": "1.0.0",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "analyze_websocket": "/ws/analyze",
            "analyze_rest": "POST /api/analyze",
            "session_status": "GET /api/session/{session_id}"
        }
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "api_keys_configured": {
            "github_token": bool(os.getenv("GITHUB_TOKEN")),
            "featherless_api_key": bool(os.getenv("FEATHERLESS_API_KEY")),
            "qwen_api_key": bool(os.getenv("QWEN_API_KEY")),
            "groq_api_key": bool(os.getenv("GROQ_API_KEY"))
        },
        "band": band_coordinator.get_status()
    }


@app.post("/api/analyze")
async def analyze_rest(request_data: dict):
    repo_url = request_data.get("repo_url")
    if not repo_url:
        raise HTTPException(status_code=400, detail="repo_url is required")

    try:
        explorer = ExplorerAgent()
        documenter = DocumenterAgent()
        mentor = MentorAgent()
        reviewer = ReviewerAgent()
        task_suggester = TaskSuggesterAgent()

        context = {"repo_url": repo_url}

        explorer_response = await explorer.process(context)
        if explorer_response.status == "error":
            raise HTTPException(status_code=400, detail=explorer_response.message)

        documenter_response = await documenter.process(explorer_response.data)
        if documenter_response.status == "error":
            raise HTTPException(status_code=400, detail=documenter_response.message)

        mentor_response = await mentor.process(documenter_response.data)
        reviewer_response = await reviewer.process(mentor_response.data)
        suggester_response = await task_suggester.process(reviewer_response.data)

        final_context = suggester_response.data

        return {
            "status": "success",
            "repository": f"{final_context.get('repository_owner')}/{final_context.get('repository_name')}",
            "total_files": final_context.get("total_files"),
            "result": {
                "architecture_docs": final_context.get("architecture_docs"),
                "onboarding_guide": final_context.get("onboarding_guide"),
                "code_review": final_context.get("review"),
                "quality_score": final_context.get("quality_score"),
                "quality_score_label": final_context.get("quality_score_label"),
                "suggested_tasks": final_context.get("suggested_tasks")
            },
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "status": "success",
        "data": session.to_dict(),
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/session/{session_id}/ask")
async def ask_mentor(session_id: str, request_data: dict):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    question = request_data.get("question")
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    try:
        session_manager.add_chat_message(session_id, "user", question)

        context = {
            "repository_name": session.repository,
            "architecture_docs": session.architecture_docs,
            "onboarding_guide": session.onboarding_guide,
            "code_review": session.code_review,
            "quality_score": session.quality_score,
            "quality_score_label": session.quality_score_label,
            "suggested_tasks": session.suggested_tasks
        }

        answer = await mentor_qa.chat(question, context, session.chat_history[:-1])
        session_manager.add_chat_message(session_id, "assistant", answer)

        return {
            "status": "success",
            "session_id": session_id,
            "question": question,
            "answer": answer,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions")
async def list_sessions():
    return {
        "status": "success",
        "sessions": session_manager.list_sessions(),
        "count": len(session_manager.sessions),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/session/{session_id}/handoff")
async def get_handoff_log(session_id: str):
    summary = handoff_log_manager.get_summary(session_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "status": "success",
        "data": summary,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/session/{session_id}/handoff/brief")
async def get_handoff_brief(session_id: str):
    summary = handoff_log_manager.get_brief_summary(session_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "status": "success",
        "data": summary,
        "timestamp": datetime.now().isoformat()
    }


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    if session_manager.delete_session(session_id):
        return {
            "status": "success",
            "message": f"Session {session_id} deleted",
            "timestamp": datetime.now().isoformat()
        }
    raise HTTPException(status_code=404, detail="Session not found")


@app.websocket("/ws/analyze")
async def websocket_analyze_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = None

    try:
        data = await websocket.receive_json()
        repo_url = data.get("repo_url")

        if not repo_url:
            await websocket.send_json({
                "status": "error",
                "message": "repo_url is required",
                "timestamp": datetime.now().isoformat()
            })
            return

        session_id = session_manager.create_session(repo_url)
        handoff_log_manager.create_log(session_id, repo_url)

        log_entries = []

        await websocket.send_json({
            "status": "started",
            "session_id": session_id,
            "repository": repo_url,
            "band_mode": band_coordinator.is_band_enabled,
            "timestamp": datetime.now().isoformat()
        })

        # ── Band mode: agents collaborate through Band chat room ──
        if band_coordinator.is_band_enabled:
            await _run_band_mode(websocket, session_id, repo_url, log_entries)
        else:
            # ── Local mode: sequential in-process pipeline ──
            await _run_local_mode(websocket, session_id, repo_url, log_entries)

    except WebSocketDisconnect:
        print(f"Client disconnected (session: {session_id})")
    except Exception as e:
        await websocket.send_json({
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        })
        print(f"WebSocket error: {str(e)}")


# ─── Band mode pipeline ───────────────────────────────────────────────
async def _run_band_mode(websocket, session_id: str, repo_url: str, log_entries: list):
    """Run analysis through Band — agents collaborate via chat room."""

    await websocket.send_json({
        "status": "processing",
        "agent": "Band",
        "step": "Band mode: Creating collaboration room, adding agents...",
        "band_mode": True,
        "timestamp": datetime.now().isoformat()
    })

    async def on_progress(event: dict):
        """Stream Band agent progress to frontend."""
        event_type = event.get("type", "")
        agent = event.get("agent", "Band")

        if event_type == "agent_start":
            await websocket.send_json({
                "status": "processing",
                "agent": agent,
                "step": event.get("message", f"{agent} processing..."),
                "band_mode": True,
                "timestamp": event.get("timestamp", datetime.now().isoformat())
            })
        elif event_type == "agent_done":
            log_entries.append({
                "agent": agent,
                "status": event.get("status", "success"),
                "message": event.get("message", ""),
                "band_mode": True,
                "timestamp": event.get("timestamp", datetime.now().isoformat())
            })
            await websocket.send_json({
                "status": "processing",
                "agent": agent,
                "step": event.get("message", f"{agent} done"),
                "data_summary": event.get("data_summary", {}),
                "band_mode": True,
                "timestamp": event.get("timestamp", datetime.now().isoformat())
            })
        elif event_type == "handoff":
            await websocket.send_json({
                "status": "processing",
                "agent": "Band",
                "step": event.get("message", ""),
                "band_mode": True,
                "timestamp": event.get("timestamp", datetime.now().isoformat())
            })
        elif event_type == "error":
            await websocket.send_json({
                "status": "error",
                "agent": agent,
                "message": event.get("message", "Unknown error"),
                "band_mode": True,
                "timestamp": event.get("timestamp", datetime.now().isoformat())
            })

    try:
        final_context = await band_coordinator.run_band_analysis(
            repo_url=repo_url,
            on_progress=on_progress,
            timeout=300.0,
        )

        session_manager.save_analysis_result(session_id, {
            "repository": f"{final_context.get('repository_owner')}/{final_context.get('repository_name')}",
            "total_files": final_context.get("total_files"),
            "architecture_docs": final_context.get("architecture_docs"),
            "onboarding_guide": final_context.get("onboarding_guide"),
            "code_review": final_context.get("review"),
            "quality_score": final_context.get("quality_score"),
            "quality_score_label": final_context.get("quality_score_label"),
            "suggested_tasks": final_context.get("suggested_tasks"),
            "band_room_id": final_context.get("band_room_id"),
            "band_mode": True,
            "handoff_log": log_entries
        })

        await websocket.send_json({
            "status": "completed",
            "session_id": session_id,
            "message": "All agents finished processing via Band.",
            "band_mode": True,
            "band_room_id": final_context.get("band_room_id"),
            "result": {
                "repository": f"{final_context.get('repository_owner')}/{final_context.get('repository_name')}",
                "total_files": final_context.get("total_files"),
                "architecture_docs": final_context.get("architecture_docs"),
                "onboarding_guide": final_context.get("onboarding_guide"),
                "code_review": final_context.get("review"),
                "quality_score": final_context.get("quality_score"),
                "quality_score_label": final_context.get("quality_score_label"),
                "suggested_tasks": final_context.get("suggested_tasks")
            },
            "handoff_log": log_entries,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logging.error(f"[BAND] Analysis failed: {e}")
        await websocket.send_json({
            "status": "error",
            "agent": "Band",
            "message": f"Band analysis failed: {str(e)}",
            "band_mode": True,
            "timestamp": datetime.now().isoformat()
        })


# ─── Local mode pipeline (fallback when Band is not available) ─────────
async def _run_local_mode(websocket, session_id: str, repo_url: str, log_entries: list):
    """Run analysis sequentially in-process — the original pipeline."""

    explorer = ExplorerAgent()
    documenter = DocumenterAgent()
    mentor = MentorAgent()
    reviewer = ReviewerAgent()
    task_suggester = TaskSuggesterAgent()

    # Helper to run one agent step
    async def _step(agent, agent_name: str, context: dict, ws_step: str):
        await websocket.send_json({
            "status": "processing", "agent": agent_name,
            "step": ws_step, "timestamp": datetime.now().isoformat()
        })
        resp = await agent.process(context)
        handoff_log_manager.log_handoff(
            session_id, source_agent=agent_name, target_agent=None,
            status=resp.status, message=resp.message,
            input_keys=list(context.keys()), output_keys=list(resp.data.keys())
        )
        log_entries.append({
            "agent": agent_name, "status": resp.status,
            "message": resp.message, "timestamp": datetime.now().isoformat()
        })
        if resp.status == "error":
            await websocket.send_json({
                "status": "error", "agent": agent_name,
                "message": resp.message, "timestamp": datetime.now().isoformat()
            })
            return None, None
        return resp.data, resp

    # 1. Explorer
    ctx, resp = await _step(explorer, "Explorer", {"repo_url": repo_url},
                            "Explorer: Scanning repository structure...")
    if ctx is None:
        return
    await websocket.send_json({
        "status": "processing", "agent": "Band",
        "step": f"Handoff: Passing {ctx.get('total_files', 0)} files to Documenter...",
        "timestamp": datetime.now().isoformat()
    })

    # 2. Documenter
    ctx, resp = await _step(documenter, "Documenter", ctx,
                            "Documenter: Reading code and generating documentation...")
    if ctx is None:
        return
    await websocket.send_json({
        "status": "processing", "agent": "Band",
        "step": "Handoff: Passing documentation to Mentor...",
        "timestamp": datetime.now().isoformat()
    })

    # 3. Mentor
    ctx, resp = await _step(mentor, "Mentor", ctx,
                            "Mentor: Generating onboarding guide...")
    if ctx is None:
        return
    await websocket.send_json({
        "status": "processing", "agent": "Band",
        "step": "Handoff: Passing onboarding guide to Reviewer...",
        "timestamp": datetime.now().isoformat()
    })

    # 4. Reviewer (with feedback loop)
    MAX_REVIEW_RETRIES = 2
    review_retry = 0
    while True:
        ctx, resp = await _step(reviewer, "Reviewer", ctx,
                                "Reviewer: Analyzing code quality..." if review_retry == 0
                                else f"Reviewer: Re-evaluating (attempt {review_retry + 1})...")
        if ctx is None:
            return

        score = ctx.get("quality_score", 100)

        # If score is too low and we haven't exceeded retries, request re-analysis
        if score < 50 and review_retry < MAX_REVIEW_RETRIES:
            review = ctx.get("review", {})
            issues = review.get("issues", [])
            recs = review.get("recommendations", [])

            # Build fully dynamic feedback from Reviewer's actual output
            feedback_parts = [f"Code quality score: {score}/100 ({ctx.get('quality_score_label', 'poor')})."]
            if issues:
                feedback_parts.append("Issues found:\n" + "\n".join(f"- {issue}" for issue in issues[:5]))
            if recs:
                feedback_parts.append("Required improvements:\n" + "\n".join(f"- {rec}" for rec in recs[:5]))
            feedback_parts.append("Re-analyze the codebase and address these exact issues in your documentation.")
            review_feedback = "\n\n".join(feedback_parts)

            await websocket.send_json({
                "status": "processing", "agent": "Reviewer",
                "step": f"Reviewer: Score {score}/100 — requesting deeper analysis...",
                "timestamp": datetime.now().isoformat()
            })

            # Re-run Documenter with reviewer feedback
            retry_ctx = dict(ctx)
            retry_ctx["reviewer_feedback"] = review_feedback
            ctx, resp = await _step(documenter, "Documenter", retry_ctx,
                                    f"Documenter: Re-analyzing based on review feedback...")
            if ctx is None:
                return

            await websocket.send_json({
                "status": "processing", "agent": "Band",
                "step": "Handoff: Updated documentation sent back to Reviewer...",
                "timestamp": datetime.now().isoformat()
            })
            review_retry += 1
            continue
        break

    await websocket.send_json({
        "status": "processing", "agent": "Band",
        "step": "Handoff: Passing review to Task Suggester...",
        "timestamp": datetime.now().isoformat()
    })

    # 5. Task Suggester
    ctx, resp = await _step(task_suggester, "Task_Suggester", ctx,
                            "Task Suggester: Generating good first issues for contributors...")
    if ctx is None:
        return

    final_context = ctx
    session_manager.save_analysis_result(session_id, {
        "repository": f"{final_context.get('repository_owner')}/{final_context.get('repository_name')}",
        "total_files": final_context.get("total_files"),
        "architecture_docs": final_context.get("architecture_docs"),
        "onboarding_guide": final_context.get("onboarding_guide"),
        "code_review": final_context.get("review"),
        "quality_score": final_context.get("quality_score"),
        "quality_score_label": final_context.get("quality_score_label"),
        "suggested_tasks": final_context.get("suggested_tasks"),
        "handoff_log": log_entries
    })

    await websocket.send_json({
        "status": "completed",
        "session_id": session_id,
        "message": "All agents finished processing.",
        "band_mode": False,
        "result": {
            "repository": f"{final_context.get('repository_owner')}/{final_context.get('repository_name')}",
            "total_files": final_context.get("total_files"),
            "architecture_docs": final_context.get("architecture_docs"),
            "onboarding_guide": final_context.get("onboarding_guide"),
            "code_review": final_context.get("review"),
            "quality_score": final_context.get("quality_score"),
            "quality_score_label": final_context.get("quality_score_label"),
            "suggested_tasks": final_context.get("suggested_tasks")
        },
        "handoff_log": log_entries,
        "timestamp": datetime.now().isoformat()
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)