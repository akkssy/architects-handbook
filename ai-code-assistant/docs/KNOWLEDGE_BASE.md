# Cognify AI - Complete Knowledge Base

> **Purpose**: This document serves as a comprehensive onboarding guide for AI agents and developers working with the Cognify AI codebase. It captures all architectural decisions, implementation patterns, and project context.

---

## Executive Summary

**Cognify AI** is an AI-powered code assistant available as both a **Python CLI tool** and a **VSCode extension**. It provides code review, generation, editing, refactoring, and semantic search capabilities using local LLMs (via Ollama) or cloud providers (Google AI, Groq, Cerebras, OpenRouter, OpenAI).

### Key Capabilities
- 🔍 **Code Review** - Analyze code for bugs, security issues, and style problems
- ⚡ **Code Generation** - Generate functions, classes, and tests from natural language
- 🔎 **Semantic Search** - Search codebase using natural language (RAG)
- ✏️ **AI File Editing** - Edit files with natural language instructions
- 🔄 **Multi-File Refactor** - Refactor across multiple files
- 💬 **Interactive Chat** - Chat with AI about your code
- 🖥️ **VSCode Extension** - Full IDE integration with sidebar chat

---

## Quick Reference

### Key File Locations

| Component | Path | Description |
|-----------|------|-------------|
| CLI Entry Point | `src/ai_code_assistant/cli.py` | All CLI commands |
| Configuration | `src/ai_code_assistant/config.py` | Pydantic config classes |
| LLM Manager | `src/ai_code_assistant/llm.py` | LangChain/Ollama integration |
| Code Reviewer | `src/ai_code_assistant/reviewer/` | Code analysis module |
| Code Generator | `src/ai_code_assistant/generator/` | Code generation module |
| Chat Session | `src/ai_code_assistant/chat/` | Interactive chat |
| File Editor | `src/ai_code_assistant/editor/` | AI file editing |
| Refactor | `src/ai_code_assistant/refactor/` | Multi-file refactoring |
| RAG/Search | `src/ai_code_assistant/retrieval/` | Semantic search & indexing |
| Utilities | `src/ai_code_assistant/utils/` | File handling, formatters |
| VSCode Extension | `vscode-extension/` | TypeScript extension |
| Tests | `tests/` | 144 unit tests |
| Documentation | `docs/` | Markdown & HTML docs |

### CLI Commands Quick Reference

```bash
# Core Commands
cognify status                    # Check connection status
cognify review <file>             # Review code
cognify generate "<description>"  # Generate code
cognify chat                      # Interactive chat
cognify edit <file> "<instruction>" # Edit file with AI
cognify refactor "<instruction>"  # Multi-file refactor
cognify rename <old> <new>        # Rename symbols

# RAG/Search Commands
cognify index .                   # Index codebase
cognify search "<query>"          # Semantic search

# Provider Commands
cognify providers                 # List providers
cognify use-provider <name>       # Switch provider
cognify test-provider             # Test connection
```

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **LLM Framework** | LangChain | Orchestration, prompts, chains |
| **Local LLM** | Ollama | Local model inference |
| **Cloud LLMs** | Google AI, Groq, OpenRouter, OpenAI | Cloud inference |
| **Vector Database** | ChromaDB | Semantic search storage |
| **Embeddings** | Sentence Transformers | Code embeddings (all-MiniLM-L6-v2) |
| **CLI Framework** | Click + Rich | Command-line interface |
| **Configuration** | Pydantic + YAML | Type-safe config management |
| **Testing** | Pytest | Unit testing |
| **VSCode Extension** | TypeScript | IDE integration |

### Python Dependencies (pyproject.toml)

```toml
dependencies = [
    "langchain>=0.1.0",
    "langchain-ollama>=0.1.0",
    "langchain-core>=0.1.0",
    "click>=8.1.0",
    "rich>=13.0.0",
    "pyyaml>=6.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "chromadb>=1.0.0",
    "sentence-transformers>=2.0.0",
    "watchdog>=4.0.0",
]
```

---

## Architecture Overview

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
         └─────────────────┴────────────────┴────────────────┘
                                    │
                          ┌─────────▼─────────┐
                          │    LLMManager     │
                          │     (llm.py)      │
                          └─────────┬─────────┘
                                    │
                          ┌─────────▼─────────┐
                          │  Provider Layer   │
                          │ Ollama/Cloud APIs │
                          └───────────────────┘
