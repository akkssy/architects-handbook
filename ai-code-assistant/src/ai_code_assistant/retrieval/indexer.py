"""
Codebase indexer using ChromaDB and sentence-transformers.

Indexes code files for semantic search.
"""

import os
import hashlib
from pathlib import Path
from typing import List, Optional, Set
from dataclasses import dataclass, field

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from .chunker import CodeChunker, CodeChunk


@dataclass
class IndexStats:
    """Statistics about the index."""
    total_files: int = 0
    total_chunks: int = 0
    indexed_files: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass  
class IndexConfig:
    """Configuration for the indexer."""
    # Embedding model (runs locally)
    embedding_model: str = "all-MiniLM-L6-v2"
    # ChromaDB persistence directory
    persist_directory: str = ".ai-assistant-index"
    # Collection name
    collection_name: str = "codebase"
    # File extensions to index
    extensions: Set[str] = field(default_factory=lambda: {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs",
        ".rb", ".php", ".c", ".cpp", ".h", ".hpp", ".cs", ".swift",
        ".kt", ".scala", ".sh", ".yaml", ".yml", ".json", ".md", ".sql",
        ".html", ".css", ".scss", ".vue", ".svelte",
    })
    # Directories to ignore
    ignore_dirs: Set[str] = field(default_factory=lambda: {
        ".git", ".svn", ".hg", "node_modules", "__pycache__", ".pytest_cache",
        ".mypy_cache", ".tox", ".venv", "venv", "env", ".env", "dist", "build",
        "target", ".idea", ".vscode", "coverage", ".coverage", "htmlcov",
        ".eggs", "*.egg-info", ".ai-assistant-index",
    })
    # Max file size in bytes (skip large files)
    max_file_size: int = 1024 * 1024  # 1MB


class CodebaseIndexer:
    """Indexes codebase into ChromaDB for semantic search."""
    
    def __init__(self, config: Optional[IndexConfig] = None, root_path: Optional[str] = None):
        """Initialize the indexer.
        
        Args:
            config: Index configuration
            root_path: Root directory of the codebase
        """
        self.config = config or IndexConfig()
        self.root_path = Path(root_path) if root_path else Path.cwd()
        self.chunker = CodeChunker()
        
        # Initialize embedding model (lazy load)
        self._embedder: Optional[SentenceTransformer] = None
        
        # Initialize ChromaDB
        persist_path = self.root_path / self.config.persist_directory
        self._client = chromadb.PersistentClient(
            path=str(persist_path),
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.config.collection_name,
            metadata={"description": "Codebase index for semantic search"},
        )
    
    @property
    def embedder(self) -> SentenceTransformer:
        """Lazy load the embedding model."""
        if self._embedder is None:
            self._embedder = SentenceTransformer(self.config.embedding_model)
        return self._embedder
    
    def _should_index_file(self, file_path: Path) -> bool:
        """Check if a file should be indexed."""
        # Check extension
        if file_path.suffix.lower() not in self.config.extensions:
            return False
        
        # Check if in ignored directory
        for part in file_path.parts:
            if part in self.config.ignore_dirs:
                return False
            # Handle glob patterns like *.egg-info
            for pattern in self.config.ignore_dirs:
                if "*" in pattern and file_path.match(pattern):
                    return False
        
        # Check file size
        try:
            if file_path.stat().st_size > self.config.max_file_size:
                return False
        except OSError:
            return False
        
        return True
    
    def _get_file_hash(self, content: str) -> str:
        """Get hash of file content for change detection."""
        return hashlib.md5(content.encode()).hexdigest()
    
    def _read_file(self, file_path: Path) -> Optional[str]:
        """Safely read a file."""
        try:
            return file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None
    
    def index_file(self, file_path: Path, stats: IndexStats) -> bool:
        """Index a single file.
        
        Returns True if file was indexed, False if skipped.
        """
        content = self._read_file(file_path)
        if content is None:
            stats.errors.append(f"Could not read: {file_path}")
            return False
        
        # Get relative path for storage
        try:
            rel_path = str(file_path.relative_to(self.root_path))
        except ValueError:
            rel_path = str(file_path)
        
        # Chunk the file
        chunks = self.chunker.chunk_file(rel_path, content)
        if not chunks:
            stats.skipped_files.append(rel_path)
            return False
        
        # Generate embeddings
        texts = [chunk.content for chunk in chunks]
        embeddings = self.embedder.encode(texts, show_progress_bar=False).tolist()
        
        # Prepare data for ChromaDB
        ids = [chunk.id for chunk in chunks]
        documents = texts
        metadatas = [chunk.to_dict() for chunk in chunks]

        # Delete old chunks for this file (if re-indexing)
        try:
            existing = self._collection.get(where={"file_path": rel_path})
            if existing["ids"]:
                self._collection.delete(ids=existing["ids"])
        except Exception:
            pass  # Collection might be empty

        # Add to collection
        self._collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        stats.indexed_files.append(rel_path)
        stats.total_chunks += len(chunks)
        return True

    def index_directory(self, directory: Optional[Path] = None, verbose: bool = True) -> IndexStats:
        """Index all files in a directory recursively.

        Args:
            directory: Directory to index (defaults to root_path)
            verbose: Print progress

        Returns:
            IndexStats with results
        """
        directory = directory or self.root_path
        stats = IndexStats()

        # Find all files to index
        files_to_index = []
        for file_path in directory.rglob("*"):
            if file_path.is_file() and self._should_index_file(file_path):
                files_to_index.append(file_path)

        stats.total_files = len(files_to_index)

        if verbose:
            print(f"Found {len(files_to_index)} files to index...")

        # Index each file
        for i, file_path in enumerate(files_to_index):
            if verbose and (i + 1) % 10 == 0:
                print(f"  Indexed {i + 1}/{len(files_to_index)} files...")

            try:
                self.index_file(file_path, stats)
            except Exception as e:
                stats.errors.append(f"{file_path}: {str(e)}")

        if verbose:
            print(f"\n✓ Indexed {len(stats.indexed_files)} files ({stats.total_chunks} chunks)")
            if stats.errors:
                print(f"⚠ {len(stats.errors)} errors occurred")

        return stats

    def clear_index(self) -> None:
        """Clear the entire index."""
        self._client.delete_collection(self.config.collection_name)
        self._collection = self._client.create_collection(
            name=self.config.collection_name,
            metadata={"description": "Codebase index for semantic search"},
        )

    def get_stats(self) -> dict:
        """Get statistics about the current index."""
        count = self._collection.count()
        return {
            "total_chunks": count,
            "collection_name": self.config.collection_name,
            "embedding_model": self.config.embedding_model,
            "root_path": str(self.root_path),
        }

