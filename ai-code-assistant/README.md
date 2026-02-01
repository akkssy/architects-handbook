# 🧠 Cognify AI

<p align="center">
  <strong>Code Cognition — Your Local AI-Powered Code Assistant</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#documentation">Docs</a> •
  <a href="#contributing">Contributing</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/tests-144%20passed-brightgreen.svg" alt="Tests">
  <img src="https://img.shields.io/badge/ollama-local%20LLM-orange.svg" alt="Ollama">
</p>

---

A powerful CLI tool that brings AI-powered code cognition to your terminal. Review code, generate functions, search your codebase semantically, and refactor projects—all running **locally** with [Ollama](https://ollama.ai). No API keys, no cloud, complete privacy.

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔍 **Code Review** | Analyze code for bugs, security issues, and style problems |
| ⚡ **Code Generation** | Generate functions, classes, and tests from natural language |
| 🔎 **Semantic Search** | Search your codebase using natural language queries |
| 📝 **AI File Editing** | Edit files with natural language instructions |
| 🔄 **Multi-File Refactor** | Refactor across multiple files at once |
| 🏷️ **Symbol Renaming** | Rename functions, classes, variables across your project |
| 💬 **Interactive Chat** | Chat with AI about your code |
| 📊 **Codebase Indexing** | Create searchable semantic index with RAG |

## 🚀 Quick Start

### Prerequisites

1. **Install Ollama**: Download from [ollama.ai](https://ollama.ai)
2. **Pull a coding model**:
   ```bash
   ollama pull deepseek-coder:6.7b
   ```
3. **Start Ollama** (if not running):
   ```bash
   ollama serve
   ```

### Installation

```bash
# Clone the repository
git clone https://github.com/akkssy/cognify-ai.git
cd cognify-ai

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the package
pip install -e .
```

### Verify Installation

```bash
ai-assist status
```

## 📖 Usage

### Code Review
Analyze code for bugs, security vulnerabilities, and style issues:
```bash
ai-assist review path/to/file.py
ai-assist review src/ --format json
```

### Code Generation
Generate code from natural language descriptions:
```bash
ai-assist generate "binary search function" --language python
ai-assist generate "REST API client class" --mode class
ai-assist generate "unit tests for calculator" --mode test
```

### Semantic Search
Search your codebase using natural language:
```bash
# First, index your codebase
ai-assist index .

# Then search
ai-assist search "error handling"
ai-assist search "database connection" -k 10
```

### File Editing
Edit files with AI assistance:
```bash
ai-assist edit config.py "add logging to all functions" --preview
ai-assist edit utils.py "add type hints" --backup
```

### Multi-File Refactoring
Refactor across multiple files:
```bash
ai-assist refactor "add docstrings to all functions" -p "src/**/*.py" --dry-run
ai-assist refactor "convert print to logging" --pattern "**/*.py" --confirm
```

### Symbol Renaming
Rename symbols across your project:
```bash
ai-assist rename old_function new_function --type function --dry-run
ai-assist rename MyClass BetterClass --type class -p "src/**/*.py"
```

### Interactive Chat
Chat with AI about your code:
```bash
ai-assist chat
```

### All Commands
```bash
ai-assist --help
```

## ⚙️ Configuration

Configuration is managed via `config.yaml`:

```yaml
llm:
  model: "deepseek-coder:6.7b"
  base_url: "http://localhost:11434"
  temperature: 0.1
  max_tokens: 4096

review:
  severity_levels: [critical, warning, suggestion]
  categories: [bugs, security, performance, style]

generation:
  include_type_hints: true
  include_docstrings: true

retrieval:
  embedding_model: "all-MiniLM-L6-v2"
  chunk_size: 50

editor:
  create_backup: true
  show_diff: true

refactor:
  max_files: 20
  require_confirmation: true
```

Or use environment variables:
```bash
export AI_ASSISTANT_LLM_MODEL="codellama:7b"
```

## 📁 Project Structure

```
cognify-ai/
├── src/ai_code_assistant/
│   ├── cli.py              # Command-line interface
│   ├── config.py           # Configuration management
│   ├── llm.py              # LLM integration (Ollama/LangChain)
│   ├── reviewer/           # Code review module
│   ├── generator/          # Code generation module
│   ├── retrieval/          # Semantic search & indexing (RAG)
│   ├── editor/             # AI file editing
│   ├── refactor/           # Multi-file refactoring
│   ├── chat/               # Interactive chat
│   └── utils/              # Utilities & formatters
├── tests/                  # 144 unit tests
├── docs/                   # Documentation
├── config.yaml             # Configuration
└── pyproject.toml          # Dependencies
```

## 🧪 Testing

```bash
# Run all tests
PYTHONPATH=src pytest tests/ -v

# Run with coverage
PYTHONPATH=src pytest tests/ --cov=ai_code_assistant
```

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| LLM Framework | LangChain |
| Local LLM | Ollama |
| Vector Database | ChromaDB |
| Embeddings | Sentence Transformers |
| CLI | Click + Rich |
| Config | Pydantic |
| Testing | Pytest |

## 🐛 Troubleshooting

**"Connection refused" error**
```bash
ollama serve  # Make sure Ollama is running
```

**LLM returns invalid JSON**
```bash
ollama pull deepseek-coder:6.7b  # Try a larger model
```

**Import errors**
```bash
pip install -e ".[dev]"
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Ollama](https://ollama.ai) - Local LLM runtime
- [LangChain](https://langchain.com) - LLM framework
- [DeepSeek](https://deepseek.com) - Coding model
- [ChromaDB](https://www.trychroma.com) - Vector database

---

<p align="center">
  Made with ❤️ for developers who value privacy and local AI
</p>
