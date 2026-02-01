import * as vscode from 'vscode';
import { CognifyRunner } from './cognifyRunner';
import { ChatPanel } from './chatPanel';
import { ChatViewProvider } from './chatViewProvider';
import { StatusBarManager } from './statusBar';
import { DiagnosticsManager } from './diagnostics';

let cognifyRunner: CognifyRunner;
let chatPanel: ChatPanel | undefined;
let chatViewProvider: ChatViewProvider;
let statusBarManager: StatusBarManager;
let diagnosticsManager: DiagnosticsManager;

export function activate(context: vscode.ExtensionContext) {
    console.log('Cognify AI extension is now active!');

    // Initialize components
    cognifyRunner = new CognifyRunner();
    statusBarManager = new StatusBarManager();
    diagnosticsManager = new DiagnosticsManager();

    // Register the sidebar chat view provider
    chatViewProvider = new ChatViewProvider(context.extensionUri, cognifyRunner);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(
            ChatViewProvider.viewType,
            chatViewProvider
        )
    );

    // Register commands
    const commands = [
        vscode.commands.registerCommand('cognify.reviewFile', () => reviewFile()),
        vscode.commands.registerCommand('cognify.reviewSelection', () => reviewSelection()),
        vscode.commands.registerCommand('cognify.generateCode', () => generateCode()),
        vscode.commands.registerCommand('cognify.editCode', () => editCode()),
        vscode.commands.registerCommand('cognify.explainCode', () => explainCode()),
        vscode.commands.registerCommand('cognify.openChat', () => openChat(context)),
        vscode.commands.registerCommand('cognify.checkStatus', () => checkStatus()),
        vscode.commands.registerCommand('cognify.switchProvider', () => switchProvider()),
    ];

    commands.forEach(cmd => context.subscriptions.push(cmd));
    context.subscriptions.push(statusBarManager.statusBarItem);

    // Check status on activation
    checkStatusSilent();
}

async function reviewFile() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showWarningMessage('No active file to review');
        return;
    }

    const filePath = editor.document.uri.fsPath;
    statusBarManager.setLoading('Reviewing...');

    try {
        const result = await cognifyRunner.reviewFile(filePath);
        diagnosticsManager.setDiagnostics(editor.document.uri, result.issues);
        showReviewResult(result);
        statusBarManager.setReady();
    } catch (error) {
        statusBarManager.setError();
        vscode.window.showErrorMessage(`Review failed: ${error}`);
    }
}

async function reviewSelection() {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.selection.isEmpty) {
        vscode.window.showWarningMessage('No code selected');
        return;
    }

    const code = editor.document.getText(editor.selection);
    const language = editor.document.languageId;
    statusBarManager.setLoading('Reviewing selection...');

    try {
        const result = await cognifyRunner.reviewCode(code, language);
        showReviewResult(result);
        statusBarManager.setReady();
    } catch (error) {
        statusBarManager.setError();
        vscode.window.showErrorMessage(`Review failed: ${error}`);
    }
}

async function generateCode() {
    const description = await vscode.window.showInputBox({
        prompt: 'Describe the code you want to generate',
        placeHolder: 'e.g., a function to sort a list of objects by date'
    });

    if (!description) return;

    const editor = vscode.window.activeTextEditor;
    const language = editor?.document.languageId || 'python';
    statusBarManager.setLoading('Generating...');

    try {
        const result = await cognifyRunner.generateCode(description, language);
        await showGeneratedCode(result.code, language);
        statusBarManager.setReady();
    } catch (error) {
        statusBarManager.setError();
        vscode.window.showErrorMessage(`Generation failed: ${error}`);
    }
}

async function editCode() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showWarningMessage('No active editor');
        return;
    }

    const instruction = await vscode.window.showInputBox({
        prompt: 'What changes do you want to make?',
        placeHolder: 'e.g., add error handling, optimize performance'
    });

    if (!instruction) return;

    const selection = editor.selection;
    const code = selection.isEmpty 
        ? editor.document.getText() 
        : editor.document.getText(selection);
    const language = editor.document.languageId;
    statusBarManager.setLoading('Editing...');

    try {
        const result = await cognifyRunner.editCode(code, instruction, language);
        await showEditPreview(editor, result.code, selection);
        statusBarManager.setReady();
    } catch (error) {
        statusBarManager.setError();
        vscode.window.showErrorMessage(`Edit failed: ${error}`);
    }
}

async function explainCode() {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.selection.isEmpty) {
        vscode.window.showWarningMessage('No code selected');
        return;
    }

    const code = editor.document.getText(editor.selection);
    const language = editor.document.languageId;
    statusBarManager.setLoading('Explaining...');

    try {
        const explanation = await cognifyRunner.explainCode(code, language);
        showExplanation(explanation);
        statusBarManager.setReady();
    } catch (error) {
        statusBarManager.setError();
        vscode.window.showErrorMessage(`Explanation failed: ${error}`);
    }
}