```

### Data Flow Example (Code Review)

```
1. User runs: cognify review myfile.py
2. CLI parses args → loads config → creates LLMManager
3. CodeAnalyzer reads file → builds prompt with code
4. LLMManager sends to Ollama/Cloud provider
5. Response parsed → JSON extracted → ReviewResult created
6. Formatter outputs to console/markdown/JSON
```

---

## Module Deep Dive

### 1. Configuration System (`config.py`)

**Design Pattern**: Pydantic BaseSettings with hierarchical config

**Configuration Hierarchy** (highest priority first):
1. Command-line arguments
2. Environment variables (`AI_ASSISTANT_*`)
3. Config file (`config.yaml`)
4. Default values in code

**Key Config Classes**:

```python
class LLMConfig(BaseModel):
    provider: str = "ollama"           # ollama, google, groq, etc.
    model: str = "deepseek-coder:6.7b"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.1
    max_tokens: int = 4096
    timeout: int = 120

class ReviewConfig(BaseModel):
    severity_levels: List[str] = ["critical", "warning", "suggestion"]
    categories: List[str] = ["bugs", "security", "performance", "style"]
    max_file_size_kb: int = 500

class GenerationConfig(BaseModel):
    include_type_hints: bool = True
    include_docstrings: bool = True
    default_mode: str = "function"

class RetrievalConfig(BaseModel):
    embedding_model: str = "all-MiniLM-L6-v2"
    persist_directory: str = ".ai-assistant-index"
    chunk_size: int = 50

class EditorConfig(BaseModel):
    create_backup: bool = True
    show_diff: bool = True

class RefactorConfig(BaseModel):
    max_files: int = 20
    require_confirmation: bool = True
