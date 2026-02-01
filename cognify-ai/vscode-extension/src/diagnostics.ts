import * as vscode from 'vscode';
import { ReviewIssue } from './cognifyRunner';

export class DiagnosticsManager {
    private diagnosticCollection: vscode.DiagnosticCollection;

    constructor() {
        this.diagnosticCollection = vscode.languages.createDiagnosticCollection('cognify');
    }

    setDiagnostics(uri: vscode.Uri, issues: ReviewIssue[]) {
        const diagnostics: vscode.Diagnostic[] = issues
            .filter(issue => issue.line !== undefined)
            .map(issue => {
                const line = (issue.line || 1) - 1; // Convert to 0-based
                const range = new vscode.Range(line, 0, line, 1000);
                
                const severity = this.getSeverity(issue.severity);
                const diagnostic = new vscode.Diagnostic(range, issue.message, severity);
                diagnostic.source = 'Cognify AI';
                
                if (issue.suggestion) {
                    diagnostic.message += `\n💡 Suggestion: ${issue.suggestion}`;
                }

                return diagnostic;
            });

        this.diagnosticCollection.set(uri, diagnostics);
    }

    private getSeverity(severity: string): vscode.DiagnosticSeverity {
        switch (severity.toLowerCase()) {
            case 'error':
                return vscode.DiagnosticSeverity.Error;
            case 'warning':
                return vscode.DiagnosticSeverity.Warning;
            case 'info':
            default:
                return vscode.DiagnosticSeverity.Information;
        }
    }

    clear(uri?: vscode.Uri) {
        if (uri) {
            this.diagnosticCollection.delete(uri);
        } else {
            this.diagnosticCollection.clear();
        }
    }

    dispose() {
        this.diagnosticCollection.dispose();
    }
}

