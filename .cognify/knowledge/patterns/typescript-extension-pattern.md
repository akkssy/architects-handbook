# TypeScript Extension Pattern

**ID:** 20260201113225-055f8f92
**Category:** patterns
**Tags:** typescript, vscode, extension
**Created:** 2026-02-01T11:32:25.080238
**Updated:** 2026-02-01T11:32:25.080238
**Source:** user

---

When creating VSCode extensions in TypeScript, use WebviewViewProvider for sidebar views. Always implement the resolveWebviewView method and set up message passing between the extension and webview.