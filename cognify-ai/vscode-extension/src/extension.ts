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

// Refresh license status periodically
let licenseRefreshInterval: NodeJS.Timeout | undefined;

export function activate(context: vscode.ExtensionContext) {
    console.log('Cognify AI extension is now active!');

    // Initialize components
    cognifyRunner = new CognifyRunner();
    statusBarManager = new StatusBarManager();
    diagnosticsManager = new DiagnosticsManager();

    // Register the sidebar chat view provider
    chatViewProvider = new ChatViewProvider(context.extensionUri, cognifyRunner, context);
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
        // New user management commands
        vscode.commands.registerCommand('cognify.showSettings', () => showSettings()),
        vscode.commands.registerCommand('cognify.showLicenseStatus', () => showLicenseStatus()),
        vscode.commands.registerCommand('cognify.toggleAnalytics', () => toggleAnalytics()),
        vscode.commands.registerCommand('cognify.toggleTelemetry', () => toggleTelemetry()),
        vscode.commands.registerCommand('cognify.showUsageData', () => showUsageData()),
    ];

    commands.forEach(cmd => context.subscriptions.push(cmd));
    context.subscriptions.push(statusBarManager.statusBarItem);

    // Check status on activation
    checkStatusSilent();

    // Refresh license status on activation and periodically
    refreshLicenseStatus();
    licenseRefreshInterval = setInterval(refreshLicenseStatus, 60000); // Every minute

    context.subscriptions.push({
        dispose: () => {
            if (licenseRefreshInterval) {
                clearInterval(licenseRefreshInterval);
            }
        }
    });
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

// ==================== User Management Functions ====================

async function refreshLicenseStatus() {
    try {
        const license = await cognifyRunner.getLicenseStatus();
        statusBarManager.setLicenseInfo({
            tier: license.tier,
            remaining: license.remaining_cloud_calls,
            llmCallsToday: license.usage_today.llm_calls_today
        });
    } catch {
        // Silently fail - status bar will show default
    }
}