```

**Config File Locations** (searched in order):
1. `./config.yaml`
2. `./.ai-code-assistant.yaml`
3. `~/.ai-code-assistant/config.yaml`
4. `~/.config/ai-code-assistant/config.yaml`

---

### 2. LLM Manager (`llm.py`)

**Design Pattern**: Lazy initialization, adapter pattern

**Key Features**:
- Lazy LLM connection (created on first use)
- Message-based API using LangChain types
- Streaming support for real-time output
- Template-based invocation

```python
class LLMManager:
    def __init__(self, config: Config):
        self.config = config
        self._llm: Optional[BaseChatModel] = None

    @property
    def llm(self) -> BaseChatModel:
        """Lazy initialization of LLM."""
        if self._llm is None:
            self._llm = ChatOllama(
                model=self.config.llm.model,
                base_url=self.config.llm.base_url,
                temperature=self.config.llm.temperature,
            )
        return self._llm

    def invoke(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Send prompt to LLM and get response."""
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        return str(self.llm.invoke(messages).content)

    def stream(self, prompt: str, system_prompt: Optional[str] = None):
        """Stream response for real-time output."""
        for chunk in self.llm.stream(messages):
            yield str(chunk.content)
```

---

### 3. Code Reviewer (`reviewer/`)

**Files**:
- `analyzer.py` - Main CodeAnalyzer class
- `prompts.py` - Review prompt templates

**Key Class**: `CodeAnalyzer`

```python
class CodeAnalyzer:
    def review_file(self, file_path: Path, ...) -> ReviewResult:
        """Review a file for issues."""

    def review_code(self, code: str, language: str, ...) -> ReviewResult:
        """Review code string directly."""
```

**ReviewResult Structure**:
```python
@dataclass
class ReviewResult:
    issues: List[Issue]
    summary: str
    file_path: str
    language: str

@dataclass
class Issue:
    severity: str      # critical, warning, suggestion
    category: str      # bugs, security, performance, style
    line_number: int
    message: str
    suggestion: str
    confidence: float
```

---

### 4. Code Generator (`generator/`)

**Files**:
- `code_gen.py` - Main CodeGenerator class
- `prompts.py` - Generation prompt templates

**Generation Modes**:
- `function` - Generate a single function
- `class` - Generate a class with methods
- `test` - Generate unit tests
- `script` - Generate a complete script
- `generic` - Free-form generation

```python
class CodeGenerator:
    def generate_function(self, description: str, language: str) -> GenerationResult
    def generate_class(self, description: str, language: str) -> GenerationResult
    def generate_test(self, description: str, language: str) -> GenerationResult
    def generate(self, description: str, language: str) -> GenerationResult
```

---

### 5. Chat Session (`chat/`)

**Files**:
- `session.py` - ChatSession class

**Features**:
- Conversation history management
- Code context loading
- Streaming responses
- Export to markdown

```python
class ChatSession:
    def __init__(self, config: Config, llm_manager: LLMManager):
        self.history: List[Message] = []
        self._code_context: Dict[str, str] = {}  # filename -> code

    def add_code_context(self, filename: str, code: str) -> None
    def load_file_context(self, file_path: Path) -> bool
    def send_message(self, user_input: str, stream: bool = False)
    def clear_history(self) -> None
    def export_history(self) -> str
```

**Chat Commands**:
- `/load <file>` - Load file as context
- `/clear` - Clear history
- `/context` - Show loaded files
- `/export` - Export to markdown
- `/quit` - Exit chat

---

### 6. File Editor (`editor/`)

**Files**:
- `file_editor.py` - Main FileEditor class
- `diff_handler.py` - Diff generation and application
- `prompts.py` - Edit prompt templates

**Edit Modes**:
- `refactor` - Improve code structure
- `fix` - Fix bugs
- `enhance` - Add features
- `targeted` - Edit specific line range

```python
class FileEditor:
    def edit_file(self, file_path: Path, instruction: str,
                  mode: str = "refactor", preview: bool = True) -> EditResult
```

**EditResult Structure**:
```python
@dataclass
class EditResult:
    original_code: str
    edited_code: str
    diff: str
    changes_made: List[str]
    success: bool
```

---

### 7. Multi-File Refactor (`refactor/`)

**Files**:
- `multi_file_editor.py` - Main MultiFileEditor class
- `change_plan.py` - Change planning
- `analyzer.py` - Code analysis
- `prompts.py` - Refactor prompts

```python
class MultiFileEditor:
    def refactor(self, instruction: str, files: List[Path],
                 dry_run: bool = False) -> RefactorResult
```

---

### 8. RAG/Semantic Search (`retrieval/`)

**Files**:
- `indexer.py` - CodebaseIndexer for building index
- `search.py` - CodebaseSearch for querying
- `chunker.py` - CodeChunker for splitting code

**Architecture**:
```
Code Files → Chunker → Embeddings → ChromaDB
                                        ↓
Query → Embedding → Similarity Search → Results
```

```python
class CodebaseIndexer:
    def index_directory(self, directory: Path) -> IndexStats
    def update_file(self, file_path: Path) -> None
    def remove_file(self, file_path: Path) -> None

class CodebaseSearch:
    def search(self, query: str, k: int = 5) -> List[SearchResult]
```

**Index Configuration**:
```python
@dataclass
class IndexConfig:
    embedding_model: str = "all-MiniLM-L6-v2"
    persist_directory: str = ".ai-assistant-index"
    collection_name: str = "codebase"
    extensions: Set[str] = {".py", ".js", ".ts", ...}
```

---

### 9. Utilities (`utils/`)

**Files**:
- `file_handler.py` - File operations
- `formatters.py` - Output formatters

**Formatters**:
- `ConsoleFormatter` - Rich terminal output
- `MarkdownFormatter` - Markdown files
- `JsonFormatter` - JSON output

```python
def get_formatter(format_type: str) -> BaseFormatter:
    formatters = {
        "console": ConsoleFormatter,
        "markdown": MarkdownFormatter,
        "json": JsonFormatter,
    }
    return formatters[format_type]()
```

---

## VSCode Extension Architecture

The VSCode extension provides full IDE integration through a TypeScript codebase.

### Extension Structure

```
vscode-extension/
├── src/
│   ├── extension.ts      # Main activation & command registration
│   ├── cognifyRunner.ts  # CLI execution wrapper
│   ├── sidebarChat.ts    # WebviewViewProvider for sidebar
│   ├── chatPanel.ts      # Full chat panel implementation
│   ├── statusBar.ts      # Status bar manager
│   └── diagnostics.ts    # Diagnostics/issues display
├── images/
│   └── icon.png          # Extension icon (atom design)
├── package.json          # Extension manifest
└── tsconfig.json         # TypeScript configuration
```

### Key Components

#### 1. Extension Entry Point (`extension.ts`)

**Activation**:
```typescript
export function activate(context: vscode.ExtensionContext) {
    // Initialize components
    cognifyRunner = new CognifyRunner();
    statusBarManager = new StatusBarManager();
    diagnosticsManager = new DiagnosticsManager();

    // Register commands
    const commands = [
        vscode.commands.registerCommand('cognify.reviewFile', () => reviewFile()),
        vscode.commands.registerCommand('cognify.generateCode', () => generateCode()),
        vscode.commands.registerCommand('cognify.openChat', () => openChat(context)),
        // ... more commands
    ];
}
```

**Registered Commands**:
- `cognify.reviewFile` - Review active file
- `cognify.reviewSelection` - Review selected code
- `cognify.generateCode` - Generate code from description
- `cognify.editCode` - Edit code with instructions
- `cognify.explainCode` - Explain selected code
- `cognify.openChat` - Open chat panel
- `cognify.checkStatus` - Check connection status
- `cognify.switchProvider` - Switch LLM provider

#### 2. CognifyRunner (`cognifyRunner.ts`)

Executes CLI commands via child processes:

```typescript
export class CognifyRunner {
    private async runCommand(args: string[]): Promise<string> {
        return new Promise((resolve, reject) => {
            const proc = spawn('cognify', args, {
                cwd: workspaceFolder,
                env: { ...process.env }
            });
            // Handle stdout, stderr, exit code
        });
    }

    async reviewFile(filePath: string): Promise<ReviewResult>
    async generateCode(description: string, language: string): Promise<GenerateResult>
    async editCode(code: string, instruction: string, language: string): Promise<GenerateResult>
    async chat(message: string, context?: string): Promise<string>
}
```

#### 3. SidebarChatProvider (`sidebarChat.ts`)

Implements `WebviewViewProvider` for the sidebar chat:

```typescript
export class SidebarChatProvider implements vscode.WebviewViewProvider {
    private _currentContext: { filename: string; code: string; } | undefined;

    resolveWebviewView(webviewView: vscode.WebviewView) {
        // Set up HTML with chat interface
        // Handle messages from webview
    }

    private async _addContext() {
        const editor = vscode.window.activeTextEditor;
        // Get selected text or entire file
        // Store in _currentContext
        // Show badge in UI
    }

    private async _sendMessage(message: string) {
        // Include context if available
        // Send to CLI via CognifyRunner
        // Display response
        // Clear context after send
    }
}
```

#### 4. StatusBarManager (`statusBar.ts`)

Manages status bar display:

```typescript
class StatusBarManager {
    setReady()    // Shows "$(check) Cognify"
    setLoading(text: string)  // Shows spinner with text
    setError()    // Shows "$(alert) Cognify"
}
```

### Extension Configuration (`package.json`)

```json
{
  "configuration": {
    "properties": {
      "cognify.provider": {
        "type": "string",
        "default": "ollama",
        "enum": ["ollama", "groq", "google", "cerebras", "openrouter", "openai"]
      },
      "cognify.model": {
        "type": "string",
        "default": "deepseek-coder:6.7b"
      },
      "cognify.autoContext": {
        "type": "boolean",
        "default": true
      },
      "cognify.maxContextTokens": {
        "type": "number",
        "default": 8000
      }
    }
  }
}
```

### Communication Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    VSCode Extension                              │
│  ┌────────────┐    ┌───────────────┐    ┌──────────────┐       │
│  │  Webview   │───▶│ Extension.ts  │───▶│CognifyRunner │       │
│  │ (HTML/JS)  │◀───│   Handlers    │◀───│  (spawn)     │       │
│  └────────────┘    └───────────────┘    └──────┬───────┘       │
└──────────────────────────────────────────────────┼──────────────┘
                                                   │
                                            spawn process
                                                   │
                                                   ▼
                                          ┌───────────────┐
                                          │  Cognify CLI  │
                                          │  (Python)     │
                                          └───────┬───────┘
                                                  │
                                                  ▼
                                          ┌───────────────┐
                                          │ LLM Provider  │
                                          │ Ollama/Cloud  │
                                          └───────────────┘
```

---

## Provider System

The system supports multiple LLM providers:

| Provider | Type | Free Tier | Setup |
|----------|------|-----------|-------|
| **Ollama** | Local | ✅ Yes | `ollama pull deepseek-coder:6.7b` |
| **Groq** | Cloud | ✅ Yes | `export GROQ_API_KEY=...` |
| **Google AI** | Cloud | ✅ Yes | `export GOOGLE_API_KEY=...` |
| **Cerebras** | Cloud | ✅ Yes | `export CEREBRAS_API_KEY=...` |
| **OpenRouter** | Cloud | Per-model | `export OPENROUTER_API_KEY=...` |
| **OpenAI** | Cloud | ❌ No | `export OPENAI_API_KEY=...` |

### Switching Providers

**CLI**:
```bash
cognify providers                    # List available providers
cognify use-provider groq           # Switch to Groq
cognify test-provider               # Test connection
```

**VSCode**:
- Command Palette → "Cognify: Switch Provider"
- Or update settings: `cognify.provider`

### Recommended Models

| Provider | Recommended Model | Use Case |
|----------|-------------------|----------|
| Ollama | `deepseek-coder:6.7b` | General coding |
| Ollama | `codellama:7b` | Code completion |
| Groq | `llama-3.1-70b-versatile` | High quality |
| Google | `gemini-1.5-pro` | Long context |

---

## Testing Approach

### Test Structure

```
tests/
├── test_cli.py              # CLI command tests
├── test_config.py           # Configuration tests
├── test_llm.py              # LLM manager tests
├── test_reviewer.py         # Code review tests
├── test_generator.py        # Code generation tests
├── test_chat.py             # Chat session tests
├── test_editor.py           # File editing tests
├── test_refactor.py         # Refactoring tests
├── test_retrieval.py        # RAG/search tests
└── conftest.py              # Fixtures
```

### Running Tests

```bash
# Run all tests
PYTHONPATH=src pytest tests/ -v

# Run with coverage
PYTHONPATH=src pytest tests/ --cov=ai_code_assistant

# Run specific test file
PYTHONPATH=src pytest tests/test_reviewer.py -v

# Run tests matching pattern
PYTHONPATH=src pytest tests/ -k "test_review" -v
```

### Test Count: **144 unit tests**

---

## Documentation Structure

### Markdown Files (`docs/`)

| File | Description |
|------|-------------|
| `ARCHITECTURE.md` | System architecture overview |
| `PROVIDERS.md` | LLM provider setup guide |
| `FILE_EDITING_FEATURE.md` | File editing documentation |
| `REFACTOR_FEATURE.md` | Multi-file refactoring guide |
| `RETRIEVAL_FEATURE.md` | RAG/semantic search guide |
| `CHANGELOG_RETRIEVAL.md` | Retrieval feature changelog |
| `KNOWLEDGE_BASE.md` | This document |

### HTML Generation

HTML docs are generated with dark theme using `generate_html.py`:

```bash
python docs/generate_html.py
```

This creates styled HTML versions of all markdown files with:
- Dark theme (#1a1a2e background)
- Syntax highlighting
- Responsive design
- Table of contents

### GitHub Pages

Documentation deployed at: `https://akkssy.github.io/cognify-ai/`

---

## Deployment & Distribution

### Python Package (PyPI)

**Installation**:
```bash
pip install cognify-code
```

**Build from source**:
```bash
pip install -e ".[dev]"
```

**Entry Point**: `ai-assist = "ai_code_assistant.cli:main"`

### VSCode Extension

**Package**:
```bash
cd vscode-extension
npm run compile
npm run package  # Creates cognify-ai-X.X.X.vsix
```

**Install**:
```bash
code --install-extension cognify-ai-X.X.X.vsix
```

### Repository Structure

```
cognify-ai/
├── ai-code-assistant/       # Python CLI package
│   ├── src/
│   ├── tests/
│   ├── docs/
│   └── pyproject.toml
├── vscode-extension/        # TypeScript extension
│   ├── src/
│   └── package.json
└── index.html              # Landing page
```

---

## Common Patterns & Best Practices

### 1. Adding a New CLI Command

```python
# In cli.py

@main.command()
@click.argument("input_arg")
@click.option("--flag", is_flag=True, help="Enable flag")
@click.pass_context
def new_command(ctx, input_arg: str, flag: bool):
    """Description of the new command."""
    config, llm = get_components(ctx.obj.get("config_path"))
    console = Console()

    with console.status("Processing..."):
        # Use existing modules
        result = some_module.process(input_arg, llm)

    # Output using Rich
    console.print(Panel(result, title="Result"))
```

### 2. Adding a New Module

1. Create directory: `src/ai_code_assistant/new_module/`
2. Add files: `__init__.py`, `main.py`, `prompts.py`
3. Export from `__init__.py`
4. Add config class if needed in `config.py`
5. Add CLI commands in `cli.py`
6. Write tests in `tests/test_new_module.py`

### 3. Prompt Engineering Pattern

```python
# In prompts.py

from langchain_core.prompts import ChatPromptTemplate

REVIEW_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert code reviewer.
Analyze the code and return JSON with this structure:
{{"issues": [...], "summary": "..."}}
"""),
    ("human", """Review this {language} code:
```{language}
{code}
```"""),
])

