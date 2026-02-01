# Architecture Deep Dive

This document explains the technical architecture of the AI Code Assistant for developers who want to understand or extend the codebase.

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI (cli.py)                             │
│  Commands: review, generate, chat, edit, refactor, rename        │
└─────────────────────────┬───────────────────────────────────────┘
                          │
         ┌────────────────┼────────────────┬────────────────┐
         ▼                ▼                ▼                ▼
┌─────────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  CodeAnalyzer   │ │CodeGenerator │ │ ChatSession  │ │MultiFileEdit │
│  (reviewer/)    │ │ (generator/) │ │   (chat/)    │ │ (refactor/)  │
└────────┬────────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
         │                 │                │                │
         └────────────────┬┴────────────────┴────────────────┘
                          ▼
              ┌───────────────────────┐
              │     LLMManager        │
              │       (llm.py)        │
              └───────────┬───────────┘
                          │
              ┌───────────▼───────────┐
              │   LangChain + Ollama  │
              │   (Local LLM Server)  │
              └───────────────────────┘
```

## Data Flow

### Code Review Flow

```
1. User runs: ai-code review myfile.py
                    │
2. CLI parses args  ▼
   ┌─────────────────────────────────┐
   │ cli.py: review_command()        │
   │ - Load config                   │
   │ - Create LLMManager             │
   │ - Create CodeAnalyzer           │
   └─────────────┬───────────────────┘
                 │
3. Read file     ▼
   ┌─────────────────────────────────┐
   │ analyzer.py: review_file()      │
   │ - Read source code from disk    │
   │ - Detect language from extension│
   └─────────────┬───────────────────┘
                 │
4. Build prompt  ▼
   ┌─────────────────────────────────┐
   │ prompts.py: build_review_prompt │
   │ - Insert code into template     │
   │ - Add focus areas (bugs, etc)   │
   └─────────────┬───────────────────┘
                 │
5. Call LLM      ▼
   ┌─────────────────────────────────┐
   │ llm.py: invoke()                │
   │ - Create SystemMessage          │
   │ - Create HumanMessage           │
   │ - Send to Ollama via LangChain  │
   └─────────────┬───────────────────┘
                 │
6. Parse JSON    ▼
   ┌─────────────────────────────────┐
   │ analyzer.py: _parse_response()  │
   │ - Extract JSON from markdown    │
   │ - Repair common JSON errors     │
   │ - Validate structure            │
   │ - Create ReviewResult object    │
   └─────────────┬───────────────────┘
                 │
7. Format output ▼
   ┌─────────────────────────────────┐
   │ formatters.py                   │
   │ - ConsoleFormatter (default)    │
   │ - MarkdownFormatter             │
   │ - JsonFormatter                 │
   └─────────────────────────────────┘
```

## Module Details

### 1. Configuration System (`config.py`)

**Purpose**: Centralized configuration with multiple sources.

**Configuration Hierarchy** (highest priority first):
1. Command-line arguments
2. Environment variables (`AI_ASSISTANT_*`)
3. Config file (`config.yaml`)
4. Default values in code

```python
# Pydantic BaseSettings automatically handles:
# - Type validation
# - Environment variable binding
# - Default values

class Config(BaseSettings):
    llm: LLMConfig = LLMConfig()
    review: ReviewConfig = ReviewConfig()
    generation: GenerationConfig = GenerationConfig()
    
    class Config:
        env_prefix = "AI_ASSISTANT_"  # AI_ASSISTANT_LLM_MODEL=xxx
```

### 2. LLM Manager (`llm.py`)

**Purpose**: Abstract away LLM communication details.

**Key Design Decisions**:
- **Lazy initialization**: LLM connection created on first use
- **Message-based API**: Uses LangChain's message types
- **Streaming support**: For real-time output in chat mode

```python
class LLMManager:
    def __init__(self, config: LLMConfig):
        self._config = config
        self._llm = None  # Lazy init
    
    @property
    def llm(self) -> ChatOllama:
        if self._llm is None:
            self._llm = ChatOllama(
                model=self._config.model,
                base_url=self._config.base_url,
                temperature=self._config.temperature,
            )
        return self._llm
