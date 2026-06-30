"""
Executor agent for HyperAgent simulation.

The Executor agent validates solutions and reproduces reported issues.
It utilizes an interactive_bash_shell for maintaining execution states
and open_file for accessing relevant documentation.

Based on the HyperAgent architecture from FSoft-AI4Code:
https://github.com/FSoft-AI4Code/HyperAgent
"""

from typing import Dict, Any, Optional, List
import logging
import subprocess
import os
import sys
from .base_agent import BaseAgent
from ..degrading_brain import degrading_think


class ExecutorAgent(BaseAgent):
    """
    Executor agent - Solution validation and issue reproduction specialist.
    
    The Executor:
    - Validates solutions and reproduces reported issues
    - Uses interactive_bash_shell for maintaining execution states
    - Uses open_file for accessing relevant documentation
    - Manages environment setup autonomously
    - Facilitates efficient testing and validation processes
    """

    def __init__(self, config, message_queue, logger: Optional[logging.Logger] = None):
        super().__init__(config, message_queue, "executor", logger)
        self.test_results = []
        self.execution_history = []
        self.working_dir = None
        self.llm_client = None
        
    def set_llm_client(self, llm_client):
        """Set the LLM client for real LLM calls."""
        self.llm_client = llm_client
        
    def process(self, task: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a validation/execution task.
        
        Args:
            task: Task with 'action' (validate, run_tests, reproduce_issue, etc.)
            context: Additional context including code changes and test commands
            
        Returns:
            Dictionary containing validation results and execution info
        """
        action = task.get("action", "validate")
        task_id = task.get("task_id", "unknown")
        
        self.logger.info(f"Executor processing action: {action} for task {task_id}")
        
        if action == "validate":
            result = self._validate(context)
        elif action == "run_tests":
            result = self._run_tests(context)
        elif action == "reproduce_issue":
            result = self._reproduce_issue(context)
        elif action == "setup_environment":
            result = self._setup_environment(context)
        elif action == "execute_command":
            result = self._execute_command(context)
        else:
            result = {"error": f"Unknown action: {action}"}
        
        self._log_action(action, {"task_id": task_id})
        
        return {
            "agent": "executor",
            "task_id": task_id,
            "action": action,
            "result": result,
            "status": "completed"
        }
    
    def _validate(self, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate code changes using syntax checking and LLM analysis."""
        changes = context.get("changes", []) if context else []
        repo_path = context.get("repo_path", ".") if context else "."
        
        validation_result = {
            "changes_validated": len(changes),
            "issues_found": 0,
            "warnings": [],
            "status": "valid"
        }
        
        # Validate Python syntax for modified files
        for change in changes:
            if isinstance(change, dict) and "file" in change:
                file_path = os.path.join(repo_path, change["file"])
                if os.path.exists(file_path) and file_path.endswith('.py'):
                    try:
                        result = subprocess.run(
                            [sys.executable, "-m", "py_compile", file_path],
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        if result.returncode != 0:
                            validation_result["issues_found"] += 1
                            validation_result["warnings"].append({
                                "file": file_path,
                                "error": result.stderr
                            })
                    except (subprocess.TimeoutExpired, Exception) as e:
                        validation_result["warnings"].append({
                            "file": file_path,
                            "error": str(e)
                        })
        
        # Use LLM to analyze validation results with degradation
        try:
            system_prompt = "You are a code validation analyst. Analyze the validation results and provide insights about code quality and potential issues."
            user_text = f"Validated {len(changes)} code changes. Found {validation_result['issues_found']} issues:\n" + "\n".join([f"- {w['file']}: {w.get('error', 'unknown')}" for w in validation_result['warnings'][:3]])
            
            llm_analysis = degrading_think(
                system_prompt=system_prompt,
                user_text=user_text,
                state=self.degradation_state,
                max_tokens=400
            )
            
            self.logger.info(f"Executor LLM validation analysis: {str(llm_analysis)}")
        except Exception as e:
            self.logger.warning(f"Executor LLM validation analysis failed: {e}")
        
        if validation_result["issues_found"] > 0:
            validation_result["status"] = "invalid"
        
        return validation_result
    
    def _run_tests(self, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Run tests to verify changes using pytest or unittest."""
        test_command = context.get("test_command", "pytest") if context else "pytest"
        repo_path = context.get("repo_path", ".") if context else "."
        test_path = context.get("test_path", "") if context else ""
        
        # Build full test command
        if test_path:
            full_command = [test_command, test_path]
        else:
            full_command = [test_command]
        
        try:
            result = subprocess.run(
                full_command,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            # Parse pytest output
            output = result.stdout + result.stderr
            tests_run = 0
            tests_passed = 0
            tests_failed = 0
            
            # Simple parsing (in production, use pytest JSON output)
            if "passed" in output:
                try:
                    parts = output.split("passed")
                    if parts:
                        passed_part = parts[0].strip()
                        if "==" in passed_part:
                            tests_run = int(passed_part.split("==")[-1].strip())
                        tests_passed = int(passed_part.split()[-1].strip()) if passed_part.split() else 0
                except (ValueError, IndexError):
                    pass
            
            if "failed" in output:
                try:
                    failed_part = output.split("failed")[0].split("passed")[-1]
                    tests_failed = int(failed_part.strip().split()[-1])
                except (ValueError, IndexError):
                    tests_failed = 1 if result.returncode != 0 else 0
            
            test_result = {
                "command": " ".join(full_command),
                "tests_run": tests_run,
                "tests_passed": tests_passed,
                "tests_failed": tests_failed,
                "execution_time": 0.0,  # Would need to measure actual time
                "return_code": result.returncode,
                "output": output,
                "status": "passed" if result.returncode == 0 else "failed"
            }
            
            self.test_results.append(test_result)
            return test_result
            
        except subprocess.TimeoutExpired:
            return {
                "command": " ".join(full_command),
                "error": "Test execution timed out",
                "status": "timeout"
            }
        except FileNotFoundError:
            return {
                "command": " ".join(full_command),
                "error": f"Test command not found: {test_command}",
                "status": "command_not_found"
            }
        except Exception as e:
            return {
                "command": " ".join(full_command),
                "error": str(e),
                "status": "error"
            }
    
    def _reproduce_issue(self, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Reproduce a reported issue by running reproduction steps."""
        issue_description = context.get("issue", "") if context else ""
        reproduction_steps = context.get("steps", []) if context else []
        repo_path = context.get("repo_path", ".") if context else "."
        
        results = []
        
        for step in reproduction_steps:
            if isinstance(step, dict) and "command" in step:
                try:
                    result = subprocess.run(
                        step["command"],
                        shell=True,
                        cwd=repo_path,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    results.append({
                        "step": step,
                        "return_code": result.returncode,
                        "output": result.stdout,
                        "error": result.stderr
                    })
                except (subprocess.TimeoutExpired, Exception) as e:
                    results.append({
                        "step": step,
                        "error": str(e)
                    })
        
        return {
            "issue": issue_description,
            "reproduced": any(r.get("return_code", 0) != 0 for r in results),
            "steps_executed": len(results),
            "results": results
        }
    
    def _setup_environment(self, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Setup the execution environment."""
        repo_path = context.get("repo_path", ".") if context else "."
        
        # Check Python version
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        
        # Try to install dependencies if requirements.txt exists
        dependencies_installed = []
        req_file = os.path.join(repo_path, "requirements.txt")
        if os.path.exists(req_file):
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", req_file],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                if result.returncode == 0:
                    # Parse installed packages
                    for line in result.stdout.split('\n'):
                        if "Successfully installed" in line:
                            dependencies_installed = line.split("Successfully installed")[1].strip().split()
            except (subprocess.TimeoutExpired, Exception) as e:
                return {
                    "status": "setup_failed",
                    "python_version": python_version,
                    "error": str(e)
                }
        
        return {
            "status": "setup_complete",
            "python_version": python_version,
            "dependencies_installed": dependencies_installed,
            "environment_ready": True
        }
    
    def _execute_command(self, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute a shell command."""
        command = context.get("command", "") if context else ""
        repo_path = context.get("repo_path", ".") if context else "."
        
        if not command:
            return {"error": "No command provided"}
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            return {
                "command": command,
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "status": "completed"
            }
        except subprocess.TimeoutExpired:
            return {
                "command": command,
                "error": "Command execution timed out",
                "status": "timeout"
            }
        except Exception as e:
            return {
                "command": command,
                "error": str(e),
                "status": "error"
            }
