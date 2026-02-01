import * as vscode from 'vscode';
import { CognifyRunner, ChatMessage, IndexStatus, IndexProgress } from './cognifyRunner';

interface ConversationMessage {
    role: 'user' | 'assistant';
    content: string;
    context?: string;
    timestamp: number;
}

interface ChatSession {
    id: string;
    name: string;
    messages: ConversationMessage[];
    agentId: string;
    createdAt: number;
    updatedAt: number;
}

interface IndexState {
    status: 'unknown' | 'checking' | 'not_indexed' | 'indexed' | 'indexing' | 'error';
    chunkCount: number;
    fileCount: number;
    progress?: IndexProgress;
    error?: string;
}

// Agent type definitions
type AgentId = 'general' | 'reviewer' | 'generator' | 'documenter' | 'tester';

interface Agent {
    id: AgentId;
    name: string;
    icon: string;
    description: string;
    systemPrompt: string;
    suggestions: string[];
}

// Define all available agents with their system prompts
const AGENTS: Record<AgentId, Agent> = {
    general: {
        id: 'general',
        name: 'General Assistant',
        icon: '💬',
        description: 'General-purpose coding assistant for any task',
        systemPrompt: `You are Cognify AI, a helpful and knowledgeable coding assistant. You help developers with:
- Answering questions about code and programming concepts
- Explaining complex topics in simple terms
- Providing guidance on best practices
- Helping debug issues and solve problems
- Suggesting improvements and optimizations

Be concise, accurate, and helpful. When showing code, use proper formatting with language-specific syntax highlighting.`,
        suggestions: ['Write a function to', 'Explain this code', 'How do I...']
    },
    reviewer: {
        id: 'reviewer',
        name: 'Code Reviewer',
        icon: '🔍',
        description: 'Analyzes code for bugs, security issues, and best practices',
        systemPrompt: `You are Cognify AI's Code Reviewer Agent, an expert at analyzing code quality. Your role is to:

1. **Bug Detection**: Identify potential bugs, logic errors, and edge cases
2. **Security Analysis**: Find security vulnerabilities (SQL injection, XSS, buffer overflows, etc.)
3. **Best Practices**: Check adherence to coding standards and design patterns
4. **Performance**: Spot performance bottlenecks and inefficiencies
5. **Maintainability**: Assess code readability, complexity, and technical debt

When reviewing code:
- Be thorough but constructive
- Prioritize issues by severity (Critical > High > Medium > Low)
- Provide specific line references when possible
- Suggest concrete fixes for each issue
- Acknowledge good practices you observe

Format your reviews clearly with sections for different issue types.`,
        suggestions: ['Review this code', 'Find bugs in', 'Check security of']
    },
    generator: {
        id: 'generator',
        name: 'Code Generator',
        icon: '✨',
        description: 'Generates functions, classes, and boilerplate code',
        systemPrompt: `You are Cognify AI's Code Generator Agent, specialized in writing high-quality code. Your role is to:

1. **Generate Code**: Write functions, classes, modules, and complete implementations
2. **Follow Patterns**: Use appropriate design patterns and architectural principles
3. **Best Practices**: Write clean, readable, and maintainable code
4. **Type Safety**: Include proper type hints/annotations where applicable
5. **Error Handling**: Include appropriate error handling and edge cases

When generating code:
- Ask clarifying questions if requirements are unclear
- Provide complete, working implementations
- Include brief comments explaining complex logic
- Follow the language's idiomatic style
- Consider edge cases and input validation
- Make code modular and reusable

Always wrap code in proper markdown code blocks with language specification.`,
        suggestions: ['Generate a function that', 'Create a class for', 'Write code to']
    },
    documenter: {
        id: 'documenter',
        name: 'Documentation Writer',
        icon: '📝',
        description: 'Writes docstrings, comments, and README content',
        systemPrompt: `You are Cognify AI's Documentation Agent, an expert technical writer. Your role is to:

1. **Docstrings**: Write comprehensive function/class documentation
2. **Comments**: Add clear inline comments explaining complex logic
3. **README Files**: Create well-structured project documentation
4. **API Docs**: Document APIs with examples and parameter descriptions
5. **Tutorials**: Write step-by-step guides and explanations

When writing documentation:
- Use the appropriate format for the language (JSDoc, docstrings, etc.)
- Include parameter types, return values, and exceptions
- Provide usage examples
- Keep explanations clear and concise
- Use proper markdown formatting
- Consider the target audience (beginners vs experts)

Documentation should be accurate, complete, and easy to understand.`,
        suggestions: ['Document this function', 'Write a README for', 'Add comments to']
    },
    tester: {
        id: 'tester',
        name: 'Test Writer',
        icon: '🧪',
        description: 'Creates unit tests and test cases',
        systemPrompt: `You are Cognify AI's Test Writer Agent, specialized in creating comprehensive tests. Your role is to:

1. **Unit Tests**: Write thorough unit tests for functions and classes
2. **Test Cases**: Design test cases covering edge cases and boundaries
3. **Mocking**: Create appropriate mocks and stubs for dependencies
4. **Assertions**: Use meaningful assertions with clear failure messages
5. **Coverage**: Ensure high code coverage with meaningful tests

When writing tests:
- Use the appropriate testing framework for the language (Jest, pytest, JUnit, etc.)
- Follow the Arrange-Act-Assert (AAA) pattern
- Test both happy paths and error cases
- Include edge cases (null, empty, boundary values)
- Write descriptive test names that explain what's being tested
- Keep tests independent and isolated
- Add setup/teardown when needed

Provide complete, runnable test files with all necessary imports.`,
        suggestions: ['Write tests for', 'Create test cases for', 'Test this function']
    }
};

