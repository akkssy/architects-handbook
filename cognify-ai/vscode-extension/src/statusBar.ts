import * as vscode from 'vscode';

export interface LicenseInfo {
    tier: string;
    remaining: number | null;
    llmCallsToday: number;
}

export class StatusBarManager {
    public statusBarItem: vscode.StatusBarItem;
    private _licenseInfo: LicenseInfo | null = null;

    constructor() {
        this.statusBarItem = vscode.window.createStatusBarItem(
            vscode.StatusBarAlignment.Right,
            100
        );
        this.statusBarItem.command = 'cognify.showLicenseStatus';
        this.setReady();
        this.statusBarItem.show();
    }

    setReady() {
        this._updateDisplay();
    }

    setLoading(message: string = 'Processing...') {
        this.statusBarItem.text = `$(sync~spin) ${message}`;
        this.statusBarItem.tooltip = 'Cognify AI is processing...';
        this.statusBarItem.backgroundColor = undefined;
    }

    setError() {
        this.statusBarItem.text = '$(error) Cognify';
        this.statusBarItem.tooltip = 'Cognify AI - Connection error. Click to check status.';
        this.statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
    }

    /**
     * Update license information displayed in status bar
     */
    setLicenseInfo(info: LicenseInfo) {
        this._licenseInfo = info;
        this._updateDisplay();
    }

    private _updateDisplay() {
        if (this._licenseInfo) {
            const { tier, remaining, llmCallsToday } = this._licenseInfo;
            const tierIcon = tier === 'free' ? '$(sparkle)' : '$(verified)';
            const tierLabel = tier.charAt(0).toUpperCase() + tier.slice(1);

            if (remaining !== null && remaining !== undefined) {
                // Show remaining calls for limited tiers
                const usagePercent = remaining > 0 ? Math.round((remaining / 100) * 100) : 0;
                if (remaining <= 10) {
                    this.statusBarItem.text = `${tierIcon} Cognify: ${remaining} left`;
                    this.statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
                } else {
                    this.statusBarItem.text = `${tierIcon} Cognify: ${remaining} left`;
                    this.statusBarItem.backgroundColor = undefined;
                }
                this.statusBarItem.tooltip = `Cognify AI - ${tierLabel} Tier\n` +
                    `Cloud LLM calls today: ${llmCallsToday}\n` +
                    `Remaining: ${remaining}/100\n` +
                    `Click for details`;
            } else {
                // Unlimited tier
                this.statusBarItem.text = `${tierIcon} Cognify Pro`;
                this.statusBarItem.tooltip = `Cognify AI - ${tierLabel} Tier (Unlimited)\n` +
                    `Cloud LLM calls today: ${llmCallsToday}\n` +
                    `Click for details`;
                this.statusBarItem.backgroundColor = undefined;
            }
        } else {
            this.statusBarItem.text = '$(sparkle) Cognify';
            this.statusBarItem.tooltip = 'Cognify AI - Click for license status';
            this.statusBarItem.backgroundColor = undefined;
        }
    }

    dispose() {
        this.statusBarItem.dispose();
    }
}