```

### 3. Code Analyzer (`reviewer/analyzer.py`)

**Purpose**: Analyze code and produce structured review results.

**JSON Parsing Strategy**:
LLMs don't always produce valid JSON. We handle this with:

1. **Markdown extraction**: Find JSON in ```json code blocks
2. **Direct extraction**: Find `{...}` patterns
3. **JSON repair**: Fix common errors (trailing commas, unquoted keys)
4. **Retry on failure**: Ask LLM to fix its response

```python
def _extract_json(self, text: str) -> Optional[dict]:
    # Try: markdown code block
    if match := re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL):
        return json.loads(match.group(1))
    
    # Try: raw JSON object
    if match := re.search(r'\{.*\}', text, re.DOTALL):
        return json.loads(match.group())
    
    # Try: repair and parse
    return self._repair_json(text)
```

### 4. Code Generator (`generator/code_gen.py`)

**Purpose**: Generate code from natural language descriptions.

**Generation Modes**:
- `function`: Single function with docstring
- `class`: Class with methods
- `script`: Complete runnable script
- `test`: Unit tests for given code
- `generic`: Freeform generation

**Code Extraction**:
LLM responses often include explanation text. We extract just the code:

```python
def _extract_code(self, response: str, language: str) -> str:
    # Try language-specific block: ```python
    pattern = rf'```{language}\s*(.*?)\s*```'
    if match := re.search(pattern, response, re.DOTALL):
        return match.group(1).strip()
    
    # Try generic block: ```
    if match := re.search(r'```\s*(.*?)\s*```', response, re.DOTALL):
        return match.group(1).strip()
    
    # No code block, return as-is
    return response.strip()
```

### 5. Chat Session (`chat/session.py`)

**Purpose**: Maintain conversation context for multi-turn interactions.

**Key Features**:
- Conversation history maintained in memory
- System prompt sets assistant personality
- Streaming responses for better UX

```python
class ChatSession:
    def __init__(self, llm_manager: LLMManager):
        self.llm_manager = llm_manager
        self.history: List[BaseMessage] = []
        self.system_prompt = "You are a helpful coding assistant..."

    def chat(self, user_input: str) -> str:
        # Add user message to history
        self.history.append(HumanMessage(content=user_input))

        # Get response with full history context
        response = self.llm_manager.invoke_with_history(
            self.history,
            self.system_prompt
        )

        # Add assistant response to history
        self.history.append(AIMessage(content=response))
        return response
```

### 6. Output Formatters (`utils/formatters.py`)

**Purpose**: Present results in different formats.

**Strategy Pattern Implementation**:

```python
class BaseFormatter(ABC):
    """Abstract base class defining the interface."""

    @abstractmethod
    def format_review(self, result: ReviewResult) -> str:
        pass

    @abstractmethod
    def format_generation(self, result: GenerationResult) -> str:
        pass

class ConsoleFormatter(BaseFormatter):
    """Rich terminal output with colors and tables."""

class MarkdownFormatter(BaseFormatter):
    """Markdown for documentation/reports."""

class JsonFormatter(BaseFormatter):
    """Machine-readable JSON output."""

def get_formatter(format_type: str) -> BaseFormatter:
    """Factory function to get appropriate formatter."""
    formatters = {
        "console": ConsoleFormatter,
        "markdown": MarkdownFormatter,
        "json": JsonFormatter,
    }
    return formatters.get(format_type.lower(), ConsoleFormatter)()
```

## Prompt Engineering

### Review Prompt Structure

```
┌─────────────────────────────────────────┐
│ SYSTEM PROMPT                           │
│ - Role: "Expert code reviewer"          │
│ - Categories to check                   │
│ - Output format (JSON schema)           │
│ - Severity levels                       │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ USER PROMPT                             │
│ - Language: Python                      │
│ - Focus areas: bugs, security, style    │
│ - The actual code to review             │
└─────────────────────────────────────────┘
```

### Why JSON Output?

1. **Structured data** - Easy to parse programmatically
2. **Consistent format** - Same fields every time
3. **Validation** - Can verify response completeness
4. **Flexibility** - Easy to format differently for display

## Error Handling Strategy

### Graceful Degradation

```python
def review_file(self, file_path: str) -> ReviewResult:
    try:
        code = self._read_file(file_path)
    except FileNotFoundError:
        return ReviewResult(error="File not found", ...)
    except Exception as e:
        return ReviewResult(error=f"Read error: {e}", ...)

    try:
        response = self.llm_manager.invoke(prompt)
        return self._parse_response(response)
    except json.JSONDecodeError:
        # Try to repair JSON
        return self._retry_with_repair(response)
    except Exception as e:
        return ReviewResult(error=f"Analysis failed: {e}", ...)
