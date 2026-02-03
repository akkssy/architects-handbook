"""
Codebase retrieval module for semantic and hybrid search.

This module provides functionality to:
- Index code files into a vector database
- Search for relevant code using natural language queries (semantic search)
- Search for exact matches using BM25 keyword search (hybrid search)
- Watch for file changes and update the index
"""

from .indexer import CodebaseIndexer
from .search import CodebaseSearch, SearchResult, SearchResponse
from .chunker import CodeChunker

__all__ = [
    "CodebaseIndexer",
    "CodebaseSearch",
    "SearchResult",
    "SearchResponse",
    "CodeChunker",
]

