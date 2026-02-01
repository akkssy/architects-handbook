import * as vscode from 'vscode';
import { CognifyRunner, ChatMessage } from './cognifyRunner';

interface ConversationMessage {
    role: 'user' | 'assistant';
    content: string;
    context?: string;
    timestamp: number;
}

export class ChatPanel {
    public static currentPanel: ChatPanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private readonly _cognifyRunner: CognifyRunner;
    private _disposables: vscode.Disposable[] = [];
    private _onDidDisposeEmitter = new vscode.EventEmitter<void>();
    public readonly onDidDispose = this._onDidDisposeEmitter.event;

    // Conversation state
    private _conversationHistory: ConversationMessage[] = [];
    private _currentContext: string | undefined;
    private _contextFileName: string | undefined;

    constructor(extensionUri: vscode.Uri, cognifyRunner: CognifyRunner) {
        this._extensionUri = extensionUri;
        this._cognifyRunner = cognifyRunner;

        this._panel = vscode.window.createWebviewPanel(
            'cognifyChat',
            'Cognify Chat',
            vscode.ViewColumn.Beside,
            {
                enableScripts: true,
                retainContextWhenHidden: true
            }
        );

        this._panel.webview.html = this._getHtmlContent();

        this._panel.webview.onDidReceiveMessage(
            async (message) => {
                switch (message.command) {
                    case 'sendMessage':
                        await this._handleMessage(message.text);
                        break;
                    case 'insertCode':
                        await this._insertCode(message.code);
                        break;
                    case 'addContext':
                        await this._addContext();
                        break;
                    case 'clearContext':
                        this._clearContext();
                        break;
                    case 'clearHistory':
                        this._clearHistory();
                        break;
                    case 'applyCode':
                        await this._applyCode(message.code);
                        break;
                }
            },
            null,
            this._disposables
        );

        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
    }

    reveal() {
        this._panel.reveal(vscode.ViewColumn.Beside);
    }

    private async _handleMessage(text: string) {
        // Get current file context from selection if no explicit context set
        const editor = vscode.window.activeTextEditor;
        let contextToUse = this._currentContext;
        let language = 'python';

        if (editor) {
            language = editor.document.languageId;
            const selection = editor.selection;
            if (!selection.isEmpty && !contextToUse) {
                contextToUse = editor.document.getText(selection);
            }
        }

        // Add user message to history
        this._conversationHistory.push({
            role: 'user',
            content: text,
            context: contextToUse,
            timestamp: Date.now()
        });

        // Send thinking indicator
        this._panel.webview.postMessage({
            command: 'thinking',
            thinking: true
        });

        try {
            // Prepare history for API (last 10 messages for context window management)
            const historyForApi: ChatMessage[] = this._conversationHistory
                .slice(-10)
                .map(msg => ({
                    role: msg.role,
                    content: msg.content
                }));

            // Use smart chat with context and history
            const result = await this._cognifyRunner.smartChat(text, {
                context: contextToUse,
                language,
                history: historyForApi.slice(0, -1) // Exclude current message
            });

            // Add assistant response to history
            this._conversationHistory.push({
                role: 'assistant',
                content: result.response,
                timestamp: Date.now()
            });

            // Send response with intent info
            this._panel.webview.postMessage({
                command: 'response',
                text: result.response,
                intent: result.intent,
                hasCode: result.hasCode
            });

            // Clear context after use (optional - can be toggled)
            // this._clearContext();

        } catch (error) {
            this._panel.webview.postMessage({
                command: 'error',
                text: `Error: ${error}`
            });
        }
    }

    private async _addContext() {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showWarningMessage('No file open. Please open a file first.');
            return;
        }

        const selection = editor.selection;
        if (selection.isEmpty) {
            // Use entire file
            this._currentContext = editor.document.getText();
            this._contextFileName = editor.document.fileName.split('/').pop() || 'file';
        } else {
            // Use selection
            this._currentContext = editor.document.getText(selection);
            const lineCount = selection.end.line - selection.start.line + 1;
            this._contextFileName = `${editor.document.fileName.split('/').pop()} (${lineCount} lines)`;
        }

