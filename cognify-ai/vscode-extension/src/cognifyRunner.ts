import * as vscode from 'vscode';
import { spawn, exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export interface ReviewResult {
    summary: string;
    issues: ReviewIssue[];
}

export interface ReviewIssue {
    severity: 'error' | 'warning' | 'info';
    message: string;
    line?: number;
    suggestion?: string;
}

export interface GenerateResult {
    code: string;
    explanation?: string;
}

export interface StatusResult {
    connected: boolean;
    provider: string;
    model: string;
}

export interface IndexStatus {
    indexed: boolean;
    chunkCount: number;
    fileCount?: number;
    indexPath?: string;
    error?: string;
}

export interface IndexProgress {
    current: number;
    total: number;
    currentFile?: string;
}

export interface IndexResult {
    success: boolean;
    filesIndexed: number;
    chunksCreated: number;
    errors: string[];
}

export interface ChatMessage {
    role: 'user' | 'assistant';
    content: string;
}

export interface SmartChatOptions {
    context?: string;
    language?: string;
    history?: ChatMessage[];
    searchContext?: string;  // Semantic search context from index
}

export interface SmartChatResult {
    response: string;
    intent: 'generate' | 'review' | 'edit' | 'explain' | 'chat';
    hasCode: boolean;
}

export interface SearchResult {
    content: string;
    file_path: string;
    start_line: number;
    end_line: number;
    chunk_type: string;
    name: string;
    language: string;
    score: number;
}

export interface SearchResponse {
    query: string;
    total_results: number;
    results: SearchResult[];
    formatted_context?: string;  // Pre-formatted for LLM
}

export interface KnowledgeEntry {
    id: string;
    title: string;
    content: string;
    tags: string[];
    created_at: string;
    updated_at: string;
    file_path: string;
}

export interface KnowledgeSearchResult {
    entries: KnowledgeEntry[];
    query: string;
}

export class CognifyRunner {
    private getConfig() {
        const config = vscode.workspace.getConfiguration('cognify');
        return {
            provider: config.get<string>('provider', 'ollama'),
            model: config.get<string>('model', 'deepseek-coder:6.7b'),
            autoContext: config.get<boolean>('autoContext', true),
            maxContextTokens: config.get<number>('maxContextTokens', 8000)
        };
    }

    private async runCommand(args: string[]): Promise<string> {
        const config = this.getConfig();
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || process.cwd();
        
        return new Promise((resolve, reject) => {
            const proc = spawn('cognify', args, {
                cwd: workspaceFolder,
                env: { ...process.env }
            });

            let stdout = '';
            let stderr = '';

            proc.stdout.on('data', (data) => { stdout += data.toString(); });
            proc.stderr.on('data', (data) => { stderr += data.toString(); });

            proc.on('close', (code) => {
                if (code === 0) {
                    resolve(stdout);
                } else {
                    reject(new Error(stderr || `Command failed with code ${code}`));
                }
            });

            proc.on('error', (err) => {
                reject(new Error(`Failed to run cognify: ${err.message}. Is cognify installed?`));
            });
        });
    }

    async reviewFile(filePath: string): Promise<ReviewResult> {
        const config = this.getConfig();
        const args = ['agent-review', filePath, '--format', 'json'];
        
        if (config.autoContext) {
            args.push('--auto-context');
            args.push('--max-context-tokens', config.maxContextTokens.toString());
        }

        try {
            const output = await this.runCommand(args);
            return this.parseReviewOutput(output);
        } catch (error) {
            // Fallback to basic review
            const basicArgs = ['review', filePath, '--format', 'json'];
            const output = await this.runCommand(basicArgs);
            return this.parseReviewOutput(output);
        }
    }

    async reviewCode(code: string, language: string): Promise<ReviewResult> {
        // Write code to temp file and review
        const fs = require('fs');
        const os = require('os');
        const path = require('path');
        
        const ext = this.getExtension(language);
        const tempFile = path.join(os.tmpdir(), `cognify_review_${Date.now()}${ext}`);
        
        try {
            fs.writeFileSync(tempFile, code);
            const result = await this.reviewFile(tempFile);
            fs.unlinkSync(tempFile);
            return result;
        } catch (error) {
            try { fs.unlinkSync(tempFile); } catch {}
            throw error;
        }
    }

    async generateCode(description: string, language: string): Promise<GenerateResult> {
        const args = ['agent-generate', description, '--language', language];
        const output = await this.runCommand(args);
        return { code: this.extractCode(output), explanation: output };
    }

    async editCode(code: string, instruction: string, language: string): Promise<GenerateResult> {
        const fs = require('fs');
        const os = require('os');
        const path = require('path');
        
        const ext = this.getExtension(language);
        const tempFile = path.join(os.tmpdir(), `cognify_edit_${Date.now()}${ext}`);
        
        try {
            fs.writeFileSync(tempFile, code);
            const args = ['edit', tempFile, instruction, '--preview'];
            const output = await this.runCommand(args);
            const newCode = fs.readFileSync(tempFile, 'utf-8');
            fs.unlinkSync(tempFile);
            return { code: newCode, explanation: output };
        } catch (error) {
            try { fs.unlinkSync(tempFile); } catch {}
            throw error;
        }
    }

    async explainCode(code: string, language: string): Promise<string> {
        const args = ['agent-explain', '--code', code];
        return await this.runCommand(args);
    }

    async checkStatus(): Promise<StatusResult> {
        try {
            const output = await this.runCommand(['status']);
            const config = this.getConfig();
            return {
                connected: output.toLowerCase().includes('connected') || output.toLowerCase().includes('ok'),
                provider: config.provider,
                model: config.model
            };
        } catch {
            const config = this.getConfig();
            return { connected: false, provider: config.provider, model: config.model };
        }
    }

    async chat(message: string, context?: string, history?: ChatMessage[]): Promise<string> {
        const args = ['smart-chat', message];
        if (context) {
            args.push('--context', context);
        }
        if (history && history.length > 0) {
            args.push('--history', JSON.stringify(history));
        }
        return await this.runCommand(args);
    }

    async smartChat(message: string, options: SmartChatOptions = {}): Promise<SmartChatResult> {
        const args = ['smart-chat', message];

        // Combine user context with search context
        let combinedContext = '';

        if (options.searchContext) {
            combinedContext += `\n=== Relevant Code from Codebase ===\n${options.searchContext}\n`;
        }

        if (options.context) {
            combinedContext += `\n=== User Provided Context ===\n${options.context}\n`;
        }

        if (combinedContext) {
            args.push('--context', combinedContext);
        }
        if (options.language) {
            args.push('--language', options.language);
        }
        if (options.history && options.history.length > 0) {
            args.push('--history', JSON.stringify(options.history));
        }

        const output = await this.runCommand(args);

        // Detect what action was taken based on response patterns
        const intent = this.detectResponseIntent(output);

        return {
            response: output,
            intent,
            hasCode: output.includes('```')
        };
    }

    private detectResponseIntent(response: string): 'generate' | 'review' | 'edit' | 'explain' | 'chat' {
        const lower = response.toLowerCase();
        if (lower.includes("here's the generated code") || lower.includes("here is the generated")) {
            return 'generate';
        }
        if (lower.includes("code review summary") || lower.includes("issues found")) {
            return 'review';
        }
        if (lower.includes("here's the modified code") || lower.includes("here is the modified")) {
            return 'edit';
        }
        if (lower.includes("this code") && (lower.includes("does") || lower.includes("works"))) {
            return 'explain';
        }
        return 'chat';
    }

    private parseReviewOutput(output: string): ReviewResult {
        try {
            // Try to parse as JSON first
            const json = JSON.parse(output);
            return {
                summary: json.summary || 'Review complete',
                issues: (json.issues || []).map((issue: any) => ({
                    severity: issue.severity || 'info',
                    message: issue.message || issue.description || '',
                    line: issue.line || issue.line_number,
                    suggestion: issue.suggestion || issue.fix
                }))
            };
        } catch {
            // Parse text output
            return this.parseTextReview(output);
        }
    }

    private parseTextReview(output: string): ReviewResult {
        const issues: ReviewIssue[] = [];
        const lines = output.split('\n');

        let summary = 'Review complete';

        for (const line of lines) {
            if (line.toLowerCase().includes('summary:')) {
                summary = line.replace(/summary:/i, '').trim();
            }

            // Match patterns like [ERROR], [WARNING], [INFO]
            const match = line.match(/\[(ERROR|WARNING|INFO)\]\s*(?:Line\s*(\d+):?)?\s*(.*)/i);
            if (match) {
                issues.push({
                    severity: match[1].toLowerCase() as 'error' | 'warning' | 'info',
                    line: match[2] ? parseInt(match[2]) : undefined,
                    message: match[3]
                });
            }
        }

        return { summary, issues };
    }

    private extractCode(output: string): string {
        // Extract code from markdown code blocks
        const codeBlockMatch = output.match(/```[\w]*\n([\s\S]*?)```/);
        if (codeBlockMatch) {
            return codeBlockMatch[1].trim();
        }

        // If no code block, return the output as-is
        return output.trim();
    }

    private getExtension(language: string): string {
        const extensions: Record<string, string> = {
            'python': '.py',
            'javascript': '.js',
            'typescript': '.ts',
            'java': '.java',
            'cpp': '.cpp',
            'c': '.c',
            'go': '.go',
            'rust': '.rs',
            'ruby': '.rb',
            'php': '.php',
            'swift': '.swift',
            'kotlin': '.kt',
            'scala': '.scala',
            'csharp': '.cs'
        };
        return extensions[language] || '.txt';
    }

    // ==================== Indexing Methods ====================

    /**
     * Check if the workspace has an existing index and get its status
     */
    async checkIndexStatus(workspacePath?: string): Promise<IndexStatus> {
        const path = workspacePath || vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;

        if (!path) {
            return {
                indexed: false,
                chunkCount: 0,
                error: 'No workspace folder open'
            };
        }

        try {
            // Run cognify status and parse the index info
            const output = await this.runCommand(['status']);

            // Parse the output to find index information
            const indexMatch = output.match(/Index found with (\d+) chunks/i);
            if (indexMatch) {
                return {
                    indexed: true,
                    chunkCount: parseInt(indexMatch[1], 10),
                    indexPath: path
                };
            }

            // Check for "No index found" message
            if (output.toLowerCase().includes('no index found')) {
                return {
                    indexed: false,
                    chunkCount: 0,
                    indexPath: path
                };
            }

            // Default: assume no index
            return {
                indexed: false,
                chunkCount: 0,
                indexPath: path
            };
        } catch (error) {
            return {
                indexed: false,
                chunkCount: 0,
                error: error instanceof Error ? error.message : 'Failed to check index status'
            };
        }
    }

    /**
     * Index a workspace/folder with progress callback
     */
    async indexWorkspace(
        workspacePath: string,
        options: { clear?: boolean; onProgress?: (progress: IndexProgress) => void } = {}
    ): Promise<IndexResult> {
        const args = ['index', workspacePath];

        if (options.clear) {
            args.push('--clear');
        }

        return new Promise((resolve, reject) => {
            const proc = spawn('cognify', args, {
                cwd: workspacePath,
                env: { ...process.env }
            });

            let stdout = '';
            let stderr = '';
            let filesIndexed = 0;
            let totalFiles = 0;
            let chunksCreated = 0;
            const errors: string[] = [];

            proc.stdout.on('data', (data) => {
                const text = data.toString();
                stdout += text;

                // Parse progress updates
                // Match "Found X files to index..."
                const foundMatch = text.match(/Found (\d+) files to index/i);
                if (foundMatch) {
                    totalFiles = parseInt(foundMatch[1], 10);
                    options.onProgress?.({ current: 0, total: totalFiles });
                }

                // Match "Indexed X/Y files..."
                const progressMatch = text.match(/Indexed (\d+)\/(\d+) files/i);
                if (progressMatch) {
                    filesIndexed = parseInt(progressMatch[1], 10);
                    totalFiles = parseInt(progressMatch[2], 10);
                    options.onProgress?.({ current: filesIndexed, total: totalFiles });
                }

                // Match final "Indexed X files (Y chunks)"
                const finalMatch = text.match(/Indexed (\d+) files \((\d+) chunks\)/i);
                if (finalMatch) {
                    filesIndexed = parseInt(finalMatch[1], 10);
                    chunksCreated = parseInt(finalMatch[2], 10);
                }
            });

            proc.stderr.on('data', (data) => {
                stderr += data.toString();
            });

            proc.on('close', (code) => {
                if (code === 0) {
                    resolve({
                        success: true,
                        filesIndexed,
                        chunksCreated,
                        errors
                    });
                } else {
                    resolve({
                        success: false,
                        filesIndexed,
                        chunksCreated,
                        errors: [stderr || `Indexing failed with code ${code}`]
                    });
                }
            });

            proc.on('error', (err) => {
                resolve({
                    success: false,
                    filesIndexed: 0,
                    chunksCreated: 0,
                    errors: [`Failed to run cognify: ${err.message}`]
                });
            });
        });
    }

    /**
     * Search the indexed codebase
     */
    async searchCodebase(query: string, options: { topK?: number; language?: string } = {}): Promise<string> {
        const args = ['search', query];

        if (options.topK) {
            args.push('-k', options.topK.toString());
        }
        if (options.language) {
            args.push('--language', options.language);
        }
        args.push('--format', 'context');

        return await this.runCommand(args);
    }

    // ==================== Knowledge Base Methods ====================

    /**
     * Search the knowledge base for relevant entries
     */
    async searchKnowledge(query: string, options: { limit?: number } = {}): Promise<string> {
        const args = ['knowledge', 'search', query, '--format', 'context'];

        if (options.limit) {
            args.push('--limit', options.limit.toString());
        }

        return await this.runCommand(args);
    }

    /**
     * Save a new knowledge entry
     */
    async saveKnowledge(title: string, content: string, options: {
        tags?: string[];
        category?: string;
        source?: string;
    } = {}): Promise<KnowledgeEntry> {
        const args = ['knowledge', 'save', title, '--content', content, '--format', 'json'];

        if (options.category) {
            args.push('--category', options.category);
        }
        if (options.source) {
            args.push('--source', options.source);
        }
        if (options.tags && options.tags.length > 0) {
            for (const tag of options.tags) {
                args.push('--tags', tag);
            }
        }

        const output = await this.runCommand(args);
        return JSON.parse(output);
    }

    /**
     * Get knowledge base statistics
     */
    async getKnowledgeStats(): Promise<{ total_entries: number; categories: Record<string, number>; tags: Record<string, number> }> {
        const output = await this.runCommand(['knowledge', 'stats', '--format', 'json']);
        return JSON.parse(output);
    }

    /**
     * List all knowledge entries
     */
    async listKnowledge(category?: string): Promise<KnowledgeEntry[]> {
        const args = ['knowledge', 'list', '--format', 'json'];
        if (category) {
            args.push('--category', category);
        }
        const output = await this.runCommand(args);
        return JSON.parse(output);
    }
}

