# REPOWISE — Multi-Agent Repository Explorer

A powerful multi-agent system that automatically analyzes GitHub repositories, generating intelligent documentation, onboarding guides, and task recommendations for developers exploring new codebases.

**Built for**: Band of Agents Hackathon — Track 2: Multi-Agent Software Development
**Tech**: FastAPI • Next.js 14 • Band SDK • Qwen (Featherless AI)

---

## 🎯 Features

- 🔍 **Automated Repository Analysis** — Explorer agent scans repository structure and identifies key files
- 📚 **Intelligent Documentation** — Documenter agent generates technical summaries of code modules
- 🎓 **Onboarding Guides** — Mentor agent creates beginner-friendly guides for new contributors
- 🔎 **Code Quality Review** — Reviewer agent inspects code with structured scoring and recommendations
- ✅ **Task Suggestions** — Task Suggester recommends entry points for first-time contributors
- 💬 **Interactive Q&A** — Ask contextual questions about the analyzed codebase
- 🔄 **Real-time Progress** — WebSocket streaming shows agent handoff progress in real-time
- 💾 **Session Management** — Store and retrieve analysis results for later reference
- ⚡ **Fallback Mode** — Works without API keys using fallback documentation
- 📊 **Handoff Logging** — Full historical tracking of agent-to-agent handoffs

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+** (Backend)
- **Node.js 18+** (Frontend)
- **Git**
- Optional: GitHub Token, LLM API key

### Windows Setup
```bash
git clone https://github.com/einzeinn/RepoWise.git
cd RepoWise
setup.bat
start-dev.bat
```

### macOS/Linux Setup
```bash
git clone https://github.com/einzeinn/RepoWise.git
cd RepoWise
chmod +x setup.sh
./setup.sh
./start-dev.sh
```

**Services will start on:**
- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000` (API docs: `/docs`)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      REPOWISE System Architecture                │
└─────────────────────────────────────────────────────────────────┘

Frontend (Next.js 14)  ←→  WebSocket + REST
┌───────────────────────────────────────────────────────┐
│                  FastAPI Backend (Python)               │
├───────────────────────────────────────────────────────┤
│  SessionManager │ HandoffLog │ MentorQ&A │ BandCoord  │
├───────────────────────────────────────────────────────┤
│ ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│ │ Explorer │→ │Documenter│→ │ Reviewer │              │
│ │ (Scan)   │  │(Analyze) │  │ (Score)  │              │
│ └──────────┘  └──────────┘  └────┬─────┘              │
│                                   ↓                    │
│                             ┌──────────┐  ┌──────────┐│
│                             │ Mentor   │→ │TaskSuggest││
│                             │ (Guide)  │  │ (Tasks)   ││
│                             └──────────┘  └──────────┘│
├───────────────────────────────────────────────────────┤
│  GitHub API  │  Featherless AI (Qwen2.5-Coder-32B)    │
│              │  Qwen DashScope  │  Groq (fallback)     │
└───────────────────────────────────────────────────────┘
```

---

## 📖 API Documentation

### REST Endpoints

#### GET `/`
Root endpoint with service info
```json
{
  "message": "REPOWISE API is running",
  "version": "1.0.0",
  "endpoints": {...}
}
```

#### GET `/health`
Health check with configuration status
```json
{
  "status": "healthy",
  "api_keys_configured": {
    "github_token": false,
    "featherless_api_key": false
  }
}
```

#### POST `/api/analyze`
Synchronous repository analysis
```json
REQUEST:
{
  "repo_url": "https://github.com/facebook/react"
}

RESPONSE:
{
  "status": "success",
  "repository": "facebook/react",
  "total_files": 2843,
  "result": {
    "architecture_docs": {...},
    "onboarding_guide": "...",
    "suggested_tasks": "..."
  }
}
```

#### GET `/api/session/{session_id}`
Retrieve session analysis results
```json
{
  "status": "success",
  "data": {
    "session_id": "uuid",
    "repository": "owner/repo",
    "architecture_docs": {...},
    "onboarding_guide": "...",
    "suggested_tasks": "..."
  }
}
```

#### POST `/api/session/{session_id}/ask`
Q&A with Mentor agent
```json
REQUEST:
{
  "question": "How should I set up the development environment?"
}

RESPONSE:
{
  "status": "success",
  "question": "How should I...",
  "answer": "To get started..."
}
```

#### GET `/api/session/{session_id}/handoff`
Full handoff log with all agent interactions
```json
{
  "session_id": "uuid",
  "status": "completed",
  "progress": "4/4",
  "entries": [
    {
      "timestamp": "2026-06-03T10:30:15",
      "source_agent": "Explorer",
      "target_agent": "Documenter",
      "status": "success",
      "message": "Found 2,843 files"
    }
  ]
}
```

#### GET `/api/session/{session_id}/handoff/brief`
Summary of agent handoffs
```json
{
  "session_id": "uuid",
  "status": "completed",
  "progress": "4/4",
  "summary": [...]
}
```

#### GET `/api/sessions`
List all active sessions
```json
{
  "status": "success",
  "sessions": [...],
  "count": 5
}
```

#### DELETE `/api/session/{session_id}`
Delete a session

### WebSocket Endpoint

#### WS `/ws/analyze`
Real-time streaming of analysis progress

