"""
Codebase retrieval module for semantic search.

This module provides functionality to:
- Index code files into a vector database
- Search for relevant code using natural language queries
- Watch for file changes and update the index
"""

from .indexer import CodebaseIndexer
from .search import CodebaseSearch
from .chunker import CodeChunker

__all__ = [
    "CodebaseIndexer",
    "CodebaseSearch", 
    "CodeChunker",
]

