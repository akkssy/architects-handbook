"""File editor for AI-powered code modifications."""

import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from ai_code_assistant.config import Config, get_language_by_extension
from ai_code_assistant.llm import LLMManager
from ai_code_assistant.editor.prompts import EDIT_PROMPTS
from ai_code_assistant.editor.diff_handler import DiffHandler, DiffResult


EditMode = Literal["edit", "targeted", "refactor", "fix", "add"]


@dataclass
class EditResult:
    """Result of a file edit operation."""
    filename: str
    original_content: str
    modified_content: str
    instruction: str
    mode: EditMode
    diff: Optional[DiffResult] = None
    backup_path: Optional[str] = None
    applied: bool = False
    error: Optional[str] = None
    raw_response: str = ""
    
    @property
    def success(self) -> bool:
        return self.error is None and bool(self.modified_content)
    
    @property
    def has_changes(self) -> bool:
        return self.original_content != self.modified_content
    
    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "instruction": self.instruction,
            "mode": self.mode,
            "success": self.success,
            "has_changes": self.has_changes,
            "applied": self.applied,
            "backup_path": self.backup_path,
            "error": self.error,
            "diff": self.diff.to_dict() if self.diff else None,
        }


class FileEditor:
    """AI-powered file editor."""
    
    def __init__(self, config: Config, llm_manager: LLMManager):
        """Initialize the file editor.
        
        Args:
            config: Application configuration
            llm_manager: LLM manager for AI interactions
        """
        self.config = config
        self.llm = llm_manager
        self.diff_handler = DiffHandler()
    
    def edit_file(
        self,
        file_path: Path,
        instruction: str,
        mode: EditMode = "edit",
        preview: bool = False,
        create_backup: bool = True,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> EditResult:
        """Edit a file using AI based on natural language instructions.
        
        Args:
            file_path: Path to the file to edit
            instruction: Natural language edit instruction
            mode: Edit mode (edit, targeted, refactor, fix, add)
            preview: If True, don't apply changes
            create_backup: If True, create backup before editing
            start_line: Start line for targeted edits
            end_line: End line for targeted edits
            
        Returns:
            EditResult with the edit outcome
        """
        # Validate file exists
        if not file_path.exists():
            return EditResult(
                filename=str(file_path),
                original_content="",
                modified_content="",
                instruction=instruction,
                mode=mode,
                error=f"File not found: {file_path}",
            )
        
        # Check file size
        file_size_kb = file_path.stat().st_size / 1024
        max_size = self.config.editor.max_file_size_kb if hasattr(self.config, 'editor') else 500
        if file_size_kb > max_size:
            return EditResult(
                filename=str(file_path),
                original_content="",
                modified_content="",
                instruction=instruction,
                mode=mode,
                error=f"File too large: {file_size_kb:.1f}KB (max: {max_size}KB)",
            )
        
        # Read original content
        try:
            original_content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            return EditResult(
                filename=str(file_path),
                original_content="",
                modified_content="",
                instruction=instruction,
                mode=mode,
                error=f"Could not read file: {e}",
            )
        
        # Detect language
        language = get_language_by_extension(self.config, file_path) or "text"
        
        # Get modified content from LLM
        result = self._get_edited_content(
            original_content=original_content,
            instruction=instruction,
            filename=str(file_path.name),
            language=language,
            mode=mode,
            start_line=start_line,
            end_line=end_line,
        )
        
        if result.error:
            return result
        
        # Generate diff
        diff = self.diff_handler.generate_diff(
            original=original_content,
            modified=result.modified_content,
            filename=str(file_path.name),
        )
        result.diff = diff
        
        # Apply changes if not preview mode
        if not preview and result.has_changes:
            backup_path = None
            
            # Create backup if requested
            if create_backup:
                backup_path = self._create_backup(file_path)
                result.backup_path = str(backup_path) if backup_path else None
            
            # Write modified content
            try:
                file_path.write_text(result.modified_content, encoding="utf-8")
                result.applied = True
            except Exception as e:
                result.error = f"Could not write file: {e}"
                result.applied = False
        
        return result

    def _get_edited_content(
        self,
        original_content: str,
        instruction: str,
        filename: str,
        language: str,
        mode: EditMode,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> EditResult:
        """Get edited content from LLM.

        Args:
            original_content: Original file content
            instruction: Edit instruction
            filename: Name of the file
            language: Programming language
            mode: Edit mode
            start_line: Start line for targeted edits
            end_line: End line for targeted edits

        Returns:
            EditResult with modified content
        """
        # Select appropriate prompt
        if mode == "targeted" and start_line and end_line:
            prompt = EDIT_PROMPTS["targeted"]
            kwargs = {
                "code": original_content,
                "instruction": instruction,
                "filename": filename,
                "language": language,
                "start_line": start_line,
                "end_line": end_line,
            }
        else:
            prompt = EDIT_PROMPTS.get(mode, EDIT_PROMPTS["edit"])
            kwargs = {
                "code": original_content,
                "instruction": instruction,
                "filename": filename,
                "language": language,
            }

        try:
            response = self.llm.invoke_with_template(prompt, **kwargs)
            modified_content = self._extract_code(response, language)

            if not modified_content:
                return EditResult(
                    filename=filename,
                    original_content=original_content,
                    modified_content="",
                    instruction=instruction,
                    mode=mode,
                    error="Could not extract code from LLM response",
                    raw_response=response,
                )

            return EditResult(
                filename=filename,
                original_content=original_content,
                modified_content=modified_content,
                instruction=instruction,
                mode=mode,
                raw_response=response,
            )

        except Exception as e:
            return EditResult(
                filename=filename,
                original_content=original_content,
                modified_content="",
                instruction=instruction,
                mode=mode,
                error=f"LLM error: {str(e)}",
            )

    def _extract_code(self, response: str, language: str) -> str:
        """Extract code from LLM response.

        Args:
            response: Raw LLM response
            language: Expected language

        Returns:
            Extracted code or empty string
        """
        # Try to find code block with language tag
        pattern = rf"```{language}\s*\n(.*?)```"
        match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # Try generic code block
        pattern = r"```\w*\s*\n(.*?)```"
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Try to find code without explicit blocks (fallback)
        # If response looks like code, return it
        lines = response.strip().split('\n')
        if len(lines) > 1 and not response.startswith('I ') and not response.startswith('Here'):
            return response.strip()

        return ""

    def _create_backup(self, file_path: Path) -> Optional[Path]:
        """Create a backup of the file.

        Args:
            file_path: Path to the file to backup

        Returns:
            Path to backup file or None if failed
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}.{timestamp}.bak{file_path.suffix}"
        backup_path = file_path.parent / backup_name

        try:
            shutil.copy2(file_path, backup_path)
            return backup_path
        except Exception:
            return None

    def edit_code(
        self,
        code: str,
        instruction: str,
        language: str = "python",
        mode: EditMode = "edit",
    ) -> EditResult:
        """Edit code string directly without file operations.

        Args:
            code: Code to edit
            instruction: Edit instruction
            language: Programming language
            mode: Edit mode

        Returns:
            EditResult with modified code
        """
        result = self._get_edited_content(
            original_content=code,
            instruction=instruction,
            filename="code_snippet",
            language=language,
            mode=mode,
        )

        if result.success:
            result.diff = self.diff_handler.generate_diff(
                original=code,
                modified=result.modified_content,
                filename="code_snippet",
            )

        return result

    def restore_backup(self, backup_path: Path, original_path: Path) -> bool:
        """Restore a file from backup.

        Args:
            backup_path: Path to backup file
            original_path: Path to restore to

        Returns:
            True if successful, False otherwise
        """
        try:
            shutil.copy2(backup_path, original_path)
            return True
        except Exception:
            return False