async function showSettings() {
    try {
        const settings = await cognifyRunner.getSettings();

        const panel = vscode.window.createWebviewPanel(
            'cognifySettings',
            'Cognify Settings',
            vscode.ViewColumn.One,
            { enableScripts: true }
        );

        panel.webview.html = getSettingsHtml(settings);

        panel.webview.onDidReceiveMessage(async (message) => {
            if (message.command === 'updateSetting') {
                const success = await cognifyRunner.updateSetting(message.key, message.value);
                if (success) {
                    vscode.window.showInformationMessage(`Updated ${message.key}`);
                    // Refresh the panel
                    const newSettings = await cognifyRunner.getSettings();
                    panel.webview.html = getSettingsHtml(newSettings);
                } else {
                    vscode.window.showErrorMessage(`Failed to update ${message.key}`);
                }
            }
        });
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to load settings: ${error}`);
    }
}

function getSettingsHtml(settings: any): string {
    const checkIcon = (enabled: boolean) => enabled ? '✓' : '✗';
    const checkClass = (enabled: boolean) => enabled ? 'enabled' : 'disabled';

    return `<!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: var(--vscode-font-family); padding: 20px; max-width: 600px; margin: 0 auto; }
            h2 { border-bottom: 1px solid var(--vscode-panel-border); padding-bottom: 10px; }
            .section { margin: 20px 0; padding: 15px; background: var(--vscode-editor-background); border-radius: 8px; }
            .section h3 { margin-top: 0; display: flex; align-items: center; gap: 8px; }
            .setting-row { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--vscode-panel-border); }
            .setting-row:last-child { border-bottom: none; }
            .setting-label { flex: 1; }
            .setting-value { display: flex; align-items: center; gap: 8px; }
            .toggle { cursor: pointer; padding: 4px 12px; border-radius: 4px; border: 1px solid var(--vscode-button-border); background: var(--vscode-button-secondaryBackground); }
            .toggle:hover { background: var(--vscode-button-secondaryHoverBackground); }
            .enabled { color: #4caf50; }
            .disabled { color: #f44336; }
            .status-badge { padding: 2px 8px; border-radius: 4px; font-size: 12px; }
            .status-badge.enabled { background: rgba(76, 175, 80, 0.2); }
            .status-badge.disabled { background: rgba(244, 67, 54, 0.2); }
        </style>
    </head>
    <body>
        <h2>⚙️ Cognify AI Settings</h2>

        <div class="section">
            <h3>📊 Analytics</h3>
            <div class="setting-row">
                <span class="setting-label">Enable Analytics</span>
                <div class="setting-value">
                    <span class="status-badge ${checkClass(settings.analytics?.enabled)}">${checkIcon(settings.analytics?.enabled)} ${settings.analytics?.enabled ? 'Enabled' : 'Disabled'}</span>
                    <button class="toggle" onclick="toggleSetting('analytics.enabled', ${!settings.analytics?.enabled})">Toggle</button>
                </div>
            </div>
            <div class="setting-row">
                <span class="setting-label">Local Only</span>
                <div class="setting-value">
                    <span class="status-badge ${checkClass(settings.analytics?.local_only)}">${checkIcon(settings.analytics?.local_only)}</span>
                </div>
            </div>
            <div class="setting-row">
                <span class="setting-label">Retention Days</span>
                <div class="setting-value">${settings.analytics?.retention_days || 90} days</div>
            </div>
        </div>

        <div class="section">
            <h3>📡 Telemetry</h3>
            <div class="setting-row">
                <span class="setting-label">Enable Telemetry</span>
                <div class="setting-value">
                    <span class="status-badge ${checkClass(settings.telemetry?.enabled)}">${checkIcon(settings.telemetry?.enabled)} ${settings.telemetry?.enabled ? 'Enabled' : 'Disabled'}</span>
                    <button class="toggle" onclick="toggleSetting('telemetry.enabled', ${!settings.telemetry?.enabled})">Toggle</button>
                </div>
            </div>
            <div class="setting-row">
                <span class="setting-label">Share Usage Stats</span>
                <div class="setting-value">
                    <span class="status-badge ${checkClass(settings.telemetry?.share_usage_stats)}">${checkIcon(settings.telemetry?.share_usage_stats)}</span>
                </div>
            </div>
            <div class="setting-row">
                <span class="setting-label">Share Error Reports</span>
                <div class="setting-value">
                    <span class="status-badge ${checkClass(settings.telemetry?.share_error_reports)}">${checkIcon(settings.telemetry?.share_error_reports)}</span>
                </div>
            </div>
        </div>

        <div class="section">
            <h3>🔐 Authentication</h3>
            <div class="setting-row">
                <span class="setting-label">Enable Authentication</span>
                <div class="setting-value">
                    <span class="status-badge ${checkClass(settings.authentication?.enabled)}">${checkIcon(settings.authentication?.enabled)} ${settings.authentication?.enabled ? 'Enabled' : 'Disabled'}</span>
                    <button class="toggle" onclick="toggleSetting('authentication.enabled', ${!settings.authentication?.enabled})">Toggle</button>
                </div>
            </div>
        </div>

        <div class="section">
            <h3>📜 License</h3>
            <div class="setting-row">
                <span class="setting-label">Current Tier</span>
                <div class="setting-value">${(settings.licensing?.tier || 'free').toUpperCase()}</div>
            </div>
            <div class="setting-row">
                <span class="setting-label">Offline Mode</span>
                <div class="setting-value">
                    <span class="status-badge ${checkClass(settings.licensing?.offline_mode)}">${checkIcon(settings.licensing?.offline_mode)}</span>
                </div>
            </div>
        </div>

        <script>
            const vscode = acquireVsCodeApi();
            function toggleSetting(key, value) {
                vscode.postMessage({ command: 'updateSetting', key, value });
            }
        </script>
    </body>
    </html>`;
}

async function showLicenseStatus() {
    try {
        const license = await cognifyRunner.getLicenseStatus();

        const panel = vscode.window.createWebviewPanel(
            'cognifyLicense',
            'Cognify License',
            vscode.ViewColumn.One,
            {}
        );

        const remainingText = license.remaining_cloud_calls !== null
            ? `${license.remaining_cloud_calls} / ${license.limits.daily_cloud_llm_calls}`
            : 'Unlimited';

        const limitText = license.limits.daily_cloud_llm_calls === -1
            ? 'Unlimited'
            : license.limits.daily_cloud_llm_calls.toString();

        panel.webview.html = `<!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: var(--vscode-font-family); padding: 20px; max-width: 500px; margin: 0 auto; }
                h2 { text-align: center; }
                .tier-badge { text-align: center; padding: 20px; margin: 20px 0; background: var(--vscode-editor-background); border-radius: 12px; }
                .tier-name { font-size: 24px; font-weight: bold; }
                .tier-free { color: #9e9e9e; }
                .tier-pro { color: #4caf50; }
                .tier-team { color: #2196f3; }
                .tier-enterprise { color: #9c27b0; }
                .stats { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 20px 0; }
                .stat-box { padding: 15px; background: var(--vscode-editor-background); border-radius: 8px; text-align: center; }
                .stat-value { font-size: 24px; font-weight: bold; }
                .stat-label { font-size: 12px; color: var(--vscode-descriptionForeground); }
                .limits { margin: 20px 0; }
                .limit-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--vscode-panel-border); }
                .progress-bar { height: 8px; background: var(--vscode-progressBar-background); border-radius: 4px; margin-top: 10px; }
                .progress-fill { height: 100%; background: var(--vscode-progressBar-foreground); border-radius: 4px; transition: width 0.3s; }
            </style>
        </head>
        <body>
            <h2>📜 License Status</h2>

            <div class="tier-badge">
                <div class="tier-name tier-${license.tier}">${license.tier_display}</div>
                <div>${license.is_paid ? '✅ Paid License' : '🆓 Free Tier'}</div>
            </div>

            <div class="stats">
                <div class="stat-box">
                    <div class="stat-value">${license.usage_today.commands_today}</div>
                    <div class="stat-label">Commands Today</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value">${license.usage_today.llm_calls_today}</div>
                    <div class="stat-label">LLM Calls Today</div>
                </div>
            </div>

            <h3>Cloud LLM Usage</h3>
            <div class="stat-box">
                <div class="stat-value">${remainingText}</div>
                <div class="stat-label">Remaining Today</div>
                ${license.remaining_cloud_calls !== null ? `
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${(license.remaining_cloud_calls / license.limits.daily_cloud_llm_calls) * 100}%"></div>
                </div>
                ` : ''}
            </div>

            <h3>Tier Limits</h3>
            <div class="limits">
                <div class="limit-row">
                    <span>Daily Cloud LLM Calls</span>
                    <span>${limitText}</span>
                </div>
                <div class="limit-row">
                    <span>Daily Local LLM Calls</span>
                    <span>${license.limits.daily_local_llm_calls === -1 ? 'Unlimited' : license.limits.daily_local_llm_calls}</span>
                </div>
                <div class="limit-row">
                    <span>Max Agents</span>
                    <span>${license.limits.max_agents}</span>
                </div>
                <div class="limit-row">
                    <span>History Retention</span>
                    <span>${license.limits.history_retention_days} days</span>
                </div>
            </div>
        </body>
        </html>`;

        // Refresh status bar after viewing
        refreshLicenseStatus();
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to load license status: ${error}`);
    }
}