```

### Retry Logic for JSON Parsing

When LLM returns invalid JSON:
1. Attempt automatic repair (trailing commas, etc.)
2. If repair fails, ask LLM to correct its response
3. Return error result if all attempts fail

## Testing Strategy

### Unit Test Coverage

| Module | Tests | Coverage Focus |
|--------|-------|----------------|
| config.py | 7 | Loading, defaults, validation |
| llm.py | 9 | Mocked LLM calls, error handling |
| analyzer.py | 11 | JSON parsing, edge cases |
| code_gen.py | 13 | Code extraction, modes |
| file_handler.py | 19 | File ops, ignore patterns |
| formatters.py | 18 | All format types |
| refactor/ | 26 | Change plans, multi-file editing |

### Mocking External Dependencies

```python
@pytest.fixture
def mock_llm_manager(mocker):
    """Mock LLM to avoid real API calls in tests."""
    manager = mocker.Mock(spec=LLMManager)
    manager.invoke.return_value = '''```json
    {"summary": "Test summary", "issues": []}
    ```'''
    return manager

def test_review_success(mock_llm_manager):
    analyzer = CodeAnalyzer(config, mock_llm_manager)
    result = analyzer.review_code("def foo(): pass", "python")
    assert result.summary == "Test summary"
```

## Performance Considerations

### LLM Call Optimization

1. **Lazy initialization** - Don't connect until needed
2. **Streaming** - Show output as it's generated in chat mode
3. **Appropriate models** - Smaller models for simple tasks

### File Handling

1. **Size limits** - Reject files over configurable max size
2. **Ignore patterns** - Skip `node_modules`, `.git`, etc.
3. **Batch operations** - Process multiple files efficiently

## Security Considerations

1. **Local execution** - Code never sent to external servers
2. **No code execution** - Only analysis, never runs user code
3. **Input validation** - File paths sanitized
4. **Configurable limits** - Max file size, timeout settings

## Multi-File Refactoring (`refactor/`)

### Purpose
Coordinate changes across multiple files with dependency tracking and backup support.

### Components

| File | Purpose |
|------|---------|
| `change_plan.py` | Data structures for change plans |
| `analyzer.py` | Analyzes codebase to determine refactoring scope |
| `multi_file_editor.py` | Coordinates multi-file changes |
| `prompts.py` | Prompt templates for multi-file operations |

### Refactoring Flow

```
1. User runs: ai-assist refactor "Add type hints"
                    │
2. Collect files    ▼
   ┌─────────────────────────────────┐
   │ MultiFileEditor.refactor()      │
   │ - Collect files from pattern    │
   │ - Read file contents            │
   └─────────────┬───────────────────┘
                 │
3. Analyze       ▼
   ┌─────────────────────────────────┐
   │ RefactorAnalyzer.analyze()      │
   │ - Send files to LLM             │
   │ - Parse change plan             │
   │ - Identify dependencies         │
   └─────────────┬───────────────────┘
                 │
4. Generate      ▼
   ┌─────────────────────────────────┐
   │ MultiFileEditor._generate()     │
   │ - Generate new file contents    │
   │ - Create diffs                  │
   └─────────────┬───────────────────┘
                 │
5. Apply         ▼
   ┌─────────────────────────────────┐
   │ MultiFileEditor._apply()        │
   │ - Create backup                 │
   │ - Apply changes in order        │
   │ - Report results                │
   └─────────────────────────────────┘
```

### Change Types

- **MODIFY** - Modify existing file content
- **CREATE** - Create a new file
- **DELETE** - Delete an existing file
- **RENAME** - Rename/move a file

See [REFACTOR_FEATURE.md](./REFACTOR_FEATURE.md) for detailed documentation.