# Usage in module
def review_code(self, code: str, language: str) -> ReviewResult:
    response = self.llm.invoke_with_template(
        REVIEW_PROMPT,
        code=code,
        language=language
    )
    return self._parse_response(response)
```

### 4. Error Handling Pattern

```python
from rich.console import Console

console = Console()

try:
    result = llm.invoke(prompt)
except ConnectionError:
    console.print("[red]Error: Cannot connect to Ollama.[/red]")
    console.print("Run: [cyan]ollama serve[/cyan]")
    raise SystemExit(1)
except Exception as e:
    console.print(f"[red]Error: {e}[/red]")
    raise
```

### 5. VSCode Extension Pattern - Adding a Command

```typescript
// In extension.ts

// 1. Register command
vscode.commands.registerCommand('cognify.newCommand', () => newCommandHandler());

// 2. Implement handler
async function newCommandHandler() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showWarningMessage('No active editor');
        return;
    }

    statusBarManager.setLoading('Processing...');
    try {
        const result = await cognifyRunner.newMethod(...);
        // Handle result
        statusBarManager.setReady();
    } catch (error) {
        statusBarManager.setError();
        vscode.window.showErrorMessage(`Failed: ${error}`);
    }
}

// 3. Add to package.json commands
```

---

## Troubleshooting Guide

### Common Issues

#### "Connection refused" error

**Cause**: Ollama server not running

**Solution**:
```bash
ollama serve
# In another terminal:
cognify status
```

#### "Model not found" error

**Cause**: Model not downloaded

**Solution**:
```bash
ollama pull deepseek-coder:6.7b
# Or for a different model:
ollama pull codellama:7b
```

#### LLM returns invalid JSON

**Cause**: Model not following prompt instructions

**Solutions**:
1. Use a larger/better model
2. Lower temperature in config
3. Retry the request

```bash
# Try a larger model
ollama pull deepseek-coder:33b