        this._panel.webview.postMessage({
            command: 'contextAdded',
            fileName: this._contextFileName,
            preview: this._currentContext.substring(0, 100) + (this._currentContext.length > 100 ? '...' : '')
        });
    }

    private _clearContext() {
        this._currentContext = undefined;
        this._contextFileName = undefined;
        this._panel.webview.postMessage({ command: 'contextCleared' });
    }

    private _clearHistory() {
        this._conversationHistory = [];
        this._panel.webview.postMessage({ command: 'historyCleared' });
    }

    private async _insertCode(code: string) {
        const editor = vscode.window.activeTextEditor;
        if (editor) {
            await editor.edit(editBuilder => {
                editBuilder.insert(editor.selection.active, code);
            });
            vscode.window.showInformationMessage('Code inserted at cursor position');
        }
    }

    private async _applyCode(code: string) {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showWarningMessage('No active editor to apply code');
            return;
        }

        const selection = editor.selection;
        if (selection.isEmpty) {
            // Insert at cursor
            await editor.edit(editBuilder => {
                editBuilder.insert(editor.selection.active, code);
            });
        } else {
            // Replace selection
            await editor.edit(editBuilder => {
                editBuilder.replace(selection, code);
            });
        }
        vscode.window.showInformationMessage('Code applied successfully');
    }

    private _getHtmlContent(): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cognify Chat</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: var(--vscode-font-family);
            background: var(--vscode-editor-background);
            color: var(--vscode-editor-foreground);
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        .header {
            padding: 12px 15px;
            border-bottom: 1px solid var(--vscode-panel-border);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .header-left { display: flex; align-items: center; gap: 8px; }
        .header h2 { font-size: 15px; font-weight: 600; }
        .header-actions { display: flex; gap: 6px; }
        .header-btn {
            background: transparent;
            border: 1px solid var(--vscode-button-secondaryBackground);
            color: var(--vscode-foreground);
            padding: 4px 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 11px;
            opacity: 0.8;
        }
        .header-btn:hover { opacity: 1; background: var(--vscode-button-secondaryBackground); }

        .context-bar {
            padding: 8px 15px;
            background: var(--vscode-editor-inactiveSelectionBackground);
            border-bottom: 1px solid var(--vscode-panel-border);
            display: none;
            align-items: center;
            gap: 8px;
            font-size: 12px;
        }
        .context-bar.visible { display: flex; }
        .context-badge {
            background: var(--vscode-badge-background);
            color: var(--vscode-badge-foreground);
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11px;
        }
        .context-clear {
            margin-left: auto;
            background: transparent;
            border: none;
            color: var(--vscode-errorForeground);
            cursor: pointer;
            font-size: 14px;
        }

        .messages {
            flex: 1;
            overflow-y: auto;
            padding: 15px;
        }
        .message {
            margin-bottom: 15px;
            padding: 12px;
            border-radius: 8px;
            max-width: 90%;
            line-height: 1.5;
        }
        .message.user {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            margin-left: auto;
        }
        .message.assistant {
            background: var(--vscode-editor-inactiveSelectionBackground);
        }
        .message p { margin-bottom: 8px; }
        .message p:last-child { margin-bottom: 0; }
        .message ul, .message ol { margin: 8px 0; padding-left: 20px; }
        .message li { margin: 4px 0; }
        .message strong { color: var(--vscode-textLink-foreground); }

        .message pre {
            background: var(--vscode-textCodeBlock-background);
            padding: 12px;
            border-radius: 6px;
            overflow-x: auto;
            margin: 10px 0;
            position: relative;
            border: 1px solid var(--vscode-panel-border);
        }
        .message code {
            font-family: var(--vscode-editor-font-family);
            font-size: 13px;
        }
        .message code:not(pre code) {
            background: var(--vscode-textCodeBlock-background);
            padding: 2px 6px;
            border-radius: 3px;
        }

        .code-actions {
            position: absolute;
            top: 6px;
            right: 6px;
            display: flex;
            gap: 4px;
        }
        .code-btn {
            background: var(--vscode-button-secondaryBackground);
            border: none;
            padding: 4px 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 11px;
            color: var(--vscode-button-secondaryForeground);
        }
        .code-btn:hover { background: var(--vscode-button-secondaryHoverBackground); }

        .intent-badge {
            display: inline-block;
            font-size: 10px;
            padding: 2px 6px;
            border-radius: 3px;
            margin-bottom: 8px;
            text-transform: uppercase;
            font-weight: 600;
        }
        .intent-generate { background: #2e7d32; color: white; }
        .intent-review { background: #1565c0; color: white; }
        .intent-edit { background: #f57c00; color: white; }
        .intent-explain { background: #7b1fa2; color: white; }
        .intent-chat { background: var(--vscode-badge-background); color: var(--vscode-badge-foreground); }

        .input-area {
            padding: 12px 15px;
            border-top: 1px solid var(--vscode-panel-border);
        }
        .input-row {
            display: flex;
            gap: 8px;
            margin-bottom: 8px;
        }
        #messageInput {
            flex: 1;
            padding: 10px 12px;
            border: 1px solid var(--vscode-input-border);
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            border-radius: 6px;
            font-size: 14px;
            resize: none;
            min-height: 60px;
        }
        #messageInput:focus {
            outline: none;
            border-color: var(--vscode-focusBorder);
        }
        .action-row {
            display: flex;
            gap: 8px;
            align-items: center;
        }
        .action-btn {
            padding: 6px 12px;
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            display: flex;
            align-items: center;
            gap: 4px;
        }
        .action-btn:hover { background: var(--vscode-button-secondaryHoverBackground); }
        #sendBtn {
            margin-left: auto;
            padding: 8px 16px;
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
        }
        #sendBtn:hover { background: var(--vscode-button-hoverBackground); }
        #sendBtn:disabled { opacity: 0.5; cursor: not-allowed; }

        .thinking { opacity: 0.7; font-style: italic; }
        .suggestions {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 10px;
        }
        .suggestion-chip {
            background: var(--vscode-button-secondaryBackground);
            border: none;
            padding: 4px 10px;
            border-radius: 12px;
            cursor: pointer;
            font-size: 11px;
            color: var(--vscode-foreground);
        }
        .suggestion-chip:hover { background: var(--vscode-button-secondaryHoverBackground); }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-left">
            <span>⚛️</span>
            <h2>Cognify AI</h2>
        </div>
        <div class="header-actions">
            <button class="header-btn" onclick="clearHistory()" title="Clear conversation">🗑️ Clear</button>
        </div>
    </div>

    <div class="context-bar" id="contextBar">
        <span>📎 Context:</span>
        <span class="context-badge" id="contextBadge"></span>
        <button class="context-clear" onclick="clearContext()" title="Remove context">×</button>
    </div>

    <div class="messages" id="messages">
        <div class="message assistant">
            <p>👋 <strong>Hello! I'm Cognify AI.</strong></p>
            <p>I understand natural language - just tell me what you need:</p>
            <ul>
                <li><strong>"Write a function to..."</strong> → I'll generate code</li>
                <li><strong>"Review this code"</strong> → I'll analyze for issues</li>
                <li><strong>"Add error handling"</strong> → I'll edit your code</li>
                <li><strong>"What does this do?"</strong> → I'll explain the code</li>
                <li>Or just ask any programming question!</li>
            </ul>
            <div class="suggestions">
                <button class="suggestion-chip" onclick="useSuggestion('Write a binary search function')">Write binary search</button>
                <button class="suggestion-chip" onclick="useSuggestion('Review this code for bugs')">Review code</button>
                <button class="suggestion-chip" onclick="useSuggestion('Explain how this works')">Explain code</button>
            </div>
        </div>
    </div>

    <div class="input-area">
        <div class="input-row">
            <textarea id="messageInput" placeholder="Ask anything... (e.g., 'write a sorting function' or 'what's wrong with this code?')" rows="2"></textarea>
        </div>
        <div class="action-row">
            <button class="action-btn" onclick="addContext()">📎 Add Context</button>
            <button id="sendBtn">Send →</button>
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        const messagesDiv = document.getElementById('messages');
        const input = document.getElementById('messageInput');
        const sendBtn = document.getElementById('sendBtn');
        const contextBar = document.getElementById('contextBar');
        const contextBadge = document.getElementById('contextBadge');

        function addMessage(text, isUser, intent) {
            const div = document.createElement('div');
            div.className = 'message ' + (isUser ? 'user' : 'assistant');

            let content = '';
            if (!isUser && intent && intent !== 'chat') {
                content += '<span class="intent-badge intent-' + intent + '">' + intent + '</span>';
            }
            content += formatMessage(text);

            div.innerHTML = content;
            messagesDiv.appendChild(div);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        function formatMessage(text) {
            // Convert code blocks with action buttons
            text = text.replace(/\`\`\`(\\w*)\\n([\\s\\S]*?)\`\`\`/g, (match, lang, code) => {
                const escapedCode = escapeHtml(code.trim());
                return '<pre><code>' + escapedCode + '</code>' +
                    '<div class="code-actions">' +
                    '<button class="code-btn" onclick="copyCode(this)">Copy</button>' +
                    '<button class="code-btn" onclick="insertCode(this)">Insert</button>' +
                    '<button class="code-btn" onclick="applyCode(this)">Apply</button>' +
                    '</div></pre>';
            });

            // Convert inline code
            text = text.replace(/\`([^\`]+)\`/g, '<code>$1</code>');

            // Convert bold
            text = text.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');

            // Convert newlines to paragraphs
            const paragraphs = text.split(/\\n\\n+/);
            if (paragraphs.length > 1) {
                text = paragraphs.map(p => '<p>' + p.replace(/\\n/g, '<br>') + '</p>').join('');
            } else {
                text = text.replace(/\\n/g, '<br>');
            }

            return text;
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function copyCode(btn) {
            const code = btn.closest('pre').querySelector('code').textContent;
            navigator.clipboard.writeText(code);
            btn.textContent = 'Copied!';
            setTimeout(() => btn.textContent = 'Copy', 2000);
        }

        function insertCode(btn) {
            const code = btn.closest('pre').querySelector('code').textContent;
            vscode.postMessage({ command: 'insertCode', code });
        }

        function applyCode(btn) {
            const code = btn.closest('pre').querySelector('code').textContent;
            vscode.postMessage({ command: 'applyCode', code });
        }

        function addContext() {
            vscode.postMessage({ command: 'addContext' });
        }

        function clearContext() {
            vscode.postMessage({ command: 'clearContext' });
        }

        function clearHistory() {
            vscode.postMessage({ command: 'clearHistory' });
        }

        function useSuggestion(text) {
            input.value = text;
            input.focus();
        }

        function sendMessage() {
            const text = input.value.trim();
            if (!text) return;

            addMessage(text, true);
            input.value = '';
            sendBtn.disabled = true;
            vscode.postMessage({ command: 'sendMessage', text });
        }

        sendBtn.addEventListener('click', sendMessage);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        window.addEventListener('message', (event) => {
            const message = event.data;
            switch (message.command) {
                case 'thinking':
                    if (message.thinking) {
                        const div = document.createElement('div');
                        div.className = 'message assistant thinking';
                        div.id = 'thinking';
                        div.innerHTML = '🤔 <em>Thinking...</em>';
                        messagesDiv.appendChild(div);
                        messagesDiv.scrollTop = messagesDiv.scrollHeight;
                    }
                    break;
                case 'response':
                    document.getElementById('thinking')?.remove();
                    addMessage(message.text, false, message.intent);
                    sendBtn.disabled = false;
                    break;
                case 'error':
                    document.getElementById('thinking')?.remove();
                    addMessage('❌ ' + message.text, false);
                    sendBtn.disabled = false;
                    break;
                case 'contextAdded':
                    contextBadge.textContent = message.fileName;
                    contextBar.classList.add('visible');
                    break;
                case 'contextCleared':
                    contextBar.classList.remove('visible');
                    break;
                case 'historyCleared':
                    messagesDiv.innerHTML = '<div class="message assistant"><p>🗑️ Conversation cleared. How can I help you?</p></div>';
                    break;
            }
        });
    </script>
</body>
</html>`;
    }

    dispose() {
        this._onDidDisposeEmitter.fire();
        this._panel.dispose();
        while (this._disposables.length) {
            const d = this._disposables.pop();
            if (d) d.dispose();
        }
    }
}

