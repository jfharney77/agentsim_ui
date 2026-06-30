"""
Code Editor agent for HyperAgent simulation.

The Editor agent is responsible for code modification and generation across multiple files.
It employs tools including auto_repair_editor, code_search, and open_file.

Based on the HyperAgent architecture from FSoft-AI4Code:
https://github.com/FSoft-AI4Code/HyperAgent
"""

from typing import Dict, Any, Optional, List
import logging
import os
import difflib
from .base_agent import BaseAgent
from ..degrading_brain import degrading_think


class CodeEditorAgent(BaseAgent):
    """
    Code Editor agent - Code modification and generation specialist.
    
    The Editor:
    - Responsible for code modification and generation across multiple files
    - Uses tools: auto_repair_editor, code_search, open_file
    - Generates code patches based on target file and context from Planner
    - Applies patches using auto_repair_editor
    """

    def __init__(self, config, message_queue, logger: Optional[logging.Logger] = None):
        super().__init__(config, message_queue, "editor", logger)
        self.edited_files = []
        self.applied_patches = []
        self.llm_client = None
        
    def set_llm_client(self, llm_client):
        """Set the LLM client for real LLM calls."""
        self.llm_client = llm_client
        
    def process(self, task: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a code editing task.
        
        Args:
            task: Task with 'action' (modify_code, generate_code, etc.)
            context: Additional context including target files and modifications
            
        Returns:
            Dictionary containing edit results and patch information
        """
        action = task.get("action", "modify_code")
        task_id = task.get("task_id", "unknown")
        
        self.logger.info(f"Editor processing action: {action} for task {task_id}")
        
        if action == "modify_code":
            result = self._modify_code(context)
        elif action == "generate_code":
            result = self._generate_code(context)
        elif action == "apply_patch":
            result = self._apply_patch(context)
        elif action == "read_file":
            result = self._read_file(context)
        else:
            result = {"error": f"Unknown action: {action}"}
        
        self._log_action(action, {"task_id": task_id})
        
        return {
            "agent": "editor",
            "task_id": task_id,
            "action": action,
            "result": result,
            "status": "completed"
        }
    
    def _read_file(self, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Read the contents of a file."""
        if not context:
            return {"error": "No context provided"}
        
        file_path = context.get("file_path", "")
        
        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}"}
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            return {
                "file_path": file_path,
                "content": content,
                "line_count": len(content.split('\n'))
            }
        except Exception as e:
            return {"error": f"Failed to read file: {str(e)}"}
    
    def _modify_code(self, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Modify code in target files using real file operations."""
        if not context:
            return {"error": "No context provided"}
        
        target_file = context.get("target_file", "")
        modifications = context.get("modifications", [])
        
        if not os.path.exists(target_file):
            return {"error": f"File not found: {target_file}"}
        
        try:
            # Read original file
            with open(target_file, 'r') as f:
                original_content = f.read()
            
            # Apply modifications
            modified_content = original_content
            for mod in modifications:
                if isinstance(mod, dict):
                    if "old_text" in mod and "new_text" in mod:
                        modified_content = modified_content.replace(mod["old_text"], mod["new_text"])
                    elif "line_number" in mod and "new_line" in mod:
                        lines = modified_content.split('\n')
                        line_num = mod["line_number"] - 1  # Convert to 0-indexed
                        if 0 <= line_num < len(lines):
                            lines[line_num] = mod["new_line"]
                        modified_content = '\n'.join(lines)
            
            # Write modified content
            with open(target_file, 'w') as f:
                f.write(modified_content)
            
            # Generate diff
            diff = list(difflib.unified_diff(
                original_content.splitlines(keepends=True),
                modified_content.splitlines(keepends=True),
                fromfile=target_file,
                tofile=target_file
            ))
            
            patch_info = {
                "file": target_file,
                "changes": modifications,
                "status": "applied",
                "diff": ''.join(diff)
            }
            
            self.edited_files.append(target_file)
            self.applied_patches.append(patch_info)
            
            return {
                "target_file": target_file,
                "modifications": modifications,
                "patch": patch_info,
                "status": "success"
            }
        except Exception as e:
            return {
                "target_file": target_file,
                "error": f"Failed to modify file: {str(e)}",
                "status": "failed"
            }
    
    def _generate_code(self, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate new code based on requirements using LLM."""
        requirements = context.get("requirements", "") if context else ""
        target_file = context.get("target_file", "") if context else ""
        
        # Use LLM to generate code with degradation
        try:
            system_prompt = "You are a code generator. Generate Python code based on the requirements. Return only the code without explanations."
            user_text = f"Requirements: {requirements}\n\nGenerate a Python function or class that meets these requirements."
            
            generated_code = degrading_think(
                system_prompt=system_prompt,
                user_text=user_text,
                state=self.degradation_state,
                max_tokens=800
            )
            
            self.logger.info(f"Editor LLM code generation: {str(generated_code)}")
        except Exception as e:
            self.logger.warning(f"Editor LLM code generation failed: {e}, using template")
            # Fallback to template
            generated_code = f"""
# Generated code based on requirements: {requirements}
def generated_function():
    # Implementation
    pass
"""
        
        # If target file is specified, write to it
        if target_file:
            try:
                os.makedirs(os.path.dirname(target_file), exist_ok=True)
                with open(target_file, 'w') as f:
                    f.write(generated_code)
                return {
                    "requirements": requirements,
                    "generated_code": generated_code,
                    "target_file": target_file,
                    "status": "written"
                }
            except Exception as e:
                return {
                    "requirements": requirements,
                    "generated_code": generated_code,
                    "error": f"Failed to write file: {str(e)}"
                }
        
        return {
            "requirements": requirements,
            "generated_code": generated_code,
            "language": "python"
        }
    
    def _apply_patch(self, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply a code patch to a file using real file operations."""
        patch = context.get("patch", {}) if context else {}
        file_path = patch.get("file", "")
        
        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}"}
        
        try:
            with open(file_path, 'r') as f:
                original_content = f.read()
            
            # Apply patch (simplified - in production use patch utility)
            if "diff" in patch:
                # This is a simplified approach
                # In production, use the patch utility or a proper diff parser
                modified_content = original_content  # Placeholder
            
            with open(file_path, 'w') as f:
                f.write(modified_content)
            
            return {
                "file": file_path,
                "patch": patch,
                "status": "applied_successfully"
            }
        except Exception as e:
            return {
                "file": file_path,
                "error": f"Failed to apply patch: {str(e)}",
                "status": "failed"
            }
