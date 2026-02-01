"""Multi-file editor for coordinated refactoring operations."""

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ai_code_assistant.config import Config, get_language_by_extension
from ai_code_assistant.llm import LLMManager
from ai_code_assistant.editor.diff_handler import DiffHandler
from ai_code_assistant.refactor.prompts import (
    MULTI_FILE_EDIT_PROMPT,
    RENAME_SYMBOL_PROMPT,
    EXTRACT_TO_FILE_PROMPT,
)
from ai_code_assistant.refactor.change_plan import (
    ChangePlan,
    FileChange,
    ChangeType,
    RefactorResult,
)
from ai_code_assistant.refactor.analyzer import RefactorAnalyzer


class MultiFileEditor:
    """Editor for coordinated multi-file refactoring."""
    
    def __init__(self, config: Config, llm_manager: LLMManager):
        """Initialize the multi-file editor.
        
        Args:
            config: Application configuration
            llm_manager: LLM manager for AI interactions
        """
        self.config = config
        self.llm = llm_manager
        self.diff_handler = DiffHandler()
        self.analyzer = RefactorAnalyzer(config, llm_manager)
    
    def refactor(
        self,
        instruction: str,
        files: List[Path],
        dry_run: bool = False,
        create_backup: bool = True,
    ) -> RefactorResult:
        """Perform multi-file refactoring.
        
        Args:
            instruction: Refactoring instruction
            files: List of files to potentially modify
            dry_run: If True, don't apply changes
            create_backup: If True, create backup before changes
            
        Returns:
            RefactorResult with all changes
        """
        # Analyze to create plan
        plan = self.analyzer.analyze(instruction, files)
        
        if not plan.changes:
            return RefactorResult(
                plan=plan,
                error="No changes identified",
            )
        
        # Read current file contents
        file_contents = self._read_files([Path(c.file_path) for c in plan.changes])
        
        # Update plan with original content
        for change in plan.changes:
            if change.file_path in file_contents:
                change.original_content = file_contents[change.file_path]
        
        # Generate changes
        result = self._generate_changes(plan, file_contents)
        
        if result.error:
            return result
        
        # Apply changes if not dry run
        if not dry_run:
            backup_dir = None
            if create_backup:
                backup_dir = self._create_backup(plan)
                result.backup_dir = str(backup_dir) if backup_dir else None
            
            self._apply_changes(plan)
            result.applied = True
        
        return result
    
    def rename_symbol(
        self,
        old_name: str,
        new_name: str,
        symbol_type: str,
        files: List[Path],
        dry_run: bool = False,
    ) -> RefactorResult:
        """Rename a symbol across multiple files.
        
        Args:
            old_name: Current symbol name
            new_name: New symbol name
            symbol_type: Type of symbol (function, class, variable, etc.)
            files: Files to search and modify
            dry_run: If True, don't apply changes
            
        Returns:
            RefactorResult with all changes
        """
        # Read file contents
        file_contents = self._read_files(files)
        
        # Filter to files containing the symbol
        relevant_files = {
            path: content for path, content in file_contents.items()
            if old_name in content
        }
        
        if not relevant_files:
            plan = ChangePlan(
                instruction=f"Rename {symbol_type} '{old_name}' to '{new_name}'",
                summary=f"Symbol '{old_name}' not found in any files",
                changes=[],
            )
            return RefactorResult(plan=plan, error="Symbol not found")
        
        # Create plan
        plan = ChangePlan(
            instruction=f"Rename {symbol_type} '{old_name}' to '{new_name}'",
            summary=f"Renaming {symbol_type} across {len(relevant_files)} files",
            changes=[
                FileChange(
                    file_path=path,
                    change_type=ChangeType.MODIFY,
                    description=f"Rename '{old_name}' to '{new_name}'",
                    original_content=content,
                )
                for path, content in relevant_files.items()
            ],
        )
        
        # Generate changes using LLM
        formatted_contents = self._format_file_contents(relevant_files)
        
        try:
            response = self.llm.invoke_with_template(
                RENAME_SYMBOL_PROMPT,
                old_name=old_name,
                new_name=new_name,
                symbol_type=symbol_type,
                file_contents=formatted_contents,
            )
            
            self._parse_multi_file_response(plan, response)
            
        except Exception as e:
            return RefactorResult(plan=plan, error=f"LLM error: {str(e)}")
        
        # Apply if not dry run
        if not dry_run:
            self._apply_changes(plan)
            return RefactorResult(plan=plan, applied=True)
        
        return RefactorResult(plan=plan)
    
    def _read_files(self, files: List[Path]) -> Dict[str, str]:
        """Read contents of files."""
        contents = {}
        for file_path in files:
            if file_path.exists():
                try:
                    contents[str(file_path)] = file_path.read_text(encoding="utf-8")
                except Exception:
                    pass
        return contents
    
    def _format_file_contents(self, contents: Dict[str, str]) -> str:
        """Format file contents for prompt."""
        parts = []
        for file_path, content in contents.items():
            lang = get_language_by_extension(self.config, Path(file_path)) or "text"
            parts.append(f"### {file_path}\n```{lang}\n{content}\n```\n")
        return "\n".join(parts)

    def _generate_changes(
        self,
        plan: ChangePlan,
        file_contents: Dict[str, str],
    ) -> RefactorResult:
        """Generate actual file changes using LLM.

        Args:
            plan: The change plan
            file_contents: Current file contents

        Returns:
            RefactorResult with generated changes
        """
        # Format change plan for prompt
        change_plan_text = "\n".join([
            f"- {c.file_path}: {c.description} ({c.change_type.value})"
            for c in plan.changes
        ])

        formatted_contents = self._format_file_contents(file_contents)

        try:
            response = self.llm.invoke_with_template(
                MULTI_FILE_EDIT_PROMPT,
                instruction=plan.instruction,
                change_plan=change_plan_text,
                file_contents=formatted_contents,
            )

            self._parse_multi_file_response(plan, response)

            # Generate diffs for each change
            for change in plan.changes:
                if change.new_content and change.original_content:
                    change.diff = self.diff_handler.generate_diff(
                        original=change.original_content,
                        modified=change.new_content,
                        filename=change.file_path,
                    )

            return RefactorResult(plan=plan)

        except Exception as e:
            return RefactorResult(plan=plan, error=f"LLM error: {str(e)}")

    def _parse_multi_file_response(self, plan: ChangePlan, response: str) -> None:
        """Parse LLM response containing multiple file contents.

        Args:
            plan: Change plan to update
            response: LLM response with file contents
        """
        # Pattern to match file sections
        pattern = r"###\s*FILE:\s*([^\n]+)\s*\n```\w*\s*\n(.*?)```"
        matches = re.findall(pattern, response, re.DOTALL)

        # Map new content to changes
        for file_path, content in matches:
            file_path = file_path.strip()
            content = content.strip()

            # Find matching change in plan
            for change in plan.changes:
                if change.file_path == file_path or file_path.endswith(change.file_path):
                    change.new_content = content
                    break

    def _create_backup(self, plan: ChangePlan) -> Optional[Path]:
        """Create backup of all files to be modified.

        Args:
            plan: Change plan with files to backup

        Returns:
            Path to backup directory or None
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = Path(f".refactor_backup_{timestamp}")

        try:
            backup_dir.mkdir(exist_ok=True)

            for change in plan.changes:
                if change.change_type in (ChangeType.MODIFY, ChangeType.DELETE):
                    src = Path(change.file_path)
                    if src.exists():
                        # Preserve directory structure in backup
                        dest = backup_dir / change.file_path
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dest)

            return backup_dir

        except Exception:
            return None

    def _apply_changes(self, plan: ChangePlan) -> None:
        """Apply all changes in the plan.

        Args:
            plan: Change plan with changes to apply
        """
        for change in plan.get_ordered_changes():
            try:
                path = Path(change.file_path)

                if change.change_type == ChangeType.DELETE:
                    if path.exists():
                        path.unlink()
                    change.applied = True

                elif change.change_type == ChangeType.CREATE:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(change.new_content, encoding="utf-8")
                    change.applied = True

                elif change.change_type == ChangeType.RENAME:
                    if path.exists() and change.new_path:
                        new_path = Path(change.new_path)
                        new_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(path), str(new_path))
                    change.applied = True

                elif change.change_type == ChangeType.MODIFY:
                    if change.new_content:
                        path.write_text(change.new_content, encoding="utf-8")
                        change.applied = True
                    else:
                        change.error = "No new content generated"

            except Exception as e:
                change.error = str(e)

    def restore_backup(self, backup_dir: Path) -> bool:
        """Restore files from backup.

        Args:
            backup_dir: Path to backup directory

        Returns:
            True if successful
        """
        if not backup_dir.exists():
            return False

        try:
            for backup_file in backup_dir.rglob("*"):
                if backup_file.is_file():
                    # Get relative path from backup dir
                    rel_path = backup_file.relative_to(backup_dir)
                    dest = Path(rel_path)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup_file, dest)
            return True
        except Exception:
            return False

