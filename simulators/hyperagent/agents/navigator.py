"""
Navigator agent for HyperAgent simulation.

The Navigator agent specializes in efficient information retrieval within the codebase.
Equipped with IDE-like tools such as go_to_definition and code_search,
it traverses codebases rapidly.

Based on the HyperAgent architecture from FSoft-AI4Code:
https://github.com/FSoft-AI4Code/HyperAgent
"""

from typing import Dict, Any, Optional, List
import logging
import os
import subprocess
from .base_agent import BaseAgent
from ..degrading_brain import degrading_think


class NavigatorAgent(BaseAgent):
    """
    Navigator agent - Information retrieval specialist.
    
    The Navigator:
    - Specializes in efficient information retrieval within the codebase
    - Uses IDE-like tools (go_to_definition, code_search)
    - Designed for speed and lightweight operation
    - Traverses codebases rapidly
    """

    def __init__(self, config, message_queue, logger: Optional[logging.Logger] = None):
        super().__init__(config, message_queue, "navigator", logger)
        self.search_results = []
        self.codebase_index = {}
        self.llm_client = None
        
    def set_llm_client(self, llm_client):
        """Set the LLM client for real LLM calls."""
        self.llm_client = llm_client
        
    def process(self, task: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a navigation/search task.
        
        Args:
            task: Task with 'action' (search_codebase, go_to_definition, etc.)
            context: Additional context including search query
            
        Returns:
            Dictionary containing search results and navigation info
        """
        action = task.get("action", "search_codebase")
        task_id = task.get("task_id", "unknown")
        
        self.logger.info(f"Navigator processing action: {action} for task {task_id}")
        
        if action == "search_codebase":
            result = self._search_codebase(context)
        elif action == "go_to_definition":
            result = self._go_to_definition(context)
        elif action == "analyze_dependencies":
            result = self._analyze_dependencies(context)
        else:
            result = {"error": f"Unknown action: {action}"}
        
        self._log_action(action, {"task_id": task_id})
        
        return {
            "agent": "navigator",
            "task_id": task_id,
            "action": action,
            "result": result,
            "status": "completed"
        }
    
    def _search_codebase(self, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Search the codebase for relevant code using ripgrep."""
        query = context.get("query", "") if context else ""
        repo_path = context.get("repo_path", ".") if context else "."
        
        # Use ripgrep for real code search
        try:
            result = subprocess.run(
                ["rg", query, repo_path, "-l", "--type=py"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                files = result.stdout.strip().split('\n') if result.stdout.strip() else []
                search_results = []
                for file in files:
                    # Get line numbers and snippets
                    lines_result = subprocess.run(
                        ["rg", query, file, "-n", "--type=py", "-C", "2"],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if lines_result.returncode == 0:
                        search_results.append({
                            "file": file,
                            "matches": lines_result.stdout
                        })
                
                self.search_results = search_results
                
                # Use LLM to analyze search results with degradation
                try:
                    system_prompt = "You are a code search analyst. Analyze the search results and provide insights about relevant code locations and patterns."
                    user_text = f"Search query: {query}\n\nFound {len(search_results)} files with matches:\n" + "\n".join([f"- {r['file']}: {len(r['matches'])} matches" for r in search_results[:5]])
                    
                    llm_analysis = degrading_think(
                        system_prompt=system_prompt,
                        user_text=user_text,
                        state=self.degradation_state,
                        max_tokens=400
                    )
                    
                    self.logger.info(f"Navigator LLM analysis: {str(llm_analysis)}")
                except Exception as e:
                    self.logger.warning(f"Navigator LLM analysis failed: {e}")
                
                return {
                    "query": query,
                    "results": search_results,
                    "count": len(search_results)
                }
            else:
                return {
                    "query": query,
                    "results": [],
                    "count": 0,
                    "error": "No matches found"
                }
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            # Fallback to mock if ripgrep not available
            self.logger.warning(f"ripgrep not available, using mock search: {e}")
            mock_results = [
                {"file": "src/main.py", "line": 42, "snippet": "def process_data(data):"},
                {"file": "src/utils.py", "line": 15, "snippet": "class DataProcessor:"},
            ]
            self.search_results = mock_results
            
            # Use LLM to analyze mock search results with degradation
            try:
                system_prompt = "You are a code search analyst. Analyze the search results and provide insights about relevant code locations and patterns."
                user_text = f"Search query: {query}\n\nFound {len(mock_results)} files with matches:\n" + "\n".join([f"- {r['file']}: {r['snippet']}" for r in mock_results])
                
                llm_analysis = degrading_think(
                    system_prompt=system_prompt,
                    user_text=user_text,
                    state=self.degradation_state,
                    max_tokens=400
                )
                
                self.logger.info(f"Navigator LLM analysis: {str(llm_analysis)}")
            except Exception as e:
                self.logger.warning(f"Navigator LLM analysis failed: {e}")
            
            return {
                "query": query,
                "results": mock_results,
                "count": len(mock_results),
                "warning": "Using mock results (ripgrep not available)"
            }
    
    def _go_to_definition(self, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Go to definition of a symbol using ctags or similar."""
        symbol = context.get("symbol", "") if context else ""
        repo_path = context.get("repo_path", ".") if context else "."
        
        # Try to use ctags for real definition lookup
        try:
            result = subprocess.run(
                ["ctags", "-x", symbol, repo_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if lines:
                    parts = lines[0].split()
                    return {
                        "symbol": symbol,
                        "definition": {
                            "file": parts[1] if len(parts) > 1 else "unknown",
                            "line": parts[2] if len(parts) > 2 else "unknown",
                            "definition": parts[0] if parts else symbol
                        }
                    }
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            self.logger.warning(f"ctags not available, using mock definition: {e}")
        
        # Fallback to mock definition lookup
        return {
            "symbol": symbol,
            "definition": {
                "file": "src/utils.py",
                "line": 15,
                "definition": f"class {symbol}:"
            },
            "warning": "Using mock definition (ctags not available)"
        }
    
    def _analyze_dependencies(self, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze dependencies in the codebase using pipreqs or similar."""
        repo_path = context.get("repo_path", ".") if context else "."
        
        # Try to analyze requirements.txt or pyproject.toml
        dependencies = []
        internal_modules = []
        
        # Check for requirements.txt
        req_file = os.path.join(repo_path, "requirements.txt")
        if os.path.exists(req_file):
            with open(req_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        dependencies.append({"name": line.split('==')[0].split('>=')[0].split('<=')[0]})
        
        # Check for pyproject.toml
        pyproject_file = os.path.join(repo_path, "pyproject.toml")
        if os.path.exists(pyproject_file):
            try:
                with open(pyproject_file, 'r') as f:
                    content = f.read()
                    # Simple parsing (in production, use toml library)
                    if 'dependencies' in content:
                        self.logger.info("Found pyproject.toml with dependencies")
            except Exception as e:
                self.logger.warning(f"Could not parse pyproject.toml: {e}")
        
        # Scan for internal modules
        if os.path.exists(repo_path):
            for item in os.listdir(repo_path):
                item_path = os.path.join(repo_path, item)
                if os.path.isdir(item_path) and not item.startswith('.') and item != '__pycache__':
                    init_file = os.path.join(item_path, '__init__.py')
                    if os.path.exists(init_file):
                        internal_modules.append(item)
        
        return {
            "dependencies": dependencies,
            "internal_modules": internal_modules
        }
