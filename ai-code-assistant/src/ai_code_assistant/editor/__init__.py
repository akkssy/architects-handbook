"""File editing module for AI Code Assistant."""

from ai_code_assistant.editor.file_editor import FileEditor, EditResult
from ai_code_assistant.editor.diff_handler import DiffHandler, DiffResult
from ai_code_assistant.editor.prompts import EDIT_PROMPTS

__all__ = ["FileEditor", "EditResult", "DiffHandler", "DiffResult", "EDIT_PROMPTS"]

