"""Analyzer for determining refactoring scope and impact."""

import json
import re
from pathlib import Path
from typing import List, Optional

from ai_code_assistant.config import Config, get_language_by_extension
from ai_code_assistant.llm import LLMManager
from ai_code_assistant.refactor.prompts import ANALYZE_REFACTOR_PROMPT
from ai_code_assistant.refactor.change_plan import ChangePlan, FileChange, ChangeType


class RefactorAnalyzer:
    """Analyzes codebase to determine refactoring scope."""
    
    def __init__(self, config: Config, llm_manager: LLMManager):
        """Initialize the refactor analyzer.
        
        Args:
            config: Application configuration
            llm_manager: LLM manager for AI interactions
        """
        self.config = config
        self.llm = llm_manager
    
    def analyze(
        self,
        instruction: str,
        files: List[Path],
        max_files: int = 20,
    ) -> ChangePlan:
        """Analyze files to create a refactoring plan.
        
        Args:
            instruction: Refactoring instruction
            files: List of files to analyze
            max_files: Maximum number of files to include
            
        Returns:
            ChangePlan with proposed changes
        """
        # Limit files to analyze
        files = files[:max_files]
        
        # Read file contents
        file_contents = self._read_files(files)
        
        if not file_contents:
            return ChangePlan(
                instruction=instruction,
                summary="No files to analyze",
                changes=[],
            )
        
        # Format file contents for prompt
        formatted_contents = self._format_file_contents(file_contents)
        
        # Get analysis from LLM
        try:
            response = self.llm.invoke_with_template(
                ANALYZE_REFACTOR_PROMPT,
                instruction=instruction,
                file_contents=formatted_contents,
            )
            
            return self._parse_analysis(instruction, response)
            
        except Exception as e:
            return ChangePlan(
                instruction=instruction,
                summary=f"Analysis failed: {str(e)}",
                changes=[],
            )
    
    def _read_files(self, files: List[Path]) -> dict:
        """Read contents of files.
        
        Args:
            files: List of file paths
            
        Returns:
            Dict mapping file path to content
        """
        contents = {}
        max_size = getattr(self.config, 'refactor', None)
        max_size_kb = max_size.max_file_size_kb if max_size else 500
        
        for file_path in files:
            if not file_path.exists():
                continue
            
            # Check file size
            if file_path.stat().st_size > max_size_kb * 1024:
                continue
            
            try:
                contents[str(file_path)] = file_path.read_text(encoding="utf-8")
            except Exception:
                continue
        
        return contents
    
    def _format_file_contents(self, contents: dict) -> str:
        """Format file contents for prompt.
        
        Args:
            contents: Dict mapping file path to content
            
        Returns:
            Formatted string with all file contents
        """
        parts = []
        for file_path, content in contents.items():
            language = self._detect_language(file_path)
            parts.append(f"### {file_path}\n```{language}\n{content}\n```\n")
        return "\n".join(parts)
    
    def _detect_language(self, file_path: str) -> str:
        """Detect language from file path."""
        path = Path(file_path)
        lang = get_language_by_extension(self.config, path)
        return lang or "text"
    
    def _parse_analysis(self, instruction: str, response: str) -> ChangePlan:
        """Parse LLM analysis response into ChangePlan.
        
        Args:
            instruction: Original instruction
            response: LLM response
            
        Returns:
            Parsed ChangePlan
        """
        # Try to extract JSON from response
        json_data = self._extract_json(response)
        
        if not json_data:
            return ChangePlan(
                instruction=instruction,
                summary="Could not parse analysis response",
                changes=[],
            )
        
        # Parse changes
        changes = []
        for file_data in json_data.get("affected_files", []):
            change_type_str = file_data.get("change_type", "modify").lower()
            try:
                change_type = ChangeType(change_type_str)
            except ValueError:
                change_type = ChangeType.MODIFY
            
            changes.append(FileChange(
                file_path=file_data.get("file_path", ""),
                change_type=change_type,
                description=file_data.get("description", ""),
                priority=file_data.get("priority", "medium"),
                depends_on=file_data.get("depends_on", []),
            ))
        
        return ChangePlan(
            instruction=instruction,
            summary=json_data.get("summary", ""),
            changes=changes,
            risks=json_data.get("risks", []),
            complexity=json_data.get("estimated_complexity", "medium"),
        )
    
    def _extract_json(self, text: str) -> Optional[dict]:
        """Extract JSON from text response."""
        # Try to find JSON in code block
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try to find raw JSON
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        
        return None

