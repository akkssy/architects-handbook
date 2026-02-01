import * as vscode from 'vscode';

export class StatusBarManager {
    public statusBarItem: vscode.StatusBarItem;

    constructor() {
        this.statusBarItem = vscode.window.createStatusBarItem(
            vscode.StatusBarAlignment.Right,
            100
        );
        this.statusBarItem.command = 'cognify.checkStatus';
        this.setReady();
        this.statusBarItem.show();
    }

    setReady() {
        this.statusBarItem.text = '$(sparkle) Cognify';
        this.statusBarItem.tooltip = 'Cognify AI - Click to check status';
        this.statusBarItem.backgroundColor = undefined;
    }

    setLoading(message: string = 'Processing...') {
        this.statusBarItem.text = `$(sync~spin) ${message}`;
        this.statusBarItem.tooltip = 'Cognify AI is processing...';
    }

    setError() {
        this.statusBarItem.text = '$(error) Cognify';
        this.statusBarItem.tooltip = 'Cognify AI - Connection error. Click to check status.';
        this.statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
    }

    dispose() {
        this.statusBarItem.dispose();
    }
}

