# Multi-File Refactoring Feature

**Date:** 2026-01-24  
**Version:** 0.4.0  
**Feature:** Project-Wide Refactoring & Symbol Renaming

## Overview

Added multi-file refactoring capabilities to the AI Code Assistant, enabling coordinated changes across multiple files with dependency tracking, backup support, and dry-run preview.

## New Dependencies

No new dependencies required - uses existing LangChain and Ollama integration.

## New Files

### `src/ai_code_assistant/refactor/`

| File | Purpose |
|------|---------|
| `__init__.py` | Module exports |
| `prompts.py` | Prompt templates for multi-file operations |
| `change_plan.py` | Data structures for change plans |
| `analyzer.py` | Analyzes codebase to determine refactoring scope |
| `multi_file_editor.py` | Coordinates multi-file changes |

### `tests/test_refactor.py`
- 26 comprehensive unit tests
- Tests for change plans, analyzer, and multi-file editor

## Modified Files

### `src/ai_code_assistant/config.py`
- Added `RefactorConfig` class with settings for max files, backup, confirmation

### `config.yaml`
- Added `refactor` configuration section

### `src/ai_code_assistant/cli.py`
- Added `refactor` command for multi-file refactoring
- Added `rename` command for symbol renaming

## New CLI Commands

### Refactor Command
```bash
ai-assist refactor INSTRUCTION [OPTIONS]
```

**Arguments:**
- `INSTRUCTION` - Natural language refactoring instruction

**Options:**
- `--files, -f` - Specific files to include (can be repeated)
- `--pattern, -p` - Glob pattern to match files (e.g., `**/*.py`)
- `--directory, -d` - Directory to search for files (default: `.`)
- `--dry-run` - Show plan without applying changes
- `--no-confirm` - Skip confirmation prompt
- `--no-backup` - Don't create backup
- `--format, -f` - Output format: console, json

**Examples:**
```bash
# Add type hints to all Python files
ai-assist refactor "Add type hints to all functions"

# Rename class across codebase
ai-assist refactor "Rename User class to Account" -p "**/*.py"

# Preview changes without applying
ai-assist refactor "Extract database logic to repository pattern" --dry-run

# Refactor specific directory
ai-assist refactor "Add logging to all API endpoints" -d ./src/api
```

### Rename Command
```bash
ai-assist rename OLD_NAME NEW_NAME [OPTIONS]
```

**Arguments:**
- `OLD_NAME` - Current symbol name
- `NEW_NAME` - New symbol name

**Options:**
- `--type, -t` - Symbol type: function, class, variable, method, symbol
- `--files, -f` - Specific files to include
- `--pattern, -p` - Glob pattern to match files
- `--directory, -d` - Directory to search
- `--dry-run` - Show changes without applying

**Examples:**
```bash
# Rename a class
ai-assist rename UserService AccountService --type class

# Rename a function
ai-assist rename get_user fetch_user --type function -p "**/*.py"

# Preview rename
ai-assist rename API_KEY API_SECRET --type variable --dry-run
```

## Configuration Options

```yaml
refactor:
  max_files: 20              # Maximum files in a refactoring operation
  max_file_size_kb: 500      # Maximum file size to include
  create_backup: true        # Create backup before changes
  require_confirmation: true # Require confirmation before applying
  show_plan: true            # Show refactoring plan before execution
```

## Architecture

```
User Instruction → Analyzer → Change Plan → Multi-File Editor → Apply Changes
                      ↓              ↓              ↓
                 Read Files    Order by Deps    Generate Diffs
                      ↓              ↓              ↓
                 LLM Analysis   Validate Plan   Create Backup
```

## Key Classes

- `MultiFileEditor` - Main coordinator for multi-file operations
- `RefactorAnalyzer` - Analyzes codebase to create change plans
- `ChangePlan` - Represents a complete refactoring plan
- `FileChange` - Individual file change with type, content, and status
- `ChangeType` - Enum: MODIFY, CREATE, DELETE, RENAME
- `RefactorResult` - Result of refactoring with statistics

## Change Types

| Type | Description |
|------|-------------|
| `modify` | Modify existing file content |
| `create` | Create a new file |
| `delete` | Delete an existing file |
| `rename` | Rename/move a file |

## Features

### Dependency Tracking
Changes are ordered based on dependencies to ensure correct application order.

### Backup Support
Creates timestamped backup directory before applying changes.

### Dry Run Mode
Preview all changes without modifying files.

### Confirmation Prompt
Requires user confirmation before applying changes (configurable).

### JSON Output
Machine-readable output for integration with other tools.

