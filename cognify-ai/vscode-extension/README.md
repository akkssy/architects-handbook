# Cognify AI - VSCode Extension

<p align="center">
  <img src="images/icon.png" alt="Cognify AI" width="128" height="128">
</p>

<p align="center">
  <strong>AI-powered code assistant for Visual Studio Code</strong><br>
  Review, generate, edit, and explain code using local or cloud LLMs.
</p>

<p align="center">
  <a href="https://github.com/akkssy/cognify-ai">GitHub</a> •
  <a href="https://akkssy.github.io/cognify-ai/">Documentation</a> •
  <a href="https://github.com/akkssy/cognify-ai/issues">Report Bug</a>
</p>

---

## ✨ Features

### 🔍 Code Review
- Review entire files or selected code
- Get inline diagnostics with issues and suggestions
- Supports multiple severity levels (error, warning, info)

### ✨ Code Generation
- Generate code from natural language descriptions
- Context-aware generation using your codebase
- Supports multiple programming languages

### ✏️ Code Editing
- Edit code using natural language instructions
- Preview changes before applying
- Works with selections or entire files

### 💡 Code Explanation
- Get detailed explanations of selected code
- Understand complex algorithms and patterns
- Learn from AI-powered insights

### 💬 Interactive Chat
- Chat panel for extended conversations
- Context-aware responses using selected code
- Insert generated code directly into editor

## Requirements

- **Cognify CLI**: Install via `pip install cognify-code`
- **LLM Provider**: One of the following:
  - Ollama (local, free)
  - Groq (cloud, free tier)
  - Google Gemini (cloud)
  - OpenAI (cloud)
  - And more...

## Installation

1. Install the Cognify CLI:
   ```bash
   pip install cognify-code
   ```

2. Set up your LLM provider:
   ```bash
   # For Ollama (local)
   ollama pull deepseek-coder:6.7b
   
   # For cloud providers, set API keys
   export GROQ_API_KEY=your_key
   ```

3. Install this extension from the VSCode Marketplace

## Usage

### Keyboard Shortcuts

| Command | Windows/Linux | Mac |
|---------|--------------|-----|
| Review File | `Ctrl+Shift+R` | `Cmd+Shift+R` |
| Generate Code | `Ctrl+Shift+G` | `Cmd+Shift+G` |
| Explain Selection | `Ctrl+Shift+E` | `Cmd+Shift+E` |
| Open Chat | `Ctrl+Shift+C` | `Cmd+Shift+C` |

### Context Menu

Right-click on selected code to access:
- **Cognify: Review Selection**
- **Cognify: Explain Selection**
- **Cognify: Edit Code with AI**

### Command Palette

Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac) and type "Cognify" to see all commands.

## Configuration

Open Settings (`Ctrl+,`) and search for "Cognify" to configure:

| Setting | Description | Default |
|---------|-------------|---------|
| `cognify.provider` | LLM provider to use | `ollama` |
| `cognify.model` | Model name | `deepseek-coder:6.7b` |
| `cognify.autoContext` | Auto-include relevant files | `true` |
| `cognify.maxContextTokens` | Max tokens for context | `8000` |
| `cognify.showInlineHints` | Show inline diagnostics | `true` |

## Examples

### Review Code
1. Open a file
2. Press `Cmd+Shift+R` (or use Command Palette)
3. View issues in the Problems panel and Review panel

### Generate Code
1. Press `Cmd+Shift+G`
2. Describe what you want: "a function to validate email addresses"
3. Review and use the generated code

### Edit Code
1. Select code to edit
2. Right-click → "Cognify: Edit Code with AI"
3. Describe changes: "add error handling"
4. Preview and apply changes

## Troubleshooting

### "cognify not found"
Make sure Cognify CLI is installed and in your PATH:
```bash
pip install cognify-code
cognify --version
```

### Connection errors
Check your LLM provider status:
```bash
cognify status
```

### Slow responses
- Use a faster provider (Groq is very fast)
- Reduce `maxContextTokens` setting
- Use a smaller model

## Contributing

Contributions are welcome! Please visit our [GitHub repository](https://github.com/akkssy/cognify-ai).

## License

MIT License - see [LICENSE](../LICENSE) for details.