# Or lower temperature in config.yaml
llm:
  temperature: 0.0
```

#### Import errors in Python

**Solution**:
```bash
pip install -e ".[dev]"
# Or ensure PYTHONPATH
export PYTHONPATH=src
```

#### VSCode extension not working

**Solutions**:
1. Check if CLI is installed: `cognify status`
2. Reload VSCode: `Cmd+Shift+P` → "Developer: Reload Window"
3. Check Output panel for errors: View → Output → Select "Cognify AI"

#### Index not found (RAG search)

**Cause**: Codebase not indexed

**Solution**:
```bash
cognify index .
# Wait for indexing to complete
cognify search "your query"
```

#### Slow response times

**Solutions**:
1. Use Groq for faster inference
2. Use smaller context
3. Reduce max_tokens

```yaml
# config.yaml
llm:
  provider: groq
  model: llama-3.1-8b-instant
  max_tokens: 2048
```

---

## Development Timeline (Key Milestones)

| Phase | Features |
|-------|----------|
| **Phase 1** | Core CLI, Code Review, Code Generation |
| **Phase 2** | Interactive Chat, Chat Commands |
| **Phase 3** | RAG/Semantic Search, Codebase Indexing |
| **Phase 4** | AI File Editing, Diff Preview |
| **Phase 5** | Multi-File Refactoring, Change Plans |
| **Phase 6** | VSCode Extension, Sidebar Chat |
| **Phase 7** | Multi-Provider Support, Icon Updates |

---

## Cross-Reference Links

- **Architecture Details**: [ARCHITECTURE.md](./ARCHITECTURE.md)
- **Provider Setup**: [PROVIDERS.md](./PROVIDERS.md)
- **File Editing Guide**: [FILE_EDITING_FEATURE.md](./FILE_EDITING_FEATURE.md)
- **Refactoring Guide**: [REFACTOR_FEATURE.md](./REFACTOR_FEATURE.md)
- **RAG/Search**: [RETRIEVAL_FEATURE.md](./RETRIEVAL_FEATURE.md)
- **VSCode Extension**: [guides/vscode-extension.md](./guides/vscode-extension.md)

---

## Quick Start for New Agents

1. **Understand the architecture**: Read the ASCII diagram in "Architecture Overview"
2. **Know the entry points**: `cli.py` for commands, `llm.py` for LLM interactions
3. **Follow patterns**: Use existing modules as templates
4. **Test changes**: Run `PYTHONPATH=src pytest tests/ -v`
5. **Maintain consistency**: Match existing code style and patterns

**Key Files to Read First**:
1. `cli.py` - All CLI commands
2. `config.py` - Configuration structure
3. `llm.py` - LLM abstraction
4. `extension.ts` - VSCode extension entry

---

*Last Updated: January 2026*

