"""Multi-file refactoring module for AI Code Assistant."""

from ai_code_assistant.refactor.change_plan import (
    ChangePlan,
    FileChange,
    ChangeType,
    RefactorResult,
)
from ai_code_assistant.refactor.multi_file_editor import MultiFileEditor
from ai_code_assistant.refactor.analyzer import RefactorAnalyzer

__all__ = [
    "ChangePlan",
    "FileChange",
    "ChangeType",
    "RefactorResult",
    "MultiFileEditor",
    "RefactorAnalyzer",
]