async function toggleAnalytics() {
    try {
        const settings = await cognifyRunner.getSettings();
        const newValue = !settings.analytics?.enabled;
        const success = await cognifyRunner.toggleAnalytics(newValue);

        if (success) {
            vscode.window.showInformationMessage(`Analytics ${newValue ? 'enabled' : 'disabled'}`);
        } else {
            vscode.window.showErrorMessage('Failed to toggle analytics');
        }
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to toggle analytics: ${error}`);
    }
}

async function toggleTelemetry() {
    try {
        const settings = await cognifyRunner.getSettings();
        const newValue = !settings.telemetry?.enabled;
        const success = await cognifyRunner.toggleTelemetry(newValue);

        if (success) {
            vscode.window.showInformationMessage(`Telemetry ${newValue ? 'enabled' : 'disabled'}`);
        } else {
            vscode.window.showErrorMessage('Failed to toggle telemetry');
        }
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to toggle telemetry: ${error}`);
    }
}

async function showUsageData() {
    try {
        const usage = await cognifyRunner.getUsageData();

        vscode.window.showInformationMessage(
            `📊 Usage Data\n` +
            `Total Events: ${usage.total_events}\n` +
            `Commands Today: ${usage.commands_today}\n` +
            `LLM Calls Today: ${usage.llm_calls_today}`
        );
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to load usage data: ${error}`);
    }
}

export function deactivate() {
    if (chatPanel) {
        chatPanel.dispose();
    }
    if (licenseRefreshInterval) {
        clearInterval(licenseRefreshInterval);
    }
}