export class ChatViewProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'cognify.chatView';
    private static readonly SESSIONS_KEY = 'cognify.chatSessions';
    private static readonly CURRENT_SESSION_KEY = 'cognify.currentSessionId';
    private static readonly INDEX_STATE_KEY = 'cognify.indexState';

    private _view?: vscode.WebviewView;
    private _sessions: Map<string, ChatSession> = new Map();
    private _currentSessionId: string = '';
    private _currentContext: string | undefined;
    private _contextFileName: string | undefined;
    private _currentProvider: string = 'ollama';
    private _currentModel: string = 'deepseek-coder:6.7b';
    private _indexState: IndexState = { status: 'unknown', chunkCount: 0, fileCount: 0 };
    private _isIndexing: boolean = false;

    // Available providers and their models
    private readonly _providers: { [key: string]: string[] } = {
        'ollama': ['deepseek-coder:6.7b', 'codellama:7b', 'llama2:7b', 'mistral:7b', 'qwen2.5-coder:7b'],
        'groq': ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'mixtral-8x7b-32768', 'gemma2-9b-it'],
        'google': ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash-exp'],
        'openai': ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
        'cerebras': ['llama3.1-8b', 'llama3.1-70b'],
        'openrouter': ['anthropic/claude-3.5-sonnet', 'openai/gpt-4o', 'google/gemini-pro']
    };

    constructor(
        private readonly _extensionUri: vscode.Uri,
        private readonly _cognifyRunner: CognifyRunner,
        private readonly _context: vscode.ExtensionContext
    ) {
        // Load current settings
        this._loadSettings();
        // Load chat sessions from persistent storage
        this._loadSessions();
        // Load index state from persistent storage
        this._loadIndexState();
    }

    // Generate a unique ID for new sessions
    private _generateSessionId(): string {
        return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    // Get current session's conversation history
    private get _conversationHistory(): ConversationMessage[] {
        const session = this._sessions.get(this._currentSessionId);
        return session ? session.messages : [];
    }

    // Set current session's conversation history
    private set _conversationHistory(messages: ConversationMessage[]) {
        const session = this._sessions.get(this._currentSessionId);
        if (session) {
            session.messages = messages;
            session.updatedAt = Date.now();
        }
    }

    private _loadSessions() {
        const savedSessions = this._context.globalState.get<ChatSession[]>(ChatViewProvider.SESSIONS_KEY);
        const savedCurrentId = this._context.globalState.get<string>(ChatViewProvider.CURRENT_SESSION_KEY);

        if (savedSessions && Array.isArray(savedSessions) && savedSessions.length > 0) {
            this._sessions.clear();
            savedSessions.forEach(session => {
                this._sessions.set(session.id, session);
            });
            // Restore current session or use first available
            if (savedCurrentId && this._sessions.has(savedCurrentId)) {
                this._currentSessionId = savedCurrentId;
            } else {
                this._currentSessionId = savedSessions[0].id;
            }
        } else {
            // No sessions exist, create the first one
            this._createNewSession('Chat 1');
        }
    }

    private _saveSessions() {
        const sessionsArray = Array.from(this._sessions.values());
        this._context.globalState.update(ChatViewProvider.SESSIONS_KEY, sessionsArray);
        this._context.globalState.update(ChatViewProvider.CURRENT_SESSION_KEY, this._currentSessionId);
    }

    private _createNewSession(name?: string, agentId: AgentId = 'general'): ChatSession {
        const id = this._generateSessionId();
        const sessionNumber = this._sessions.size + 1;
        const agent = AGENTS[agentId];
        const session: ChatSession = {
            id,
            name: name || `${agent.icon} ${agent.name} ${sessionNumber}`,
            messages: [],
            agentId: agentId,
            createdAt: Date.now(),
            updatedAt: Date.now()
        };
        this._sessions.set(id, session);
        this._currentSessionId = id;
        this._saveSessions();
        return session;
    }

    // Get current session's agent
    private _getCurrentAgent(): Agent {
        const session = this._sessions.get(this._currentSessionId);
        const agentId = (session?.agentId || 'general') as AgentId;
        return AGENTS[agentId] || AGENTS['general'];
    }

    // Change agent for current session
    private _changeSessionAgent(agentId: AgentId) {
        const session = this._sessions.get(this._currentSessionId);
        if (session && AGENTS[agentId]) {
            session.agentId = agentId;
            session.updatedAt = Date.now();
            this._saveSessions();
        }
    }

    private _switchSession(sessionId: string) {
        if (this._sessions.has(sessionId)) {
            this._currentSessionId = sessionId;
            this._saveSessions();
            // Clear context when switching sessions
            this._currentContext = undefined;
            this._contextFileName = undefined;
        }
    }

    private _deleteSession(sessionId: string) {
        if (this._sessions.size <= 1) {
            // Can't delete the last session
            return false;
        }

        const deleted = this._sessions.delete(sessionId);
        if (deleted) {
            // If we deleted the current session, switch to another one
            if (this._currentSessionId === sessionId) {
                const firstSession = this._sessions.values().next().value;
                if (firstSession) {
                    this._currentSessionId = firstSession.id;
                }
            }
            this._saveSessions();
        }
        return deleted;
    }

    private _renameSession(sessionId: string, newName: string) {
        const session = this._sessions.get(sessionId);
        if (session) {
            session.name = newName;
            session.updatedAt = Date.now();
            this._saveSessions();
            return true;
        }
        return false;
    }

    private _getSessionsList(): { id: string; name: string; messageCount: number; updatedAt: number; agentId: string }[] {
        return Array.from(this._sessions.values())
            .sort((a, b) => b.updatedAt - a.updatedAt) // Most recent first
            .map(s => ({
                id: s.id,
                name: s.name,
                messageCount: s.messages.length,
                updatedAt: s.updatedAt,
                agentId: s.agentId || 'general'
            }));
    }

    private _getAgentsList(): { id: string; name: string; icon: string; description: string }[] {
        return Object.values(AGENTS).map(agent => ({
            id: agent.id,
            name: agent.name,
            icon: agent.icon,
            description: agent.description
        }));
    }

    private _saveConversationHistory() {
        // Update the current session's timestamp and save all sessions
        const session = this._sessions.get(this._currentSessionId);
        if (session) {
            session.updatedAt = Date.now();
        }
        this._saveSessions();
    }

    private _loadIndexState() {
        const savedState = this._context.globalState.get<IndexState>(ChatViewProvider.INDEX_STATE_KEY);
        if (savedState && savedState.status) {
            this._indexState = savedState;
        }
    }

    private _saveIndexState() {
        this._context.globalState.update(ChatViewProvider.INDEX_STATE_KEY, this._indexState);
    }

    private _loadSettings() {
        const config = vscode.workspace.getConfiguration('cognify');
        this._currentProvider = config.get<string>('provider', 'ollama');
        this._currentModel = config.get<string>('model', 'deepseek-coder:6.7b');
    }

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken
    ) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri]
        };

        webviewView.webview.html = this._getHtmlContent();

        // Message handler - webview will send 'webviewReady' when it's initialized
        webviewView.webview.onDidReceiveMessage(async (message) => {
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
                case 'changeProvider':
                    await this._changeProvider(message.provider);
                    break;
                case 'changeModel':
                    await this._changeModel(message.model);
                    break;
                case 'getProviders':
                    this._sendProviderState();
                    break;
                case 'startIndexing':
                    await this._startIndexing(message.clear);
                    break;
                case 'selectFolderToIndex':
                    await this._selectFolderToIndex();
                    break;
                case 'skipIndexing':
                    this._skipIndexing();
                    break;
                case 'checkIndexStatus':
                    await this._checkAndInitializeIndex();
                    break;
                case 'webviewReady':
                    // Webview is ready, now send initial state
                    this._sendProviderState();
                    this._sendAgentsState();
                    this._sendSessionsState();
                    this._restoreIndexState();
                    this._restoreConversationToWebview();
                    break;
                case 'newSession':
                    this._handleNewSession(message.agentId);
                    break;
                case 'changeAgent':
                    this._handleChangeAgent(message.agentId);
                    break;
                case 'switchSession':
                    this._handleSwitchSession(message.sessionId);
                    break;
                case 'deleteSession':
                    this._handleDeleteSession(message.sessionId);
                    break;
                case 'renameSession':
                    this._handleRenameSession(message.sessionId, message.newName);
                    break;
            }
        });
    }

    private _sendSessionsState() {
        const currentAgent = this._getCurrentAgent();
        this._view?.webview.postMessage({
            command: 'sessionsState',
            sessions: this._getSessionsList(),
            currentSessionId: this._currentSessionId,
            currentAgent: {
                id: currentAgent.id,
                name: currentAgent.name,
                icon: currentAgent.icon,
                description: currentAgent.description,
                suggestions: currentAgent.suggestions
            }
        });
    }

    private _sendAgentsState() {
        const currentAgent = this._getCurrentAgent();
        this._view?.webview.postMessage({
            command: 'agentsState',
            agents: this._getAgentsList(),
            currentAgentId: currentAgent.id
        });
    }

    private _handleNewSession(agentId?: string) {
        const agent = (agentId && AGENTS[agentId as AgentId]) ? agentId as AgentId : 'general';
        const session = this._createNewSession(undefined, agent);
        this._sendSessionsState();
        this._sendAgentsState();
        // Clear the chat display for the new session
        this._view?.webview.postMessage({
            command: 'clearMessages'
        });
        // Send agent-specific welcome message
        this._sendAgentWelcome();
        // Clear context
        this._currentContext = undefined;
        this._contextFileName = undefined;
        this._view?.webview.postMessage({
            command: 'updateContext',
            hasContext: false
        });
    }

    private _handleChangeAgent(agentId: string) {
        if (AGENTS[agentId as AgentId]) {
            this._changeSessionAgent(agentId as AgentId);
            this._sendSessionsState();
            this._sendAgentsState();
            // Send agent-specific welcome message
            this._sendAgentWelcome();
        }
    }

    private _sendAgentWelcome() {
        const agent = this._getCurrentAgent();
        this._view?.webview.postMessage({
            command: 'agentWelcome',
            agent: {
                id: agent.id,
                name: agent.name,
                icon: agent.icon,
                description: agent.description,
                suggestions: agent.suggestions
            }
        });
    }

    private _handleSwitchSession(sessionId: string) {
        this._switchSession(sessionId);
        this._sendSessionsState();
        this._sendAgentsState();
        this._restoreConversationToWebview();
        // Clear context display (context is per-session interaction)
        this._currentContext = undefined;
        this._contextFileName = undefined;
        this._view?.webview.postMessage({
            command: 'updateContext',
            hasContext: false
        });
    }

    private _handleDeleteSession(sessionId: string) {
        const deleted = this._deleteSession(sessionId);
        if (deleted) {
            this._sendSessionsState();
            this._sendAgentsState();
            this._restoreConversationToWebview();
        } else {
            vscode.window.showWarningMessage('Cannot delete the last chat session');
        }
    }

    private _handleRenameSession(sessionId: string, newName: string) {
        if (this._renameSession(sessionId, newName)) {
            this._sendSessionsState();
        }
    }

    private _restoreConversationToWebview() {
        // Clear messages first, then restore
        this._view?.webview.postMessage({
            command: 'clearMessages'
        });

        // Send all previous messages to the webview to restore the chat history
        if (this._conversationHistory.length > 0) {
            this._view?.webview.postMessage({
                command: 'restoreHistory',
                messages: this._conversationHistory
            });
        }
    }

    private _restoreIndexState() {
        // If we have a cached "indexed" state, just send it without re-checking
        if (this._indexState.status === 'indexed' && this._indexState.chunkCount > 0) {
            this._sendIndexState();
        } else if (this._indexState.status === 'not_indexed' || this._indexState.status === 'unknown') {
            // Only check index status if we don't have a valid cached state
            this._checkAndInitializeIndex();
        } else {
            // For other states (error, indexing), send current state
            this._sendIndexState();
        }
    }

    private _sendProviderState() {
        this._view?.webview.postMessage({
            command: 'providerState',
            providers: this._providers,
            currentProvider: this._currentProvider,
            currentModel: this._currentModel
        });
    }

    private async _changeProvider(provider: string) {
        if (this._providers[provider]) {
            this._currentProvider = provider;
            // Set to first model of the provider
            this._currentModel = this._providers[provider][0];

            // Update VSCode settings
            const config = vscode.workspace.getConfiguration('cognify');
            await config.update('provider', provider, vscode.ConfigurationTarget.Global);
            await config.update('model', this._currentModel, vscode.ConfigurationTarget.Global);

            this._sendProviderState();
            vscode.window.showInformationMessage(`Switched to ${provider} with model ${this._currentModel}`);
        }
    }

    private async _changeModel(model: string) {
        this._currentModel = model;

        // Update VSCode settings
        const config = vscode.workspace.getConfiguration('cognify');
        await config.update('model', model, vscode.ConfigurationTarget.Global);

        this._sendProviderState();
    }

    // ==================== Indexing Methods ====================

    private _sendIndexState() {
        this._view?.webview.postMessage({
            command: 'indexState',
            ...this._indexState
        });
    }

    private async _checkAndInitializeIndex() {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];

        // Update state to checking (don't save this temporary state)
        this._indexState = { status: 'checking', chunkCount: 0, fileCount: 0 };
        this._sendIndexState();

        if (!workspaceFolder) {
            // No workspace open
            this._indexState = {
                status: 'not_indexed',
                chunkCount: 0,
                fileCount: 0,
                error: 'no_workspace'
            };
            this._sendIndexState();
            return;
        }

        try {
            const status = await this._cognifyRunner.checkIndexStatus(workspaceFolder.uri.fsPath);

            if (status.indexed) {
                this._indexState = {
                    status: 'indexed',
                    chunkCount: status.chunkCount,
                    fileCount: status.fileCount || 0
                };
                this._saveIndexState(); // Persist indexed state
            } else {
                this._indexState = {
                    status: 'not_indexed',
                    chunkCount: 0,
                    fileCount: 0
                };
                // Auto-start indexing for workspace
                this._promptForIndexing();
            }
        } catch (error) {
            this._indexState = {
                status: 'error',
                chunkCount: 0,
                fileCount: 0,
                error: error instanceof Error ? error.message : 'Failed to check index'
            };
        }

        this._sendIndexState();
    }

    private _promptForIndexing() {
        // Send message to webview to show indexing prompt
        this._view?.webview.postMessage({
            command: 'showIndexPrompt',
            hasWorkspace: !!vscode.workspace.workspaceFolders?.[0]
        });
    }

    private async _startIndexing(clear: boolean = false) {
        if (this._isIndexing) {
            vscode.window.showWarningMessage('Indexing is already in progress');
            return;
        }

        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            vscode.window.showErrorMessage('No workspace folder open');
            return;
        }

        this._isIndexing = true;
        this._indexState = { status: 'indexing', chunkCount: 0, fileCount: 0 };
        this._sendIndexState();

        // Send initial indexing message
        this._view?.webview.postMessage({
            command: 'indexProgress',
            message: '🔍 Starting indexing...',
            current: 0,
            total: 0
        });

        try {
            const result = await this._cognifyRunner.indexWorkspace(
                workspaceFolder.uri.fsPath,
                {
                    clear,
                    onProgress: (progress) => {
                        this._indexState.progress = progress;
                        this._view?.webview.postMessage({
                            command: 'indexProgress',
                            message: `📁 Indexing files... ${progress.current}/${progress.total}`,
                            current: progress.current,
                            total: progress.total
                        });
                    }
                }
            );

            if (result.success) {
                this._indexState = {
                    status: 'indexed',
                    chunkCount: result.chunksCreated,
                    fileCount: result.filesIndexed
                };
                this._saveIndexState(); // Persist indexed state
                this._view?.webview.postMessage({
                    command: 'indexComplete',
                    success: true,
                    message: `✅ Workspace indexed! ${result.filesIndexed} files, ${result.chunksCreated} chunks`,
                    filesIndexed: result.filesIndexed,
                    chunksCreated: result.chunksCreated
                });
            } else {
                this._indexState = {
                    status: 'error',
                    chunkCount: 0,
                    fileCount: 0,
                    error: result.errors.join(', ')
                };
                this._view?.webview.postMessage({
                    command: 'indexComplete',
                    success: false,
                    message: `❌ Indexing failed: ${result.errors.join(', ')}`,
                    errors: result.errors
                });
            }
        } catch (error) {
            this._indexState = {
                status: 'error',
                chunkCount: 0,
                fileCount: 0,
                error: error instanceof Error ? error.message : 'Indexing failed'
            };
            this._view?.webview.postMessage({
                command: 'indexComplete',
                success: false,
                message: `❌ Indexing error: ${error instanceof Error ? error.message : 'Unknown error'}`
            });
        } finally {
            this._isIndexing = false;
            this._sendIndexState();
        }
    }

    private async _selectFolderToIndex() {
        const folderUri = await vscode.window.showOpenDialog({
            canSelectFiles: false,
            canSelectFolders: true,
            canSelectMany: false,
            openLabel: 'Select Folder to Index'
        });

        if (folderUri && folderUri[0]) {
            // Open the folder as workspace
            await vscode.commands.executeCommand('vscode.openFolder', folderUri[0]);
        }
    }

    private _skipIndexing() {
        this._indexState = { status: 'not_indexed', chunkCount: 0, fileCount: 0 };
        this._sendIndexState();
        this._view?.webview.postMessage({
            command: 'indexSkipped',
            message: '⏭️ Indexing skipped. You can still chat, but codebase search won\'t be available.'
        });
    }

    // ==================== End Indexing Methods ====================

    private async _handleMessage(text: string) {
        if (!this._view) return;

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

        this._conversationHistory.push({
            role: 'user',
            content: text,
            context: contextToUse,
            timestamp: Date.now()
        });
        this._saveConversationHistory();

        this._view.webview.postMessage({ command: 'thinking', thinking: true });

        try {
            // Automatically search for relevant code if workspace is indexed
            let searchContext: string | undefined;
            if (this._indexState.status === 'indexed' && this._indexState.chunkCount > 0) {
                try {
                    // Search for relevant code based on user's message
                    searchContext = await this._cognifyRunner.searchCodebase(text, {
                        topK: 5,  // Get top 5 most relevant code chunks
                        language: language !== 'plaintext' ? language : undefined
                    });

                    // Only use search context if we got meaningful results
                    if (searchContext && searchContext.includes('No relevant code found')) {
                        searchContext = undefined;
                    }
                } catch (searchError) {
                    // Silently fail - search is optional enhancement
                    console.log('Search failed, continuing without search context:', searchError);
                }
            }

            // Search knowledge base for relevant patterns and learnings
            let knowledgeContext: string | undefined;
            try {
                knowledgeContext = await this._cognifyRunner.searchKnowledge(text, { limit: 3 });
                // Only use if we got meaningful results
                if (knowledgeContext && (knowledgeContext.includes('No matching knowledge') || knowledgeContext.trim() === '')) {
                    knowledgeContext = undefined;
                }
            } catch (knowledgeError) {
                // Silently fail - knowledge is optional enhancement
                console.log('Knowledge search failed:', knowledgeError);
            }

            // Combine search contexts
            let combinedSearchContext = searchContext || '';
            if (knowledgeContext) {
                combinedSearchContext = knowledgeContext + (combinedSearchContext ? '\n\n' + combinedSearchContext : '');
            }

            const historyForApi: ChatMessage[] = this._conversationHistory
                .slice(-10)
                .map(msg => ({ role: msg.role, content: msg.content }));

            // Get current agent's system prompt
            const currentAgent = this._getCurrentAgent();

            const result = await this._cognifyRunner.smartChat(text, {
                context: contextToUse,
                searchContext: combinedSearchContext || undefined,  // Include both knowledge and codebase search
                language,
                history: historyForApi.slice(0, -1),
                systemPrompt: currentAgent.systemPrompt,
                provider: this._currentProvider,  // Pass selected provider to CLI
                model: this._currentModel          // Pass selected model to CLI
            });

            this._conversationHistory.push({
                role: 'assistant',
                content: result.response,
                timestamp: Date.now()
            });
            this._saveConversationHistory();

            this._view.webview.postMessage({
                command: 'response',
                text: result.response,
                intent: result.intent,
                hasCode: result.hasCode
            });
        } catch (error) {
            this._view.webview.postMessage({
                command: 'error',
                text: `Error: ${error}`
            });
        }
    }

    private async _addContext() {
        if (!this._view) return;
        
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showWarningMessage('No file open. Please open a file first.');
            return;
        }

        const selection = editor.selection;
        if (selection.isEmpty) {
            this._currentContext = editor.document.getText();
            this._contextFileName = editor.document.fileName.split('/').pop() || 'file';
        } else {
            this._currentContext = editor.document.getText(selection);
            const lineCount = selection.end.line - selection.start.line + 1;
            this._contextFileName = `${editor.document.fileName.split('/').pop()} (${lineCount} lines)`;
        }

        this._view.webview.postMessage({
            command: 'contextAdded',
            fileName: this._contextFileName,
            preview: this._currentContext.substring(0, 100) + (this._currentContext.length > 100 ? '...' : '')
        });
    }

    private _clearContext() {
        this._currentContext = undefined;
        this._contextFileName = undefined;
        this._view?.webview.postMessage({ command: 'contextCleared' });
    }

    private _clearHistory() {
        this._conversationHistory = [];
        this._saveConversationHistory();
        this._view?.webview.postMessage({ command: 'historyCleared' });
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
            await editor.edit(editBuilder => {
                editBuilder.insert(editor.selection.active, code);
            });
        } else {
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
            font-size: var(--vscode-font-size);
            color: var(--vscode-foreground);
            background: var(--vscode-sideBar-background);
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        .header {
            padding: 8px 12px;
            border-bottom: 1px solid var(--vscode-panel-border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h3 { font-size: 13px; font-weight: 600; }
        .header button {
            background: transparent;
            border: none;
            color: var(--vscode-foreground);
            cursor: pointer;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
        }
        .header button:hover { background: var(--vscode-toolbar-hoverBackground); }
        .context-bar {
            padding: 6px 12px;
            background: var(--vscode-editor-inactiveSelectionBackground);
            border-bottom: 1px solid var(--vscode-panel-border);
            display: none;
            align-items: center;
            gap: 8px;
            font-size: 11px;
        }
        .context-bar.active { display: flex; }
        .context-badge {
            background: var(--vscode-badge-background);
            color: var(--vscode-badge-foreground);
            padding: 2px 6px;
            border-radius: 10px;
            font-size: 10px;
        }
        .context-bar .clear-btn {
            margin-left: auto;
            background: transparent;
            border: none;
            color: var(--vscode-foreground);
            cursor: pointer;
            opacity: 0.7;
        }
        .context-bar .clear-btn:hover { opacity: 1; }
        .messages {
            flex: 1;
            overflow-y: auto;
            padding: 12px;
        }
        .message {
            margin-bottom: 12px;
            padding: 8px 12px;
            border-radius: 8px;
            max-width: 95%;
        }
        .message.user {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            margin-left: auto;
        }
        .message.assistant {
            background: var(--vscode-editor-background);
            border: 1px solid var(--vscode-panel-border);
        }
        .intent-badge {
            display: inline-block;
            font-size: 9px;
            padding: 2px 6px;
            border-radius: 8px;
            margin-bottom: 6px;
            text-transform: uppercase;
            font-weight: 600;
        }
        .intent-badge.generate { background: #2e7d32; color: white; }
        .intent-badge.review { background: #1565c0; color: white; }
        .intent-badge.edit { background: #7b1fa2; color: white; }
        .intent-badge.explain { background: #ef6c00; color: white; }
        .intent-badge.chat { background: #455a64; color: white; }
        pre {
            background: var(--vscode-textCodeBlock-background);
            padding: 8px;
            border-radius: 4px;
            overflow-x: auto;
            margin: 8px 0;
            font-size: 12px;
        }
        code {
            font-family: var(--vscode-editor-font-family);
        }
        .code-actions {
            display: flex;
            gap: 4px;
            margin-top: 4px;
        }
        .code-actions button {
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
            border: none;
            padding: 3px 8px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 10px;
        }
        .code-actions button:hover {
            background: var(--vscode-button-secondaryHoverBackground);
        }
        .thinking {
            display: none;
            padding: 12px;
            color: var(--vscode-descriptionForeground);
            font-style: italic;
        }
        .thinking.active { display: block; }
        .input-area {
            padding: 8px 12px;
            border-top: 1px solid var(--vscode-panel-border);
            background: var(--vscode-sideBar-background);
        }
        .input-row {
            display: flex;
            gap: 6px;
        }
        #messageInput {
            flex: 1;
            padding: 8px;
            border: 1px solid var(--vscode-input-border);
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            border-radius: 4px;
            font-size: 12px;
            resize: none;
        }
        #messageInput:focus {
            outline: 1px solid var(--vscode-focusBorder);
        }
        .send-btn {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            padding: 8px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 500;
        }
        .send-btn:hover {
            background: var(--vscode-button-hoverBackground);
        }
        .action-row {
            margin-top: 6px;
            display: flex;
            gap: 6px;
        }
        .action-row button {
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
            border: none;
            padding: 4px 8px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 11px;
        }
        .action-row button:hover {
            background: var(--vscode-button-secondaryHoverBackground);
        }
        .suggestions {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            padding: 8px 12px;
        }
        .suggestion-chip {
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
            border: none;
            padding: 4px 10px;
            border-radius: 12px;
            cursor: pointer;
            font-size: 11px;
        }
        .suggestion-chip:hover {
            background: var(--vscode-button-secondaryHoverBackground);
        }
        .model-selector {
            padding: 6px 12px;
            background: var(--vscode-editor-background);
            border-bottom: 1px solid var(--vscode-panel-border);
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 11px;
        }
        .model-selector label {
            opacity: 0.8;
        }
        .model-selector select {
            background: var(--vscode-dropdown-background);
            color: var(--vscode-dropdown-foreground);
            border: 1px solid var(--vscode-dropdown-border);
            padding: 3px 6px;
            border-radius: 3px;
            font-size: 11px;
            cursor: pointer;
            flex: 1;
            max-width: 120px;
        }
        .model-selector select:focus {
            outline: 1px solid var(--vscode-focusBorder);
        }
        .model-info {
            font-size: 10px;
            opacity: 0.6;
            margin-left: auto;
        }
        /* Indexing UI Styles */
        .index-status {
            padding: 8px 12px;
            background: var(--vscode-editor-background);
            border-bottom: 1px solid var(--vscode-panel-border);
            font-size: 11px;
            display: none;
        }
        .index-status.active { display: block; }
        .index-status.success { background: rgba(46, 125, 50, 0.15); }
        .index-status.warning { background: rgba(255, 152, 0, 0.15); }
        .index-status.error { background: rgba(211, 47, 47, 0.15); }
        .index-status .status-text {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .index-status .progress-bar {
            height: 3px;
            background: var(--vscode-progressBar-background);
            border-radius: 2px;
            margin-top: 6px;
            overflow: hidden;
        }
        .index-status .progress-fill {
            height: 100%;
            background: var(--vscode-button-background);
            transition: width 0.3s ease;
        }
        .index-prompt {
            padding: 12px;
            background: var(--vscode-editor-background);
            border: 1px solid var(--vscode-panel-border);
            border-radius: 6px;
            margin: 12px;
            display: none;
        }
        .index-prompt.active { display: block; }
        .index-prompt h4 {
            font-size: 12px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .index-prompt p {
            font-size: 11px;
            opacity: 0.8;
            margin-bottom: 10px;
        }
        .index-prompt .btn-group {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }
        .index-prompt button {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 11px;
        }
        .index-prompt button:hover {
            background: var(--vscode-button-hoverBackground);
        }
        .index-prompt button.secondary {
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
        }
        .index-prompt button.secondary:hover {
            background: var(--vscode-button-secondaryHoverBackground);
        }
        .index-badge {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            font-size: 10px;
            padding: 2px 6px;
            border-radius: 10px;
            background: var(--vscode-badge-background);
            color: var(--vscode-badge-foreground);
        }
        .spinner {
            display: inline-block;
            width: 12px;
            height: 12px;
            border: 2px solid var(--vscode-foreground);
            border-radius: 50%;
            border-top-color: transparent;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        /* Session Selector Styles */
        .session-bar {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            background: var(--vscode-editor-background);
            border-bottom: 1px solid var(--vscode-panel-border);
        }
        .session-bar select {
            flex: 1;
            padding: 4px 8px;
            background: var(--vscode-dropdown-background);
            color: var(--vscode-dropdown-foreground);
            border: 1px solid var(--vscode-dropdown-border);
            border-radius: 4px;
            font-size: 11px;
            cursor: pointer;
        }
        .session-bar button {
            background: transparent;
            border: none;
            color: var(--vscode-foreground);
            cursor: pointer;
            padding: 4px 6px;
            border-radius: 4px;
            font-size: 12px;
            opacity: 0.8;
        }
        .session-bar button:hover {
            background: var(--vscode-toolbar-hoverBackground);
            opacity: 1;
        }
        .session-bar button.new-chat {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            opacity: 1;
        }
        .session-bar button.new-chat:hover {
            background: var(--vscode-button-hoverBackground);
        }
        /* Agent Selector Styles */
        .agent-bar {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 12px;
            background: var(--vscode-editor-background);
            border-bottom: 1px solid var(--vscode-panel-border);
        }
        .agent-bar .agent-icon {
            font-size: 16px;
        }
        .agent-bar select {
            flex: 1;
            padding: 4px 8px;
            background: var(--vscode-dropdown-background);
            color: var(--vscode-dropdown-foreground);
            border: 1px solid var(--vscode-dropdown-border);
            border-radius: 4px;
            font-size: 11px;
            cursor: pointer;
        }
        .agent-badge {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            font-size: 10px;
            padding: 2px 8px;
            border-radius: 10px;
            background: var(--vscode-badge-background);
            color: var(--vscode-badge-foreground);
        }
        .agent-welcome {
            text-align: center;
            padding: 20px;
            border-bottom: 1px solid var(--vscode-panel-border);
        }
        .agent-welcome .agent-emoji {
            font-size: 32px;
            margin-bottom: 8px;
        }
        .agent-welcome h4 {
            font-size: 14px;
            margin-bottom: 4px;
        }
        .agent-welcome p {
            font-size: 11px;
            opacity: 0.8;
        }
    </style>
</head>
<body>
    <!-- Session Selector Bar -->
    <div class="session-bar">
        <select id="sessionSelect" onchange="switchSession(this.value)">
            <option value="">Loading...</option>
        </select>
        <button class="new-chat" onclick="newSession()" title="New Chat">➕</button>
        <button onclick="renameCurrentSession()" title="Rename Chat">✏️</button>
        <button onclick="deleteCurrentSession()" title="Delete Chat">🗑️</button>
    </div>
    <!-- Agent Selector Bar -->
    <div class="agent-bar">
        <span class="agent-icon" id="currentAgentIcon">💬</span>
        <select id="agentSelect" onchange="changeAgent(this.value)">
            <option value="general">💬 General Assistant</option>
            <option value="reviewer">🔍 Code Reviewer</option>
            <option value="generator">✨ Code Generator</option>
            <option value="documenter">📝 Documentation Writer</option>
            <option value="tester">🧪 Test Writer</option>
        </select>
    </div>
    <div class="header">
        <h3>⚛️ Cognify AI</h3>
        <button onclick="clearHistory()">Clear Chat</button>
    </div>
    <div class="model-selector">
        <label>🤖</label>
        <select id="providerSelect" onchange="changeProvider(this.value)">
            <option value="ollama">Ollama</option>
            <option value="groq">Groq</option>
            <option value="google">Google</option>
            <option value="openai">OpenAI</option>
            <option value="cerebras">Cerebras</option>
            <option value="openrouter">OpenRouter</option>
        </select>
        <select id="modelSelect" onchange="changeModel(this.value)">
            <option value="loading">Loading...</option>
        </select>
    </div>
    <!-- Index Status Bar -->
    <div class="index-status" id="indexStatus">
        <div class="status-text" id="indexStatusText">
            <span class="spinner"></span>
            <span>Checking index...</span>
        </div>
        <div class="progress-bar" id="indexProgressBar" style="display:none;">
            <div class="progress-fill" id="indexProgressFill" style="width:0%"></div>
        </div>
    </div>
    <!-- Index Prompt (shown when no index exists) -->
    <div class="index-prompt" id="indexPrompt">
        <h4>📚 Codebase Indexing</h4>
        <p id="indexPromptText">Index your workspace for semantic code search capabilities.</p>
        <div class="btn-group">
            <button onclick="startIndexing(false)">🔍 Index Workspace</button>
            <button class="secondary" onclick="skipIndexing()">Skip</button>
        </div>
    </div>
    <div class="context-bar" id="contextBar">
        <span>📎 Context:</span>
        <span class="context-badge" id="contextName"></span>
        <button class="clear-btn" onclick="clearContext()">✕</button>
    </div>
    <div class="messages" id="messages">
        <div class="message assistant">
            <p>👋 Hi! I'm Cognify AI. Ask me anything about code!</p>
            <p style="font-size:11px;margin-top:8px;opacity:0.8">Try: "write a function", "review this code", or just chat!</p>
        </div>
    </div>
    <div class="thinking" id="thinking">🤔 Thinking...</div>
    <div class="suggestions">
        <button class="suggestion-chip" onclick="sendSuggestion('Write a function to')">✨ Generate</button>
        <button class="suggestion-chip" onclick="sendSuggestion('Review this code')">🔍 Review</button>
        <button class="suggestion-chip" onclick="sendSuggestion('Explain this code')">💡 Explain</button>
    </div>
    <div class="input-area">
        <div class="input-row">
            <textarea id="messageInput" rows="2" placeholder="Ask anything about code..."></textarea>
            <button class="send-btn" onclick="sendMessage()">Send</button>
        </div>
        <div class="action-row">
            <button onclick="addContext()">📎 Add Context</button>
        </div>
    </div>
    <script>
        const vscode = acquireVsCodeApi();
        const messagesDiv = document.getElementById('messages');
        const input = document.getElementById('messageInput');
        const thinking = document.getElementById('thinking');
        const contextBar = document.getElementById('contextBar');
        const contextName = document.getElementById('contextName');

        function sendMessage() {
            const text = input.value.trim();
            if (!text) return;
            addMessage(text, 'user');
            vscode.postMessage({ command: 'sendMessage', text });
            input.value = '';
        }

        function sendSuggestion(text) {
            input.value = text;
            input.focus();
        }

        function addMessage(text, role, intent = null, hasCode = false) {
            const div = document.createElement('div');
            div.className = 'message ' + role;

            if (role === 'assistant' && intent) {
                const badge = document.createElement('div');
                badge.className = 'intent-badge ' + intent;
                badge.textContent = intent;
                div.appendChild(badge);
            }

            div.innerHTML += formatMessage(text);
            messagesDiv.appendChild(div);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        function formatMessage(text) {
            // Handle code blocks
            text = text.replace(/\`\`\`(\\w*)\\n([\\s\\S]*?)\`\`\`/g, (match, lang, code) => {
                const id = 'code-' + Math.random().toString(36).substr(2, 9);
                return '<pre><code>' + escapeHtml(code.trim()) + '</code></pre>' +
                    '<div class="code-actions">' +
                    '<button onclick="copyCode(\\'' + id + '\\')">📋 Copy</button>' +
                    '<button onclick="insertCode(\\'' + id + '\\')">📥 Insert</button>' +
                    '<button onclick="applyCode(\\'' + id + '\\')">✅ Apply</button>' +
                    '</div>' +
                    '<textarea id="' + id + '" style="display:none">' + escapeHtml(code.trim()) + '</textarea>';
            });
            // Handle inline code
            text = text.replace(/\`([^\`]+)\`/g, '<code>$1</code>');
            // Handle bold
            text = text.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');
            // Handle paragraphs
            text = text.split('\\n\\n').map(p => '<p>' + p + '</p>').join('');
            return text;
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function copyCode(id) {
            const code = document.getElementById(id).value;
            navigator.clipboard.writeText(code);
        }

        function insertCode(id) {
            const code = document.getElementById(id).value;
            vscode.postMessage({ command: 'insertCode', code });
        }

        function applyCode(id) {
            const code = document.getElementById(id).value;
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

        // ==================== Session Management ====================
        const sessionSelect = document.getElementById('sessionSelect');
        let currentSessionId = '';

        function newSession() {
            vscode.postMessage({ command: 'newSession' });
        }

        function switchSession(sessionId) {
            if (sessionId && sessionId !== currentSessionId) {
                vscode.postMessage({ command: 'switchSession', sessionId });
            }
        }

        function deleteCurrentSession() {
            if (currentSessionId) {
                vscode.postMessage({ command: 'deleteSession', sessionId: currentSessionId });
            }
        }

        function renameCurrentSession() {
            if (currentSessionId) {
                const currentOption = sessionSelect.options[sessionSelect.selectedIndex];
                const currentName = currentOption ? currentOption.text.split(' (')[0] : 'Chat';
                const newName = prompt('Enter new name for this chat:', currentName);
                if (newName && newName.trim()) {
                    vscode.postMessage({ command: 'renameSession', sessionId: currentSessionId, newName: newName.trim() });
                }
            }
        }

        function updateSessionsDropdown(sessions, activeId) {
            sessionSelect.innerHTML = '';
            sessions.forEach(session => {
                const option = document.createElement('option');
                option.value = session.id;
                const msgCount = session.messageCount > 0 ? ' (' + session.messageCount + ')' : '';
                option.textContent = session.name + msgCount;
                if (session.id === activeId) {
                    option.selected = true;
                }
                sessionSelect.appendChild(option);
            });
            currentSessionId = activeId;
        }
        // ==================== End Session Management ====================

        // ==================== Agent Management ====================
        const agentSelect = document.getElementById('agentSelect');
        const currentAgentIcon = document.getElementById('currentAgentIcon');
        let currentAgentId = 'general';
        const agentIcons = {
            'general': '💬',
            'reviewer': '🔍',
            'generator': '✨',
            'documenter': '📝',
            'tester': '🧪'
        };

        function changeAgent(agentId) {
            if (agentId && agentId !== currentAgentId) {
                vscode.postMessage({ command: 'changeAgent', agentId });
            }
        }

        function updateAgentUI(agentId) {
            currentAgentId = agentId;
            agentSelect.value = agentId;
            currentAgentIcon.textContent = agentIcons[agentId] || '💬';
        }

        function showAgentWelcome(agent) {
            // Clear existing messages and show agent-specific welcome
            messagesDiv.innerHTML = '';
            const welcomeDiv = document.createElement('div');
            welcomeDiv.className = 'message assistant';
            welcomeDiv.innerHTML = '<p style="font-size:20px;text-align:center;margin-bottom:8px;">' + agent.icon + '</p>' +
                '<p style="text-align:center;font-weight:bold;">' + agent.name + '</p>' +
                '<p style="text-align:center;font-size:11px;opacity:0.8;margin-top:4px;">' + agent.description + '</p>';
            messagesDiv.appendChild(welcomeDiv);

            // Update suggestions based on agent
            updateSuggestions(agent.suggestions || []);
        }

        function updateSuggestions(suggestions) {
            const suggestionsDiv = document.querySelector('.suggestions');
            if (suggestions && suggestions.length > 0) {
                suggestionsDiv.innerHTML = suggestions.map(s =>
                    '<button class="suggestion-chip" onclick="sendSuggestion(\\'' + escapeHtml(s) + '\\')">' + s + '</button>'
                ).join('');
            }
        }
        // ==================== End Agent Management ====================

        // ==================== Indexing UI ====================
        const indexStatus = document.getElementById('indexStatus');
        const indexStatusText = document.getElementById('indexStatusText');
        const indexProgressBar = document.getElementById('indexProgressBar');
        const indexProgressFill = document.getElementById('indexProgressFill');
        const indexPrompt = document.getElementById('indexPrompt');
        const indexPromptText = document.getElementById('indexPromptText');

        function startIndexing(clear) {
            vscode.postMessage({ command: 'startIndexing', clear: clear });
            indexPrompt.classList.remove('active');
        }

        function skipIndexing() {
            vscode.postMessage({ command: 'skipIndexing' });
            indexPrompt.classList.remove('active');
        }

        function selectFolderToIndex() {
            vscode.postMessage({ command: 'selectFolderToIndex' });
        }

        function updateIndexStatus(status, message, type) {
            indexStatus.className = 'index-status active ' + (type || '');
            indexStatusText.innerHTML = message;
        }

        function updateIndexProgress(current, total) {
            if (total > 0) {
                const percent = (current / total) * 100;
                indexProgressBar.style.display = 'block';
                indexProgressFill.style.width = percent + '%';
            } else {
                indexProgressBar.style.display = 'none';
            }
        }
        // ==================== End Indexing UI ====================

        // Model selector functions
        const providerSelect = document.getElementById('providerSelect');
        const modelSelect = document.getElementById('modelSelect');
        let providers = {};

        function changeProvider(provider) {
            vscode.postMessage({ command: 'changeProvider', provider });
        }

        function changeModel(model) {
            vscode.postMessage({ command: 'changeModel', model });
        }

        function updateModelDropdown(models, currentModel) {
            modelSelect.innerHTML = '';
            models.forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                if (model === currentModel) {
                    option.selected = true;
                }
                modelSelect.appendChild(option);
            });
        }

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        window.addEventListener('message', (event) => {
            const msg = event.data;
            switch (msg.command) {
                case 'thinking':
                    thinking.classList.toggle('active', msg.thinking);
                    break;
                case 'response':
                    thinking.classList.remove('active');
                    addMessage(msg.text, 'assistant', msg.intent, msg.hasCode);
                    break;
                case 'error':
                    thinking.classList.remove('active');
                    addMessage('❌ ' + msg.text, 'assistant');
                    break;
                case 'contextAdded':
                    contextBar.classList.add('active');
                    contextName.textContent = msg.fileName;
                    break;
                case 'contextCleared':
                    contextBar.classList.remove('active');
                    break;
                case 'historyCleared':
                    messagesDiv.innerHTML = '<div class="message assistant"><p>👋 Chat cleared. How can I help?</p></div>';
                    break;
                case 'restoreHistory':
                    // Restore previous conversation history
                    if (msg.messages && msg.messages.length > 0) {
                        // Clear the default welcome message
                        messagesDiv.innerHTML = '';
                        // Add all previous messages
                        msg.messages.forEach(message => {
                            addMessage(message.content, message.role);
                        });
                    }
                    break;
                case 'providerState':
                    providers = msg.providers;
                    providerSelect.value = msg.currentProvider;
                    updateModelDropdown(providers[msg.currentProvider] || [], msg.currentModel);
                    break;
                // ==================== Session Messages ====================
                case 'sessionsState':
                    updateSessionsDropdown(msg.sessions, msg.currentSessionId);
                    if (msg.currentAgent) {
                        updateAgentUI(msg.currentAgent.id);
                    }
                    break;
                case 'clearMessages':
                    messagesDiv.innerHTML = '<div class="message assistant"><p>👋 Hi! I\\'m Cognify AI. Ask me anything about code!</p><p style="font-size:11px;margin-top:8px;opacity:0.8">Try: "write a function", "review this code", or just chat!</p></div>';
                    break;
                case 'updateContext':
                    if (msg.hasContext) {
                        contextBar.classList.add('active');
                    } else {
                        contextBar.classList.remove('active');
                    }
                    break;
                // ==================== End Session Messages ====================
                // ==================== Agent Messages ====================
                case 'agentsState':
                    updateAgentUI(msg.currentAgentId);
                    break;
                case 'agentWelcome':
                    showAgentWelcome(msg.agent);
                    break;
                // ==================== End Agent Messages ====================
                // ==================== Indexing Messages ====================
                case 'indexState':
                    if (msg.status === 'checking') {
                        updateIndexStatus('checking', '<span class="spinner"></span> Checking index...', '');
                    } else if (msg.status === 'indexed') {
                        updateIndexStatus('indexed', '✅ Indexed: ' + msg.chunkCount + ' chunks', 'success');
                        indexProgressBar.style.display = 'none';
                    } else if (msg.status === 'not_indexed') {
                        indexStatus.classList.remove('active');
                    } else if (msg.status === 'indexing') {
                        updateIndexStatus('indexing', '<span class="spinner"></span> Indexing workspace...', '');
                    } else if (msg.status === 'error') {
                        updateIndexStatus('error', '❌ Error: ' + msg.error, 'error');
                    }
                    break;
                case 'showIndexPrompt':
                    if (msg.hasWorkspace) {
                        indexPromptText.textContent = 'Index your workspace for semantic code search capabilities.';
                    } else {
                        indexPromptText.textContent = 'No workspace detected. Select a folder to index for semantic code search.';
                    }
                    indexPrompt.classList.add('active');
                    break;
                case 'indexProgress':
                    updateIndexStatus('indexing', '<span class="spinner"></span> ' + msg.message, '');
                    updateIndexProgress(msg.current, msg.total);
                    break;
                case 'indexComplete':
                    if (msg.success) {
                        updateIndexStatus('indexed', msg.message, 'success');
                        indexProgressBar.style.display = 'none';
                    } else {
                        updateIndexStatus('error', msg.message, 'error');
                        indexProgressBar.style.display = 'none';
                    }
                    break;
                case 'indexSkipped':
                    updateIndexStatus('skipped', msg.message, 'warning');
                    setTimeout(function() { indexStatus.classList.remove('active'); }, 3000);
                    break;
                // ==================== End Indexing Messages ====================
            }
        });

        // Notify extension that webview is ready - this triggers all initialization
        vscode.postMessage({ command: 'webviewReady' });
    </script>
</body>
</html>`;
    }
}

