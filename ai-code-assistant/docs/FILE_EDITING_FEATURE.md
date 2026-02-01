# File Editing Feature

**Date:** 2026-01-24  
**Version:** 0.3.0  
**Feature:** AI-Powered File Editing

## Overview

Added AI-powered file editing capabilities to the AI Code Assistant, enabling natural language instructions to modify code files with diff preview and backup support.

## New Dependencies

No new dependencies required - uses existing LangChain and Ollama integration.

## New Files

### `src/ai_code_assistant/editor/`

| File | Purpose |
|------|---------|
| `__init__.py` | Module exports |
| `prompts.py` | Prompt templates for different edit modes |
| `diff_handler.py` | Diff generation and formatting |
| `file_editor.py` | Main file editing logic |

### `tests/test_editor.py`
- 23 comprehensive unit tests
- Tests for diff handling, edit results, and file operations

## Modified Files

### `src/ai_code_assistant/config.py`
- Added `EditorConfig` class with settings for backup, diff display, file size limits

### `config.yaml`
- Added `editor` configuration section

### `src/ai_code_assistant/cli.py`
- Added `edit` command with preview, backup, and format options

## New CLI Command

### Edit Command
```bash
ai-assist edit FILE INSTRUCTION [OPTIONS]
```

**Arguments:**
- `FILE` - Path to the file to edit
- `INSTRUCTION` - Natural language edit instruction

**Options:**
- `--mode, -m` - Edit mode: edit, refactor, fix, add (default: edit)
- `--preview, -p` - Preview changes without applying
- `--no-backup` - Don't create backup file
- `--format, -f` - Output format: console, json
- `--start-line, -s` - Start line for targeted edit
- `--end-line, -e` - End line for targeted edit

**Examples:**
```bash
# Add error handling
ai-assist edit main.py "Add error handling to the parse function"

# Refactor code
ai-assist edit utils.py "Add type hints" --mode refactor

# Fix a bug
ai-assist edit app.py "Fix the null pointer bug" --mode fix

# Preview changes
ai-assist edit api.py "Add logging" --preview

# Targeted edit
ai-assist edit config.py "Update the timeout value" -s 10 -e 20
```

## Configuration Options

```yaml
editor:
  create_backup: true      # Create backup before editing
  show_diff: true          # Show diff before applying
  max_file_size_kb: 500    # Maximum file size to edit
  auto_format: false       # Auto-format after editing
```

## Architecture

```
User Instruction → Prompt Selection → LLM → Code Extraction → Diff Generation
                                                    ↓
                                            Backup Creation → File Write
```

## Key Classes

- `FileEditor` - Main editor class with file and code editing methods
- `EditResult` - Result of an edit operation with success/error status
- `DiffHandler` - Generates and formats unified diffs
- `DiffResult` - Contains diff information with additions/deletions count
- `DiffHunk` - Represents a section of changes in a diff
- `DiffLine` - Individual line in a diff

## Edit Modes

| Mode | Description |
|------|-------------|
| `edit` | General-purpose editing (default) |
| `targeted` | Edit specific line range |
| `refactor` | Structural improvements |
| `fix` | Bug fixes with minimal changes |
| `add` | Add new features |

## Prompt Templates

Each edit mode has a specialized prompt template:
- `EDIT_PROMPT` - General editing
- `TARGETED_EDIT_PROMPT` - Line-specific edits
- `REFACTOR_PROMPT` - Code refactoring
- `FIX_PROMPT` - Bug fixing
- `ADD_FEATURE_PROMPT` - Feature addition

