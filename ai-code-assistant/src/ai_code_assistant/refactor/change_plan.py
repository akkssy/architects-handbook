"""Data structures for multi-file refactoring plans."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Literal, Optional

from ai_code_assistant.editor.diff_handler import DiffResult


class ChangeType(str, Enum):
    """Type of file change."""
    MODIFY = "modify"
    CREATE = "create"
    DELETE = "delete"
    RENAME = "rename"


@dataclass
class FileChange:
    """Represents a planned change to a single file."""
    file_path: str
    change_type: ChangeType
    description: str
    priority: Literal["high", "medium", "low"] = "medium"
    depends_on: List[str] = field(default_factory=list)
    original_content: str = ""
    new_content: str = ""
    new_path: Optional[str] = None  # For rename operations
    diff: Optional[DiffResult] = None
    applied: bool = False
    error: Optional[str] = None
    
    @property
    def success(self) -> bool:
        return self.error is None
    
    @property
    def has_changes(self) -> bool:
        if self.change_type == ChangeType.DELETE:
            return True
        if self.change_type == ChangeType.CREATE:
            return bool(self.new_content)
        return self.original_content != self.new_content
    
    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "change_type": self.change_type.value,
            "description": self.description,
            "priority": self.priority,
            "depends_on": self.depends_on,
            "has_changes": self.has_changes,
            "applied": self.applied,
            "error": self.error,
            "new_path": self.new_path,
            "diff": self.diff.to_dict() if self.diff else None,
        }


@dataclass
class ChangePlan:
    """A plan for multi-file refactoring."""
    instruction: str
    summary: str
    changes: List[FileChange] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    complexity: Literal["low", "medium", "high"] = "medium"
    
    @property
    def total_files(self) -> int:
        return len(self.changes)
    
    @property
    def files_to_modify(self) -> List[FileChange]:
        return [c for c in self.changes if c.change_type == ChangeType.MODIFY]
    
    @property
    def files_to_create(self) -> List[FileChange]:
        return [c for c in self.changes if c.change_type == ChangeType.CREATE]
    
    @property
    def files_to_delete(self) -> List[FileChange]:
        return [c for c in self.changes if c.change_type == ChangeType.DELETE]
    
    @property
    def files_to_rename(self) -> List[FileChange]:
        return [c for c in self.changes if c.change_type == ChangeType.RENAME]
    
    def get_ordered_changes(self) -> List[FileChange]:
        """Get changes ordered by dependencies and priority."""
        priority_order = {"high": 0, "medium": 1, "low": 2}
        
        # Simple topological sort based on dependencies
        ordered = []
        remaining = list(self.changes)
        applied_paths = set()
        
        while remaining:
            # Find changes with no unmet dependencies
            ready = [
                c for c in remaining
                if all(dep in applied_paths for dep in c.depends_on)
            ]
            
            if not ready:
                # Circular dependency or missing dependency - add remaining
                ready = remaining
            
            # Sort by priority
            ready.sort(key=lambda c: priority_order.get(c.priority, 1))
            
            # Add first ready change
            change = ready[0]
            ordered.append(change)
            applied_paths.add(change.file_path)
            remaining.remove(change)
        
        return ordered
    
    def to_dict(self) -> dict:
        return {
            "instruction": self.instruction,
            "summary": self.summary,
            "total_files": self.total_files,
            "complexity": self.complexity,
            "risks": self.risks,
            "changes": [c.to_dict() for c in self.changes],
        }


@dataclass
class RefactorResult:
    """Result of a multi-file refactoring operation."""
    plan: ChangePlan
    applied: bool = False
    backup_dir: Optional[str] = None
    error: Optional[str] = None
    
    @property
    def success(self) -> bool:
        return self.error is None
    
    @property
    def files_changed(self) -> int:
        return sum(1 for c in self.plan.changes if c.applied)
    
    @property
    def files_failed(self) -> int:
        return sum(1 for c in self.plan.changes if c.error)
    
    @property
    def total_additions(self) -> int:
        return sum(c.diff.additions for c in self.plan.changes if c.diff)
    
    @property
    def total_deletions(self) -> int:
        return sum(c.diff.deletions for c in self.plan.changes if c.diff)
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "applied": self.applied,
            "files_changed": self.files_changed,
            "files_failed": self.files_failed,
            "total_additions": self.total_additions,
            "total_deletions": self.total_deletions,
            "backup_dir": self.backup_dir,
            "error": self.error,
            "plan": self.plan.to_dict(),
        }