function openChat(context: vscode.ExtensionContext) {
    if (chatPanel) {
        chatPanel.reveal();
    } else {
        chatPanel = new ChatPanel(context.extensionUri, cognifyRunner);
        chatPanel.onDidDispose(() => { chatPanel = undefined; });
    }
}

async function checkStatus() {
    statusBarManager.setLoading('Checking...');
    try {
        const status = await cognifyRunner.checkStatus();
        statusBarManager.setReady();
        vscode.window.showInformationMessage(
            `Cognify Status: ${status.connected ? '✅ Connected' : '❌ Disconnected'}\n` +
            `Provider: ${status.provider}\nModel: ${status.model}`
        );
    } catch (error) {
        statusBarManager.setError();
        vscode.window.showErrorMessage(`Status check failed: ${error}`);
    }
}

async function checkStatusSilent() {
    try {
        const status = await cognifyRunner.checkStatus();
        if (status.connected) {
            statusBarManager.setReady();
        } else {
            statusBarManager.setError();
        }
    } catch {
        statusBarManager.setError();
    }
}

async function switchProvider() {
    const providers = ['ollama', 'groq', 'google', 'cerebras', 'openrouter', 'openai'];
    const selected = await vscode.window.showQuickPick(providers, {
        placeHolder: 'Select LLM provider'
    });

    if (!selected) return;

    const config = vscode.workspace.getConfiguration('cognify');
    await config.update('provider', selected, vscode.ConfigurationTarget.Global);
    vscode.window.showInformationMessage(`Switched to ${selected} provider`);
}

function showReviewResult(result: { summary: string; issues: any[] }) {
    const panel = vscode.window.createWebviewPanel(
        'cognifyReview',
        'Code Review',
        vscode.ViewColumn.Beside,
        { enableScripts: true }
    );

    const issuesHtml = result.issues.map(issue => `
        <div class="issue ${issue.severity}">
            <span class="severity">${issue.severity.toUpperCase()}</span>
            <span class="line">Line ${issue.line || '?'}</span>
            <p>${issue.message}</p>
            ${issue.suggestion ? `<p class="suggestion">💡 ${issue.suggestion}</p>` : ''}
        </div>
    `).join('');

    panel.webview.html = `<!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: var(--vscode-font-family); padding: 20px; }
            .summary { margin-bottom: 20px; padding: 15px; background: var(--vscode-editor-background); border-radius: 8px; }
            .issue { padding: 10px; margin: 10px 0; border-left: 3px solid; border-radius: 4px; }
            .issue.error { border-color: #f44336; background: rgba(244,67,54,0.1); }
            .issue.warning { border-color: #ff9800; background: rgba(255,152,0,0.1); }
            .issue.info { border-color: #2196f3; background: rgba(33,150,243,0.1); }
            .severity { font-weight: bold; margin-right: 10px; }
            .line { color: var(--vscode-descriptionForeground); }
            .suggestion { color: var(--vscode-textLink-foreground); font-style: italic; }
        </style>
    </head>
    <body>
        <h2>📋 Code Review</h2>
        <div class="summary"><strong>Summary:</strong> ${result.summary}</div>
        <h3>Issues Found (${result.issues.length})</h3>
        ${issuesHtml || '<p>No issues found! ✅</p>'}
    </body>
    </html>`;
}

async function showGeneratedCode(code: string, language: string) {
    const doc = await vscode.workspace.openTextDocument({
        content: code,
        language: language
    });
    await vscode.window.showTextDocument(doc, vscode.ViewColumn.Beside);
}

async function showEditPreview(editor: vscode.TextEditor, newCode: string, selection: vscode.Selection) {
    const action = await vscode.window.showInformationMessage(
        'Apply the suggested changes?',
        'Apply', 'Preview', 'Cancel'
    );

    if (action === 'Apply') {
        const range = selection.isEmpty
            ? new vscode.Range(0, 0, editor.document.lineCount, 0)
            : selection;
        await editor.edit(editBuilder => {
            editBuilder.replace(range, newCode);
        });
    } else if (action === 'Preview') {
        const doc = await vscode.workspace.openTextDocument({
            content: newCode,
            language: editor.document.languageId
        });
        await vscode.window.showTextDocument(doc, vscode.ViewColumn.Beside);
    }
}

function showExplanation(explanation: string) {
    const panel = vscode.window.createWebviewPanel(
        'cognifyExplain',
        'Code Explanation',
        vscode.ViewColumn.Beside,
        {}
    );

    panel.webview.html = `<!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: var(--vscode-font-family); padding: 20px; line-height: 1.6; }
            pre { background: var(--vscode-editor-background); padding: 15px; border-radius: 8px; overflow-x: auto; }
            code { font-family: var(--vscode-editor-font-family); }
        </style>
    </head>
    <body>
        <h2>💡 Code Explanation</h2>
        <div>${explanation.replace(/\n/g, '<br>')}</div>
    </body>
    </html>`;
}

export function deactivate() {
    if (chatPanel) {
        chatPanel.dispose();
    }
}

