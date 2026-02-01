"""
Code chunking strategies for semantic indexing.

Chunks code into meaningful segments for better retrieval.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path


@dataclass
class CodeChunk:
    """Represents a chunk of code with metadata."""
    content: str
    file_path: str
    start_line: int
    end_line: int
    chunk_type: str  # function, class, module, block
    name: Optional[str] = None
    language: Optional[str] = None
    
    @property
    def id(self) -> str:
        """Generate unique ID for this chunk."""
        return f"{self.file_path}:{self.start_line}-{self.end_line}"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "content": self.content,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "chunk_type": self.chunk_type,
            "name": self.name or "",
            "language": self.language or "",
        }


@dataclass
class CodeChunker:
    """Splits code files into semantic chunks."""
    
    chunk_size: int = 50  # Max lines per chunk
    chunk_overlap: int = 10  # Overlap between chunks
    
    # Language detection by extension
    LANGUAGE_MAP: dict = field(default_factory=lambda: {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".php": "php",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".sh": "bash",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".md": "markdown",
        ".sql": "sql",
    })
    
    # Patterns for detecting code boundaries
    PYTHON_PATTERNS = {
        "class": r"^class\s+(\w+)",
        "function": r"^(?:async\s+)?def\s+(\w+)",
    }
    
    def detect_language(self, file_path: str) -> Optional[str]:
        """Detect programming language from file extension."""
        ext = Path(file_path).suffix.lower()
        return self.LANGUAGE_MAP.get(ext)
    
    def chunk_file(self, file_path: str, content: str) -> List[CodeChunk]:
        """Split a file into semantic chunks."""
        language = self.detect_language(file_path)
        lines = content.split("\n")
        
        if language == "python":
            return self._chunk_python(file_path, lines, language)
        else:
            return self._chunk_generic(file_path, lines, language)
    
    def _chunk_python(self, file_path: str, lines: List[str], language: str) -> List[CodeChunk]:
        """Chunk Python code by class/function boundaries."""
        chunks = []
        current_chunk_start = 0
        current_chunk_lines = []
        current_name = None
        current_type = "module"
        
        for i, line in enumerate(lines):
            # Check for class definition
            class_match = re.match(self.PYTHON_PATTERNS["class"], line)
            func_match = re.match(self.PYTHON_PATTERNS["function"], line)
            
            if class_match or func_match:
                # Save previous chunk if exists
                if current_chunk_lines:
                    chunks.append(CodeChunk(
                        content="\n".join(current_chunk_lines),
                        file_path=file_path,
                        start_line=current_chunk_start + 1,
                        end_line=i,
                        chunk_type=current_type,
                        name=current_name,
                        language=language,
                    ))
                
                # Start new chunk
                current_chunk_start = i
                current_chunk_lines = [line]
                if class_match:
                    current_name = class_match.group(1)
                    current_type = "class"
                else:
                    current_name = func_match.group(1)
                    current_type = "function"
            else:
                current_chunk_lines.append(line)
                
                # Check if chunk is too large
                if len(current_chunk_lines) >= self.chunk_size:
                    chunks.append(CodeChunk(
                        content="\n".join(current_chunk_lines),
                        file_path=file_path,
                        start_line=current_chunk_start + 1,
                        end_line=i + 1,
                        chunk_type=current_type,
                        name=current_name,
                        language=language,
                    ))
                    # Start new chunk with overlap
                    overlap_start = max(0, len(current_chunk_lines) - self.chunk_overlap)
                    current_chunk_lines = current_chunk_lines[overlap_start:]
                    current_chunk_start = i - len(current_chunk_lines) + 1
        
        # Add final chunk
        if current_chunk_lines:
            chunks.append(CodeChunk(
                content="\n".join(current_chunk_lines),
                file_path=file_path,
                start_line=current_chunk_start + 1,
                end_line=len(lines),
                chunk_type=current_type,
                name=current_name,
                language=language,
            ))
        
        return chunks

    def _chunk_generic(self, file_path: str, lines: List[str], language: Optional[str]) -> List[CodeChunk]:
        """Chunk code using sliding window approach."""
        chunks = []
        total_lines = len(lines)

        if total_lines == 0:
            return chunks

        # If file is small enough, return as single chunk
        if total_lines <= self.chunk_size:
            chunks.append(CodeChunk(
                content="\n".join(lines),
                file_path=file_path,
                start_line=1,
                end_line=total_lines,
                chunk_type="module",
                name=Path(file_path).stem,
                language=language,
            ))
            return chunks

        # Use sliding window
        start = 0
        while start < total_lines:
            end = min(start + self.chunk_size, total_lines)
            chunk_lines = lines[start:end]

            chunks.append(CodeChunk(
                content="\n".join(chunk_lines),
                file_path=file_path,
                start_line=start + 1,
                end_line=end,
                chunk_type="block",
                name=f"{Path(file_path).stem}:{start+1}-{end}",
                language=language,
            ))

            # Move window with overlap
            start += self.chunk_size - self.chunk_overlap

            # Avoid tiny final chunks
            if total_lines - start < self.chunk_overlap:
                break

        return chunks

    def chunk_text(self, text: str, file_path: str = "unknown") -> List[CodeChunk]:
        """Convenience method to chunk text directly."""
        return self.chunk_file(file_path, text)

