"""Prompt templates for multi-file refactoring."""

from langchain_core.prompts import ChatPromptTemplate

# System prompt for analyzing refactoring scope
ANALYZE_REFACTOR_SYSTEM = """You are an expert code architect analyzing a codebase for refactoring.

Your task is to analyze the provided code files and determine what changes are needed to accomplish the refactoring goal.

For each file that needs changes, provide:
1. The file path
2. The type of change (modify, create, delete, rename)
3. A description of what changes are needed
4. The priority (high, medium, low)
5. Dependencies on other file changes

Return your analysis as JSON with this structure:
{
    "summary": "Brief description of the refactoring plan",
    "affected_files": [
        {
            "file_path": "path/to/file.py",
            "change_type": "modify|create|delete|rename",
            "description": "What changes are needed",
            "priority": "high|medium|low",
            "depends_on": ["other/file.py"]
        }
    ],
    "risks": ["List of potential risks or breaking changes"],
    "estimated_complexity": "low|medium|high"
}"""

ANALYZE_REFACTOR_PROMPT = ChatPromptTemplate.from_messages([
    ("system", ANALYZE_REFACTOR_SYSTEM),
    ("human", """Analyze the following codebase for this refactoring task:

**Refactoring Goal:** {instruction}

**Files in scope:**
{file_contents}

Analyze what changes are needed and return a JSON plan.""")
])

# System prompt for generating multi-file changes
MULTI_FILE_EDIT_SYSTEM = """You are an expert code refactoring assistant performing coordinated changes across multiple files.

When making changes:
1. Ensure consistency across all files
2. Update all imports and references
3. Maintain backward compatibility where possible
4. Follow existing code style and patterns
5. Add appropriate type hints and docstrings

For each file, return the COMPLETE modified content wrapped in a code block with the filename as a comment."""

MULTI_FILE_EDIT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", MULTI_FILE_EDIT_SYSTEM),
    ("human", """Apply the following refactoring across these files:

**Refactoring Goal:** {instruction}

**Change Plan:**
{change_plan}

**Current File Contents:**
{file_contents}

For each file that needs changes, return the complete modified content in this format:

### FILE: path/to/file.py
```python
# complete file content here
```

### FILE: path/to/another.py
```javascript
// complete file content here
```

Return ALL files that need changes with their complete content.""")
])

# Prompt for renaming symbols across files
RENAME_SYMBOL_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert at renaming symbols across a codebase.

When renaming:
1. Update all occurrences of the symbol
2. Update imports and exports
3. Update docstrings and comments that reference the symbol
4. Preserve all other code exactly as-is

Return each modified file with its complete content."""),
    ("human", """Rename the symbol across these files:

**Old Name:** {old_name}
**New Name:** {new_name}
**Symbol Type:** {symbol_type}

**Files:**
{file_contents}

Return each modified file with complete content in this format:

### FILE: path/to/file.py
```python
# complete file content
```""")
])

# Prompt for extracting code to new file
EXTRACT_TO_FILE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert at extracting code into separate modules.

When extracting:
1. Move the specified code to a new file
2. Add appropriate imports to the new file
3. Update the original file to import from the new location
4. Ensure all references are updated

Return both the new file and modified original file."""),
    ("human", """Extract code to a new file:

**What to Extract:** {instruction}
**New File Path:** {new_file_path}

**Original File ({original_file}):**
```{language}
{original_content}
```

Return both files with complete content:

### FILE: {new_file_path}
```{language}
# new file content
```

### FILE: {original_file}
```{language}
# modified original file
```""")
])

# Prompt for adding feature across multiple files
ADD_FEATURE_MULTI_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert at adding features that span multiple files.

When adding features:
1. Follow existing patterns in the codebase
2. Add necessary imports
3. Update configuration if needed
4. Add appropriate tests structure
5. Maintain consistency with existing code style

Return all files that need to be created or modified."""),
    ("human", """Add the following feature across the codebase:

**Feature Description:** {instruction}

**Existing Files:**
{file_contents}

**Files to Create/Modify:**
{target_files}

Return all files with complete content in this format:

### FILE: path/to/file.py
```python
# complete file content
```""")
])

