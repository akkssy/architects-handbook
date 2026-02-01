"""
Semantic search over indexed codebase.

Provides natural language search capabilities.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from .indexer import IndexConfig


@dataclass
class SearchResult:
    """A single search result."""
    content: str
    file_path: str
    start_line: int
    end_line: int
    chunk_type: str
    name: str
    language: str
    score: float  # Similarity score (0-1, higher is better)
    
    def __str__(self) -> str:
        """Format result for display."""
        return (
            f"📄 {self.file_path}:{self.start_line}-{self.end_line} "
            f"({self.chunk_type}: {self.name}) [score: {self.score:.3f}]"
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "chunk_type": self.chunk_type,
            "name": self.name,
            "language": self.language,
            "score": self.score,
        }


@dataclass
class SearchResponse:
    """Response from a search query."""
    query: str
    results: List[SearchResult] = field(default_factory=list)
    total_results: int = 0
    
    @property
    def has_results(self) -> bool:
        return len(self.results) > 0
    
    def format_for_llm(self, max_results: int = 5) -> str:
        """Format results as context for LLM prompts."""
        if not self.results:
            return "No relevant code found."
        
        parts = [f"Found {len(self.results)} relevant code sections:\n"]
        
        for i, result in enumerate(self.results[:max_results], 1):
            parts.append(f"\n--- Result {i}: {result.file_path}:{result.start_line}-{result.end_line} ---")
            parts.append(f"Type: {result.chunk_type} | Name: {result.name}")
            parts.append(f"```{result.language or ''}")
            parts.append(result.content)
            parts.append("```\n")
        
        return "\n".join(parts)


class CodebaseSearch:
    """Semantic search over indexed codebase."""
    
    def __init__(self, config: Optional[IndexConfig] = None, root_path: Optional[str] = None):
        """Initialize search.
        
        Args:
            config: Index configuration (must match indexer config)
            root_path: Root directory of the codebase
        """
        self.config = config or IndexConfig()
        self.root_path = Path(root_path) if root_path else Path.cwd()
        
        # Initialize embedding model (lazy load)
        self._embedder: Optional[SentenceTransformer] = None
        
        # Connect to ChromaDB
        persist_path = self.root_path / self.config.persist_directory
        if not persist_path.exists():
            raise FileNotFoundError(
                f"Index not found at {persist_path}. Run 'ai-assist index' first."
            )
        
        self._client = chromadb.PersistentClient(
            path=str(persist_path),
            settings=Settings(anonymized_telemetry=False),
        )
        
        try:
            self._collection = self._client.get_collection(self.config.collection_name)
        except Exception:
            raise FileNotFoundError(
                f"Collection '{self.config.collection_name}' not found. Run 'ai-assist index' first."
            )
    
    @property
    def embedder(self) -> SentenceTransformer:
        """Lazy load the embedding model."""
        if self._embedder is None:
            self._embedder = SentenceTransformer(self.config.embedding_model)
        return self._embedder
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.0,
        file_filter: Optional[str] = None,
        language_filter: Optional[str] = None,
    ) -> SearchResponse:
        """Search for relevant code.
        
        Args:
            query: Natural language search query
            top_k: Maximum number of results
            min_score: Minimum similarity score (0-1)
            file_filter: Filter by file path (substring match)
            language_filter: Filter by programming language
            
        Returns:
            SearchResponse with results
        """
        # Generate query embedding
        query_embedding = self.embedder.encode(query, show_progress_bar=False).tolist()
        
        # Build where clause for filtering
        where = None
        if language_filter:
            where = {"language": language_filter}
        
        # Search ChromaDB
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        
        # Process results
        search_results = []

        if results["documents"] and results["documents"][0]:
            documents = results["documents"][0]
            metadatas = results["metadatas"][0] if results["metadatas"] else [{}] * len(documents)
            distances = results["distances"][0] if results["distances"] else [0] * len(documents)

            for doc, meta, distance in zip(documents, metadatas, distances):
                # Convert distance to similarity score (ChromaDB returns L2 distance)
                # Lower distance = more similar, so we convert
                score = 1 / (1 + distance)

                # Apply minimum score filter
                if score < min_score:
                    continue

                # Apply file filter
                file_path = meta.get("file_path", "")
                if file_filter and file_filter.lower() not in file_path.lower():
                    continue

                search_results.append(SearchResult(
                    content=doc,
                    file_path=file_path,
                    start_line=int(meta.get("start_line", 0)),
                    end_line=int(meta.get("end_line", 0)),
                    chunk_type=meta.get("chunk_type", "unknown"),
                    name=meta.get("name", ""),
                    language=meta.get("language", ""),
                    score=score,
                ))

        return SearchResponse(
            query=query,
            results=search_results,
            total_results=len(search_results),
        )

    def search_similar(self, code: str, top_k: int = 5) -> SearchResponse:
        """Find code similar to the given code snippet.

        Args:
            code: Code snippet to find similar code for
            top_k: Maximum number of results

        Returns:
            SearchResponse with similar code
        """
        return self.search(query=code, top_k=top_k)

    def get_file_context(self, file_path: str) -> List[SearchResult]:
        """Get all indexed chunks for a specific file.

        Args:
            file_path: Path to the file

        Returns:
            List of SearchResult for the file
        """
        results = self._collection.get(
            where={"file_path": file_path},
            include=["documents", "metadatas"],
        )

        search_results = []
        if results["documents"]:
            for doc, meta in zip(results["documents"], results["metadatas"]):
                search_results.append(SearchResult(
                    content=doc,
                    file_path=meta.get("file_path", ""),
                    start_line=int(meta.get("start_line", 0)),
                    end_line=int(meta.get("end_line", 0)),
                    chunk_type=meta.get("chunk_type", "unknown"),
                    name=meta.get("name", ""),
                    language=meta.get("language", ""),
                    score=1.0,  # Not a similarity search
                ))

        # Sort by line number
        search_results.sort(key=lambda x: x.start_line)
        return search_results

