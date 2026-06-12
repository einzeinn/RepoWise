# REPOWISE Development Guidelines

## Architecture

### Backend (FastAPI)
- **Framework**: FastAPI with async support
- **Language**: Python 3.10+
- **Package Manager**: pip with virtual environment
- **Structure**:
  - `app.py` — Main FastAPI application
  - `agents/` — Multi-agent system implementations
  - `requirements.txt` — Python dependencies

### Frontend (Next.js)
- **Framework**: Next.js 14 with App Router
- **Language**: TypeScript
- **Package Manager**: npm
- **Styling**: Tailwind CSS
- **Structure**:
  - `app/` — Next.js app router
  - `components/` — Reusable React components
  - `lib/` — Utilities and helpers
  - `public/` — Static assets

## Development Workflow

### 1. Initial Setup

**Windows:**
```bash
setup.bat
```

**macOS/Linux:**
```bash
chmod +x setup.sh
./setup.sh
```

### 2. Environment Configuration

Copy `.env.example` to `.env` and configure:
```env
GITHUB_TOKEN=your_token_here
FEATHERLESS_API_KEY=your_key_here
QWEN_API_KEY=your_key_here
BAND_EXPLORER_ID=your_agent_id
```

### 3. Run Backend

```bash
cd backend

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

python app.py
```

Backend: `http://localhost:8000`
Docs: `http://localhost:8000/docs`

### 4. Run Frontend

```bash
cd frontend
npm run dev
```

Frontend: `http://localhost:3000`

### 5. Docker Compose (Optional)

```bash
docker-compose up
```

## Code Standards

### Python
- Use `black` for formatting (line length: 100)
- Type hints required for all functions
- Async/await for I/O operations
- Docstrings for classes and methods

### TypeScript/JavaScript
- Use TypeScript for type safety
- ESLint configuration for linting
- Functional components with hooks
- Props typed with interfaces

## File Organization

### Backend Agents
Each agent should implement:
- Initialization with context setting
- Async processing methods
- Clear responsibility separation
- Type hints for all parameters

```python
class Agent:
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process data and return results"""
        pass
```

### Frontend Components
- One component per file
- Named exports
- Clear prop interfaces
- Accessibility considerations

```typescript
interface ComponentProps {
  prop1: string;
  onAction?: () => void;
}

export function Component({ prop1, onAction }: ComponentProps) {
  return <div>{prop1}</div>;
}
```

## Testing

### Backend
```bash
cd backend
pytest
```

### Frontend
```bash
cd frontend
npm test
```

## API Communication

Frontend → Backend uses:
- **Base URL**: `NEXT_PUBLIC_API_URL` (default: `http://localhost:8000`)
- **Headers**: `Content-Type: application/json`
- **CORS**: Configured in FastAPI

Example:
```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const response = await fetch(`${API_URL}/analyze`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ repo_url: 'https://github.com/owner/repo' })
});
```

## Agent Workflow

1. **Explorer** → Scans repo, creates file tree
2. **Band Handoff** → Pass context to Documenter
3. **Documenter** → Analyzes modules, generates docs
4. **Band Handoff** → Pass context to Mentor & Task Suggester
5. **Mentor** → Ready for Q&A
6. **Task Suggester** → Generate entry points

## Deployment

### Backend (Railway)
```bash
railway up
```

### Frontend (Vercel)
```bash
vercel deploy
```

## Debugging

### Backend
- Check `http://localhost:8000/docs` for API docs
- FastAPI auto-generates interactive Swagger UI
- Enable `DEBUG=True` in `.env`

### Frontend
- Use React Developer Tools browser extension
- DevTools → Components tab for component tree
- Check Console for errors

## Common Issues

### "Module not found" Python
- Ensure venv is activated
- Run `pip install -r requirements.txt`

### "Cannot find module" TypeScript
- Run `npm install`
- Check paths in `tsconfig.json`

### CORS errors
- Check `NEXT_PUBLIC_API_URL` configuration
- Verify backend CORS settings in `app.py`

## Resources

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Next.js Docs](https://nextjs.org/docs)
- [Tailwind CSS](https://tailwindcss.com/)
- [LangChain Python](https://python.langchain.com/)
