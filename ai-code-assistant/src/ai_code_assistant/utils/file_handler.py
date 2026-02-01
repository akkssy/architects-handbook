"""File handling utilities for AI Code Assistant."""

import fnmatch
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from ai_code_assistant.config import Config, get_language_by_extension


class FileHandler:
    """Handles file system operations for code files."""

    # Common patterns to ignore
    DEFAULT_IGNORE_PATTERNS = [
        "*.pyc", "__pycache__", ".git", ".venv", "venv",
        "node_modules", ".idea", ".vscode", "*.egg-info",
        "dist", "build", ".pytest_cache", ".mypy_cache",
        "*.min.js", "*.min.css", "*.map", ".env",
    ]

    def __init__(self, config: Config):
        self.config = config
        self.ignore_patterns = self.DEFAULT_IGNORE_PATTERNS.copy()

    def add_ignore_pattern(self, pattern: str) -> None:
        """Add a pattern to ignore list."""
        self.ignore_patterns.append(pattern)

    def is_supported_file(self, file_path: Path) -> bool:
        """Check if file is a supported code file."""
        return get_language_by_extension(self.config, file_path) is not None

    def should_ignore(self, path: Path) -> bool:
        """Check if path should be ignored."""
        path_str = str(path)
        name = path.name
        
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(path_str, f"*/{pattern}/*"):
                return True
        return False

    def find_code_files(
        self,
        directory: Path,
        recursive: bool = True,
        extensions: Optional[List[str]] = None,
    ) -> Iterator[Path]:
        """Find all code files in a directory."""
        if not directory.is_dir():
            return

        pattern = "**/*" if recursive else "*"
        
        for file_path in directory.glob(pattern):
            if not file_path.is_file():
                continue
            
            if self.should_ignore(file_path):
                continue
            
            if extensions:
                if file_path.suffix.lower() not in extensions:
                    continue
            elif not self.is_supported_file(file_path):
                continue
            
            yield file_path

    def read_file(self, file_path: Path) -> Tuple[str, Optional[str]]:
        """Read file content. Returns (content, error)."""
        try:
            if not file_path.exists():
                return "", f"File not found: {file_path}"
            
            if not file_path.is_file():
                return "", f"Not a file: {file_path}"
            
            # Check file size
            file_size_kb = file_path.stat().st_size / 1024
            max_size = self.config.review.max_file_size_kb
            if file_size_kb > max_size:
                return "", f"File too large: {file_size_kb:.1f}KB (max: {max_size}KB)"
            
            content = file_path.read_text(encoding="utf-8")
            return content, None
            
        except UnicodeDecodeError:
            return "", f"Cannot read file (binary or encoding issue): {file_path}"
        except Exception as e:
            return "", f"Error reading file: {e}"

    def write_file(
        self,
        file_path: Path,
        content: str,
        create_dirs: bool = True,
        backup: bool = False,
    ) -> Optional[str]:
        """Write content to file. Returns error message or None on success."""
        try:
            if create_dirs:
                file_path.parent.mkdir(parents=True, exist_ok=True)
            
            if backup and file_path.exists():
                backup_path = file_path.with_suffix(file_path.suffix + ".bak")
                backup_path.write_text(file_path.read_text())
            
            file_path.write_text(content, encoding="utf-8")
            return None
            
        except Exception as e:
            return f"Error writing file: {e}"

    def get_file_info(self, file_path: Path) -> dict:
        """Get information about a file."""
        if not file_path.exists():
            return {"exists": False}
        
        stat = file_path.stat()
        return {
            "exists": True,
            "size_bytes": stat.st_size,
            "size_kb": stat.st_size / 1024,
            "language": get_language_by_extension(self.config, file_path),
            "extension": file_path.suffix,
            "name": file_path.name,
            "path": str(file_path.absolute()),
        }

    def batch_read(
        self,
        file_paths: List[Path],
    ) -> Dict[Path, Tuple[str, Optional[str]]]:
        """Read multiple files. Returns dict of path -> (content, error)."""
        results = {}
        for path in file_paths:
            results[path] = self.read_file(path)
        return results

    def get_output_path(
        self,
        original_path: Path,
        suffix: str = "",
        output_dir: Optional[Path] = None,
    ) -> Path:
        """Generate output path for a file."""
        if output_dir is None:
            output_dir = Path(self.config.output.output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        new_name = original_path.stem + suffix + original_path.suffix
        return output_dir / new_name

