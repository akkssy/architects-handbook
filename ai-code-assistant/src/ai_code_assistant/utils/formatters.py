"""Output formatters for AI Code Assistant."""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from ai_code_assistant.reviewer.analyzer import ReviewResult, ReviewIssue
from ai_code_assistant.generator.code_gen import GenerationResult


class BaseFormatter(ABC):
    """Base class for output formatters."""

    @abstractmethod
    def format_review(self, result: ReviewResult) -> str:
        """Format a review result."""
        pass

    @abstractmethod
    def format_generation(self, result: GenerationResult) -> str:
        """Format a generation result."""
        pass

    def save(self, content: str, output_path: Path) -> None:
        """Save formatted content to file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)


class ConsoleFormatter(BaseFormatter):
    """Formatter for rich console output."""

    def __init__(self, use_colors: bool = True):
        self.console = Console(force_terminal=use_colors, color_system="auto" if use_colors else None)

    def format_review(self, result: ReviewResult) -> str:
        """Format and display review result to console."""
        if result.error:
            self.console.print(Panel(f"[red]Error:[/red] {result.error}", title="Review Failed"))
            return result.error

        # Header
        self.console.print(Panel(
            f"[bold]{result.filename}[/bold]\nLanguage: {result.language} | Quality: {result.overall_quality}",
            title="Code Review",
        ))

        # Summary
        if result.summary:
            self.console.print(f"\n[bold]Summary:[/bold] {result.summary}\n")

        # Issues by severity
        severity_colors = {"critical": "red", "warning": "yellow", "suggestion": "blue"}
        
        for severity in ["critical", "warning", "suggestion"]:
            issues = [i for i in result.issues if i.severity == severity]
            if not issues:
                continue
            
            color = severity_colors.get(severity, "white")
            self.console.print(f"\n[bold {color}]{severity.upper()} ({len(issues)})[/bold {color}]")
            
            for issue in issues:
                self._print_issue(issue, color)

        # Metrics
        if result.metrics:
            self._print_metrics(result.metrics)

        return ""  # Console output is printed directly

    def _print_issue(self, issue: ReviewIssue, color: str) -> None:
        """Print a single issue."""
        lines = f"L{issue.line_start}"
        if issue.line_end != issue.line_start:
            lines += f"-{issue.line_end}"
        
        confidence = f" ({issue.confidence:.0%})" if issue.confidence else ""
        
        self.console.print(f"  [{color}]●[/{color}] [{color}]{issue.title}[/{color}] [{lines}]{confidence}")
        self.console.print(f"    {issue.description}")
        
        if issue.suggestion:
            self.console.print(f"    [green]→ {issue.suggestion}[/green]")

    def _print_metrics(self, metrics: dict) -> None:
        """Print metrics table."""
        table = Table(title="Metrics", show_header=False)
        table.add_column("Metric")
        table.add_column("Value")
        
        for key, value in metrics.items():
            table.add_row(key.replace("_", " ").title(), str(value))
        
        self.console.print(table)

    def format_generation(self, result: GenerationResult) -> str:
        """Format and display generation result to console."""
        if result.error:
            self.console.print(Panel(f"[red]Error:[/red] {result.error}", title="Generation Failed"))
            return result.error

        self.console.print(Panel(
            f"Mode: {result.mode} | Language: {result.language}",
            title="Generated Code",
        ))

        if result.description:
            self.console.print(f"\n[bold]Description:[/bold] {result.description}\n")

        syntax = Syntax(result.code, result.language, theme="monokai", line_numbers=True)
        self.console.print(syntax)

        return result.code


class MarkdownFormatter(BaseFormatter):
    """Formatter for markdown output."""

    def format_review(self, result: ReviewResult) -> str:
        """Format review result as markdown."""
        lines = [f"# Code Review: {result.filename}\n"]
        
        if result.error:
            lines.append(f"**Error:** {result.error}\n")
            return "\n".join(lines)

        lines.append(f"**Language:** {result.language}  ")
        lines.append(f"**Overall Quality:** {result.overall_quality}\n")

        if result.summary:
            lines.append(f"## Summary\n\n{result.summary}\n")

        # Issues
        lines.append("## Issues\n")
        
        for severity in ["critical", "warning", "suggestion"]:
            issues = [i for i in result.issues if i.severity == severity]
            if not issues:
                continue
            
            emoji = {"critical": "🔴", "warning": "🟡", "suggestion": "🔵"}.get(severity, "⚪")
            lines.append(f"### {emoji} {severity.title()} ({len(issues)})\n")
            
            for issue in issues:
                lines.append(self._format_issue_md(issue))

        # Metrics
        if result.metrics:
            lines.append("## Metrics\n")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            for key, value in result.metrics.items():
                lines.append(f"| {key.replace('_', ' ').title()} | {value} |")
            lines.append("")

        return "\n".join(lines)

    def _format_issue_md(self, issue: ReviewIssue) -> str:
        """Format a single issue as markdown."""
        lines = issue.line_start
        if issue.line_end != issue.line_start:
            lines = f"{issue.line_start}-{issue.line_end}"
        
        md = f"#### {issue.title} (Line {lines})\n\n"
        md += f"{issue.description}\n\n"
        
        if issue.suggestion:
            md += f"**Suggestion:** {issue.suggestion}\n\n"
        
        if issue.code_snippet:
            md += f"```\n{issue.code_snippet}\n```\n\n"
        
        if issue.fixed_code:
            md += f"**Fixed code:**\n```\n{issue.fixed_code}\n```\n\n"
        
        if issue.confidence:
            md += f"*Confidence: {issue.confidence:.0%}*\n\n"
        
        return md

    def format_generation(self, result: GenerationResult) -> str:
        """Format generation result as markdown."""
        lines = [f"# Generated Code\n"]
        
        if result.error:
            lines.append(f"**Error:** {result.error}\n")
            return "\n".join(lines)

        lines.append(f"**Mode:** {result.mode}  ")
        lines.append(f"**Language:** {result.language}\n")

        if result.description:
            lines.append(f"## Description\n\n{result.description}\n")

        lines.append(f"## Code\n\n```{result.language}\n{result.code}\n```\n")

        return "\n".join(lines)


class JsonFormatter(BaseFormatter):
    """Formatter for JSON output."""

    def format_review(self, result: ReviewResult) -> str:
        """Format review result as JSON."""
        data = {
            "filename": result.filename,
            "language": result.language,
            "summary": result.summary,
            "overall_quality": result.overall_quality,
            "error": result.error,
            "issues": [
                {
                    "line_start": i.line_start,
                    "line_end": i.line_end,
                    "category": i.category,
                    "severity": i.severity,
                    "title": i.title,
                    "description": i.description,
                    "suggestion": i.suggestion,
                    "confidence": i.confidence,
                }
                for i in result.issues
            ],
            "metrics": result.metrics,
        }
        return json.dumps(data, indent=2)

    def format_generation(self, result: GenerationResult) -> str:
        """Format generation result as JSON."""
        data = {
            "mode": result.mode,
            "language": result.language,
            "description": result.description,
            "code": result.code,
            "error": result.error,
            "success": result.success,
        }
        return json.dumps(data, indent=2)


def get_formatter(format_type: str, use_colors: bool = True) -> BaseFormatter:
    """Get formatter by type."""
    formatters = {
        "console": lambda: ConsoleFormatter(use_colors),
        "markdown": MarkdownFormatter,
        "json": JsonFormatter,
    }
    
    factory = formatters.get(format_type.lower(), formatters["console"])
    return factory()

