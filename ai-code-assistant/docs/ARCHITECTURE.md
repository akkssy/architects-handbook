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

## User Management System (Phase 1)

### Purpose
Provides configurable settings, privacy controls, usage analytics, and license management. All features can be enabled/disabled to give users full control.

### Components

| File | Purpose |
|------|---------|
| `settings/manager.py` | Privacy settings and configuration management |
| `analytics/collector.py` | Event tracking with privacy controls |
| `analytics/storage.py` | SQLite-based local storage for usage data |
| `licensing/features.py` | License tiers and feature flags |
| `auth/manager.py` | Authentication manager (Phase 1 placeholder) |

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      CLI Commands                               │
│  settings show/set | data show/export/delete | license status   │
└─────────────────────────┬───────────────────────────────────────┘
                          │
         ┌────────────────┼────────────────┬────────────────┐
         ▼                ▼                ▼                ▼
┌─────────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ SettingsManager │ │  Analytics   │ │   License    │ │     Auth     │
│  (settings/)    │ │ (analytics/) │ │ (licensing/) │ │   (auth/)    │
└────────┬────────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
         │                 │                │                │
         └────────────────┬┴────────────────┴────────────────┘
                          ▼
              ┌───────────────────────┐
              │   Local SQLite DB     │
              │  (~/.cognify/*)       │
              └───────────────────────┘
```

### Settings Schema

```yaml
version: "1.0.0"

telemetry:
  enabled: true                 # Master toggle
  share_usage_stats: true       # Command usage statistics
  share_error_reports: true     # Anonymous error reports
  share_feature_usage: true     # Feature usage patterns

analytics:
  enabled: true                 # Local analytics
  local_only: true              # Never sync to cloud
  retention_days: 90            # Auto-cleanup period

authentication:
  enabled: false                # Phase 2 feature
  auto_login: false             # Auto-login on startup

licensing:
  tier: "free"                  # free, pro, team, enterprise
  offline_mode: true            # Work without license server

privacy:
  anonymize_paths: true         # Don't store full file paths
  collect_code_metrics: false   # Don't analyze code content
```

### License Tiers

| Tier | Cloud LLM Calls/Day | Local LLM Calls | Max Agents | History Retention |
|------|---------------------|-----------------|------------|-------------------|
| Free | 100 | Unlimited | 2 | 7 days |
| Pro | Unlimited | Unlimited | 5 | 30 days |
| Team | Unlimited | Unlimited | 10 | 90 days |
| Enterprise | Unlimited | Unlimited | Unlimited | Unlimited |

### Analytics Database Schema

```sql
-- Usage events table
CREATE TABLE usage_events (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,      -- 'command', 'llm_call', 'feature', 'error'
    event_name TEXT NOT NULL,      -- e.g., 'review', 'generate', 'chat'
    metadata TEXT,                  -- JSON blob (no PII)
    provider TEXT,                 -- 'ollama', 'openai', 'groq', etc.
    model TEXT                     -- Model name (no API keys)
);

-- Token usage table
CREATE TABLE token_usage (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER
);

-- Daily statistics (aggregated)
CREATE TABLE daily_stats (
    date TEXT PRIMARY KEY,
    total_commands INTEGER,
    llm_calls INTEGER,
    errors INTEGER
);
```

### Privacy-First Design Principles

1. **Opt-in by default**: Telemetry enabled but can be disabled anytime
2. **Local-first**: All data stored locally in SQLite, no cloud sync by default
3. **No PII collection**: Never store code content, file paths (anonymized), or API keys
4. **Transparent tracking**: `cognify data show` displays all collected data
5. **Right to deletion**: `cognify data delete` permanently removes all analytics
6. **GDPR compliant**: Export (`cognify data export`) and delete functionality

### CLI Commands

```bash
# Settings management
cognify settings show                    # View all settings
cognify settings set <key> <value>       # Change a setting
cognify settings privacy                 # Show privacy-specific settings

# Data management
cognify data show                        # View collected analytics
cognify data export                      # Export data as JSON
cognify data delete                      # Delete all analytics

# License management
cognify license status                   # View license tier and usage
cognify license activate <key>           # Activate license key (Phase 2)
cognify license check                    # Verify license validity

# Authentication (Phase 2)
cognify auth status                      # View auth status
cognify auth login                       # Login to Cognify cloud
cognify auth logout                      # Clear credentials
```

### Integration with Existing Commands

Analytics tracking is integrated into existing commands:

```python
# In smart_chat_command()
analytics.track_command("smart_chat", {
    "provider": provider,
    "model": model,
    "has_context": bool(context)
})

# In review_command()
analytics.track_llm_call(provider, model, tokens_used)

# Usage limit enforcement
if not license_manager.check_limit("cloud_llm_calls"):
    console.print("[red]Daily cloud LLM limit reached[/red]")
    return
```

### VSCode Extension Integration

The VSCode extension integrates with user management through CLI JSON output:

```typescript
// Get settings via CLI
const settings = await cognifyRunner.getSettings();

// Get license status
const license = await cognifyRunner.getLicenseStatus();

// Update status bar with remaining calls
statusBar.setLicenseInfo({
    tier: license.tier,
    remaining: license.remaining_cloud_calls,
    llmCallsToday: license.usage_today.llm_calls_today
});
```
