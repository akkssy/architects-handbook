# Changelog

All notable changes to the Cognify AI extension will be documented in this file.

## [0.1.0] - 2026-02-01

### Added
- 🎉 Initial release of Cognify AI VSCode Extension
- 🔍 **Code Review**: Review files and selections with AI-powered analysis
  - Inline diagnostics with severity levels
  - Suggestions for improvements
- ✨ **Code Generation**: Generate code from natural language descriptions
  - Context-aware generation
  - Multi-language support
- ✏️ **Code Editing**: Edit code using natural language instructions
  - Preview changes before applying
  - Works with selections or entire files
- 💡 **Code Explanation**: Get detailed explanations of selected code
- 💬 **Interactive Chat**: Sidebar chat panel for conversations
  - Natural language understanding
  - Intelligent intent detection (generate, review, edit, explain)
  - Context management with "Add Context" button
  - Conversation history
  - Code action buttons (Copy, Insert, Apply)
- ⚙️ **Multi-Provider Support**: Works with multiple LLM providers
  - Ollama (local, free)
  - Groq (cloud, fast)
  - Google Gemini
  - OpenAI
  - Cerebras
  - OpenRouter
- ⌨️ **Keyboard Shortcuts**: Quick access to all features
- 🖱️ **Context Menu Integration**: Right-click actions for selected code
- 📊 **Status Bar**: Shows connection status and quick actions

### Requirements
- Cognify CLI (`pip install cognify-code`)
- An LLM provider (Ollama recommended for local use)

