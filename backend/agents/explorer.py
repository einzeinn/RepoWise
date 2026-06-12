import os
import httpx
from typing import Any, Dict, List
from dotenv import load_dotenv

# Import base agent class
from .base import BaseAgent, AgentResponse

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

class ExplorerAgent(BaseAgent):
    """
    Agent responsible for scanning and mapping the file structure
    of a GitHub repository.
    """
    def __init__(self):
        super().__init__(name="Explorer_Agent")
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "REPOWISE-MultiAgent-Explorer",
        }
        if self.github_token:
            self.headers["Authorization"] = f"Bearer {self.github_token}"

    async def _fetch_repo_tree(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        """Fetch the file tree from the repository recursively."""
        # This endpoint fetches all files on the default branch (main)
        url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1"
        
        # follow_redirects=True is critical for the GitHub API
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, headers=self.headers)
            
            # Fallback: Try 'master' branch if 'main' not found (404)
            if response.status_code == 404:
                url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/master?recursive=1"
                response = await client.get(url, headers=self.headers)

            if response.status_code != 200:
                raise Exception(f"Failed to access GitHub API: {response.text}")
            
            tree_data = response.json().get("tree", [])
            
            files = []
            # Filter: only keep blob (file) entries, skip directories
            for item in tree_data:
                if item["type"] == "blob":
                    files.append({
                        "path": item["path"],
                        "url": item["url"],
                        "size": item["size"]
                    })
            return files

    async def process(self, context: Dict[str, Any]) -> AgentResponse:
        """
        Run the Explorer task.
        Expects context with key 'repo_url'.
        """
        repo_url = context.get("repo_url", "")
        
        # Validate GitHub URL format (e.g. https://github.com/facebook/react)
        repo_url = repo_url.rstrip("/")
        parts = repo_url.split("/")
        
        if len(parts) < 2 or "github.com" not in repo_url:
            return AgentResponse(
                status="error",
                agent_name=self.name,
                data={},
                message="Invalid GitHub repository URL format."
            )
        
        owner, repo = parts[-2], parts[-1]

        try:
            # 1. Run async scanning process
            file_tree = await self._fetch_repo_tree(owner, repo)
            
            # 2. Build structured handoff data for the next agent
            return AgentResponse(
                status="success",
                agent_name=self.name,
                data={
                    "repository_owner": owner,
                    "repository_name": repo,
                    "total_files": len(file_tree),
                    "file_tree": file_tree
                },
                message=f"Successfully scanned repository {owner}/{repo}. Found {len(file_tree)} files."
            )
            
        except Exception as e:
            return AgentResponse(
                status="error",
                agent_name=self.name,
                data={},
                message=f"Explorer internal error: {str(e)}"
            )