**Connect and send:**
```javascript
const ws = new WebSocket("ws://localhost:8000/ws/analyze");
ws.send(JSON.stringify({
  repo_url: "https://github.com/facebook/react"
}));
```

**Receive messages:**
```json
{"status": "started", "session_id": "uuid", "repository": "url"}
{"status": "processing", "agent": "Explorer", "step": "Scanning repository..."}
{"status": "processing", "agent": "Documenter", "step": "Analyzing code..."}
{"status": "completed", "result": {...}}
```

---

## 📁 Project Structure

```
repowise/
├── backend/
│   ├── app.py                      # FastAPI application & endpoints
│   ├── agents/
│   │   ├── base.py                # Abstract base agent
│   │   ├── band_coordinator.py    # Band SDK coordination
│   │   ├── explorer.py            # Repository scanner
│   │   ├── documenter.py          # Code analyzer
│   │   ├── mentor.py              # Onboarding guide generator
│   │   ├── reviewer.py            # Code quality reviewer
│   │   ├── task_suggester.py      # Entry point suggester
│   │   ├── mentor_qa.py           # Q&A handler
│   │   ├── session_manager.py     # Session state
│   │   ├── handoff_log.py         # Handoff tracking
│   │   └── fallback_responses.py  # No-API-key fallbacks
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx              # Home page
│   │   ├── layout.tsx            # Root layout
│   │   └── globals.css           # Tailwind styles
│   ├── package.json
│   └── Dockerfile
│
├── agent_config.yaml.example      # Band agent credentials template
├── docker-compose.yml
├── DEVELOPMENT.md                 # Development guide
├── README.md                      # This file
├── LICENSE                        # MIT License
└── setup.sh / setup.bat          # Setup scripts
```

---

## 🔧 Configuration

### Environment Variables

Create `.env` file in root (see `.env.example` for reference):

```env
# GitHub API Token (optional, increases rate limits)
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx

# LLM API Keys (optional, fallback mode activates automatically)
FEATHERLESS_API_KEY=your_featherless_key
QWEN_API_KEY=your_qwen_key
GROQ_API_KEY=your_groq_key

# Band Agent IDs (required for multi-agent coordination via Band)
BAND_EXPLORER_ID=your_agent_id
BAND_DOCUMENTER_ID=your_agent_id
BAND_MENTOR_ID=your_agent_id
BAND_REVIEWER_ID=your_agent_id
BAND_TASK_SUGGESTER_ID=your_agent_id
```

> **No API keys?** The system gracefully falls back to hardcoded documentation!

---

## 🤖 Agent System

Each agent is a specialized worker in the analysis pipeline:

| Agent | Responsibility | Input | Output |
|-------|---|---|---|
| **Explorer** | Scan repository structure | `repo_url` | `file_tree`, architecture insights |
| **Documenter** | Analyze source code | `file_tree` | `architecture_docs` with summaries |
| **Reviewer** | Inspect code quality | `architecture_docs` | `review` (strengths/issues/recs), `quality_score` |
| **Mentor** | Create learning guide | `architecture_docs` | `onboarding_guide` for new devs |
| **Task Suggester** | Recommend tasks | `architecture_docs`, `review` | `suggested_tasks` for contributors |
| **Mentor Q&A** | Answer questions | `architecture_docs`, `chat_history` | contextual answers |

---

## 📊 Handoff Log Format

Every agent-to-agent transfer is logged:

```json
{
  "timestamp": "2026-06-03T10:30:15",
  "source_agent": "Explorer",
  "target_agent": "Documenter",
  "status": "success",
  "message": "Found 2,843 files",
  "input_keys": ["repo_url"],
  "output_keys": ["file_tree", "total_files"]
}
```

Access full history via `GET /api/session/{session_id}/handoff`

---

## 👨‍💻 Development

### Run Backend Only
```bash
cd backend
python -m venv venv
# Activate venv (Windows: venv\Scripts\activate)
pip install -r requirements.txt
python -m uvicorn app:app --reload
```

### Run Frontend Only
```bash
cd frontend
npm install
npm run dev
```

### API Documentation
Open browser: `http://localhost:8000/docs` (interactive Swagger UI)

### Running Tests
```bash
pip install pytest pytest-asyncio
pytest backend/
```

---

## 🤝 Contributing

1. **Fork** the repository
2. **Create feature branch**: `git checkout -b feature/amazing-feature`
3. **Make changes** with clear commits
4. **Push to branch**: `git push origin feature/amazing-feature`
5. **Open Pull Request**

### Good First Issues
- [ ] Add unit tests for agents
- [ ] Improve error handling
- [ ] Add support for more programming languages
- [ ] Create deployment guide
- [ ] Enhance README with examples

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| "repo_url is required" | Send proper JSON body with `repo_url` field |
| API key errors | Fallback mode activates automatically |
| Frontend can't connect | Check backend running on `http://localhost:8000` |
| Rate limit errors | Add GitHub token to `.env` for higher limits |

---

## 📚 Documentation

- [DEVELOPMENT.md](DEVELOPMENT.md) — Detailed development guide

---

## 📄 License

MIT License — See [LICENSE](LICENSE) file

This project is built for the **Band of Agents Hackathon** (Deadline: June 19, 2026)

---

**Made with ❤️ for the open-source community**
