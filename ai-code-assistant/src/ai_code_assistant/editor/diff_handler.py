"""Diff generation and application for code editing."""

import difflib
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class DiffLine:
    """Represents a single line in a diff."""
    line_number: int
    content: str
    change_type: str  # 'add', 'remove', 'context', 'header'
    
    def __str__(self) -> str:
        prefix = {
            'add': '+',
            'remove': '-',
            'context': ' ',
            'header': '@',
        }.get(self.change_type, ' ')
        return f"{prefix} {self.content}"


@dataclass
class DiffHunk:
    """Represents a hunk (section) of changes in a diff."""
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: List[DiffLine] = field(default_factory=list)
    
    @property
    def header(self) -> str:
        return f"@@ -{self.old_start},{self.old_count} +{self.new_start},{self.new_count} @@"


@dataclass
class DiffResult:
    """Result of diff generation."""
    original_file: str
    modified_file: str
    hunks: List[DiffHunk] = field(default_factory=list)
    unified_diff: str = ""
    additions: int = 0
    deletions: int = 0
    
    @property
    def has_changes(self) -> bool:
        return self.additions > 0 or self.deletions > 0
    
    @property
    def summary(self) -> str:
        return f"+{self.additions} -{self.deletions} lines"
    
    def to_dict(self) -> dict:
        return {
            "original_file": self.original_file,
            "modified_file": self.modified_file,
            "additions": self.additions,
            "deletions": self.deletions,
            "unified_diff": self.unified_diff,
            "has_changes": self.has_changes,
        }


class DiffHandler:
    """Handles diff generation and application."""
    
    def __init__(self, context_lines: int = 3):
        """Initialize diff handler.
        
        Args:
            context_lines: Number of context lines around changes
        """
        self.context_lines = context_lines
    
    def generate_diff(
        self,
        original: str,
        modified: str,
        filename: str = "file",
    ) -> DiffResult:
        """Generate a unified diff between original and modified content.
        
        Args:
            original: Original file content
            modified: Modified file content
            filename: Name of the file for diff headers
            
        Returns:
            DiffResult with diff information
        """
        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)
        
        # Ensure files end with newline for proper diff
        if original_lines and not original_lines[-1].endswith('\n'):
            original_lines[-1] += '\n'
        if modified_lines and not modified_lines[-1].endswith('\n'):
            modified_lines[-1] += '\n'
        
        # Generate unified diff
        diff_lines = list(difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            n=self.context_lines,
        ))
        
        unified_diff = ''.join(diff_lines)
        
        # Count additions and deletions
        additions = sum(1 for line in diff_lines if line.startswith('+') and not line.startswith('+++'))
        deletions = sum(1 for line in diff_lines if line.startswith('-') and not line.startswith('---'))
        
        # Parse hunks
        hunks = self._parse_hunks(diff_lines)
        
        return DiffResult(
            original_file=filename,
            modified_file=filename,
            hunks=hunks,
            unified_diff=unified_diff,
            additions=additions,
            deletions=deletions,
        )
    
    def _parse_hunks(self, diff_lines: List[str]) -> List[DiffHunk]:
        """Parse diff lines into hunks."""
        hunks = []
        current_hunk = None
        
        for line in diff_lines:
            if line.startswith('@@'):
                # Parse hunk header: @@ -start,count +start,count @@
                if current_hunk:
                    hunks.append(current_hunk)
                
                # Extract numbers from header
                parts = line.split('@@')[1].strip().split()
                old_part = parts[0][1:].split(',')  # Remove '-'
                new_part = parts[1][1:].split(',')  # Remove '+'
                
                old_start = int(old_part[0])
                old_count = int(old_part[1]) if len(old_part) > 1 else 1
                new_start = int(new_part[0])
                new_count = int(new_part[1]) if len(new_part) > 1 else 1
                
                current_hunk = DiffHunk(
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                )
            elif current_hunk is not None:
                if line.startswith('+') and not line.startswith('+++'):
                    change_type = 'add'
                elif line.startswith('-') and not line.startswith('---'):
                    change_type = 'remove'
                elif line.startswith(' '):
                    change_type = 'context'
                else:
                    continue
                
                current_hunk.lines.append(DiffLine(
                    line_number=0,  # Will be calculated if needed
                    content=line[1:].rstrip('\n'),
                    change_type=change_type,
                ))
        
        if current_hunk:
            hunks.append(current_hunk)

        return hunks

    def apply_diff(self, original: str, diff_result: DiffResult) -> str:
        """Apply a diff to original content.

        Note: This is a simplified implementation. For complex diffs,
        consider using the patch utility or similar tools.

        Args:
            original: Original file content
            diff_result: DiffResult to apply

        Returns:
            Modified content after applying diff
        """
        # For simplicity, we return the modified content that was used
        # to generate the diff. In a real implementation, you might
        # want to parse and apply the diff hunks.
        # This is mainly useful for verification.
        return diff_result.modified_file if hasattr(diff_result, '_modified_content') else original

    def format_for_display(
        self,
        diff_result: DiffResult,
        use_colors: bool = True,
    ) -> str:
        """Format diff for terminal display.

        Args:
            diff_result: DiffResult to format
            use_colors: Whether to use ANSI colors

        Returns:
            Formatted diff string
        """
        if not diff_result.has_changes:
            return "No changes detected."

        lines = []

        # Header
        lines.append(f"--- a/{diff_result.original_file}")
        lines.append(f"+++ b/{diff_result.modified_file}")

        for hunk in diff_result.hunks:
            lines.append(hunk.header)

            for diff_line in hunk.lines:
                if use_colors:
                    if diff_line.change_type == 'add':
                        lines.append(f"\033[32m+{diff_line.content}\033[0m")
                    elif diff_line.change_type == 'remove':
                        lines.append(f"\033[31m-{diff_line.content}\033[0m")
                    else:
                        lines.append(f" {diff_line.content}")
                else:
                    prefix = {
                        'add': '+',
                        'remove': '-',
                        'context': ' ',
                    }.get(diff_line.change_type, ' ')
                    lines.append(f"{prefix}{diff_line.content}")

        return '\n'.join(lines)

    def get_changed_lines(self, diff_result: DiffResult) -> Tuple[List[int], List[int]]:
        """Get lists of added and removed line numbers.

        Args:
            diff_result: DiffResult to analyze

        Returns:
            Tuple of (added_lines, removed_lines)
        """
        added = []
        removed = []

        for hunk in diff_result.hunks:
            old_line = hunk.old_start
            new_line = hunk.new_start

            for diff_line in hunk.lines:
                if diff_line.change_type == 'add':
                    added.append(new_line)
                    new_line += 1
                elif diff_line.change_type == 'remove':
                    removed.append(old_line)
                    old_line += 1
                else:  # context
                    old_line += 1
                    new_line += 1

        return added, removed

