"""
Fallback responses untuk demo mode tanpa LLM/API key.
Digunakan ketika FEATHERLESS_API_KEY tidak tersedia.
"""

from typing import Dict, Any

# Pola deteksi repo berdasarkan nama file
FILE_PATTERNS = {
    'app.py': 'FastAPI/Python application entry point',
    'main.py': 'Python application entry point',
    'package.json': 'Node.js/JavaScript project manifest',
    'go.mod': 'Go module definition',
    'requirements.txt': 'Python dependencies list',
    'Dockerfile': 'Container configuration',
    'docker-compose.yml': 'Multi-container orchestration',
    'README.md': 'Project documentation',
    'Makefile': 'Build automation',
}

FALLBACK_DOCS_TEMPLATE = {
    'backend_python': {
        'app.py': 'FastAPI application initialization. Handles HTTP routing, CORS configuration, and WebSocket connections for the multi-agent system.',
        'agents/explorer.py': 'Explorer Agent implementation. Fetches GitHub repository structure, extracts file tree, and identifies key files for analysis.',
        'agents/documenter.py': 'Documenter Agent. Reads source code from important files and generates technical summaries.',
        'agents/mentor.py': 'Mentor Agent. Creates onboarding guides based on architecture documentation.',
        'agents/base.py': 'Abstract base class for all agents. Defines standard response format and interface.',
    },
    'frontend_nextjs': {
        'page.tsx': 'Main landing page component for REPOWISE interface.',
        'layout.tsx': 'Root layout wrapper with navigation and global state.',
        'globals.css': 'Global Tailwind CSS styles and theme configuration.',
        'package.json': 'Frontend dependencies (Next.js, React, Zustand, Axios).',
    },
    'generic_python': {
        'main.py': 'Application entry point. Core business logic initialization.',
        'config.py': 'Configuration management and environment variables.',
        'utils.py': 'Utility functions and helpers.',
        'models.py': 'Data models and schemas.',
        'routes.py': 'HTTP route definitions.',
    }
}

def get_fallback_documentation(repo_name: str, files: list) -> Dict[str, str]:
    """
    Generate fallback documentation based on detected repo type.
    
    Args:
        repo_name: Repository name
        files: List of file paths
        
    Returns:
        Dictionary mapping file paths to documentation
    """
    docs = {}
    
    # Detect repo type
    file_names = {f.get('path', f.get('name', '')).split('/')[-1] for f in files}
    
    if 'app.py' in file_names or 'fastapi' in repo_name.lower():
        template = FALLBACK_DOCS_TEMPLATE['backend_python']
    elif 'package.json' in file_names and 'next.config.js' in file_names:
        template = FALLBACK_DOCS_TEMPLATE['frontend_nextjs']
    elif 'package.json' in file_names:
        template = FALLBACK_DOCS_TEMPLATE['generic_python']
    else:
        template = FALLBACK_DOCS_TEMPLATE['generic_python']
    
    # Match files with template
    for file_info in files[:10]:
        file_path = file_info.get('path', file_info.get('name', ''))
        filename = file_path.split('/')[-1]
        
        # Try exact match first
        if file_path in template:
            docs[file_path] = template[file_path]
        elif filename in template:
            docs[file_path] = template[filename]
        else:
            # Generic documentation for unmatched files
            ext = '.' + filename.split('.')[-1] if '.' in filename else ''
            if ext in {'.py', '.js', '.ts', '.tsx'}:
                docs[file_path] = f"Module: {filename}. Implements specific functionality for the {repo_name} project."
    
    return docs


def get_fallback_onboarding(repo_name: str, architecture_docs: dict) -> str:
    """Generate fallback onboarding guide."""
    
    if 'fastapi' in repo_name.lower() or 'app.py' in str(architecture_docs):
        return f"""## Getting Started with {repo_name}

This is a backend project built with FastAPI. To get started:

1. **Understand the Architecture**: The system uses a multi-agent pattern with specialized components handling different concerns.

2. **Key Entry Points**:
   - `app.py`: Start here to understand the HTTP API structure and WebSocket handling
   - `agents/`: Each agent handles a specific responsibility in the analysis pipeline

3. **Development Workflow**:
   - Install dependencies from `requirements.txt`
   - Create a `.env` file with necessary API keys
   - Run the FastAPI server with `uvicorn app:app --reload`
   - Check `/docs` endpoint for interactive API documentation"""
    
    else:
        return f"""## Getting Started with {repo_name}

1. **Installation**: Check README.md and requirements/dependencies files

2. **Project Structure**: 
   - Source code is organized by feature/functionality
   - Configuration is typically in root or `config/` directory

3. **Running the Project**:
   - Install dependencies
   - Follow setup instructions in README
   - Check for environment configuration examples"""


def get_fallback_suggested_tasks() -> str:
    """Generate fallback suggested tasks for contributors."""
    
    return """## Suggested First Tasks for New Contributors

1. **Documentation Improvements**
   - Review and update README.md with current setup instructions
   - Add docstrings to public functions and classes
   - Create architecture diagram showing component relationships

2. **Testing**
   - Add unit tests for utility functions
   - Implement integration tests for main workflows
   - Increase test coverage for critical paths

3. **Code Quality**
   - Run linter and fix style issues
   - Add type hints to untyped functions
   - Refactor long functions into smaller, testable units

4. **Bug Fixes**
   - Check GitHub Issues for "good first issue" label
   - Fix documentation typos and errors
   - Handle edge cases in error handling"""


def wrap_llm_call_with_fallback(api_key: str, llm_function, fallback_value: str) -> str:
    """
    Wrapper function to call LLM with fallback.
    
    Args:
        api_key: API key to check if available
        llm_function: Async function that calls the LLM
        fallback_value: Value to return if no API key or LLM fails
        
    Returns:
        LLM response or fallback value
    """
    if not api_key:
        return fallback_value
    
    # The actual try-except should be in the caller
    # This is just a utility helper
    return None
