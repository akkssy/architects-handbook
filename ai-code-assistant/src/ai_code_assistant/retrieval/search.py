"""
Semantic and hybrid search over indexed codebase.

Provides natural language search capabilities with optional BM25 keyword search
and cross-encoder re-ranking for improved precision.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from pathlib import Path
import re

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer, CrossEncoder

from .indexer import IndexConfig

# BM25 for keyword search (optional, graceful fallback)
try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False

# Cross-encoder for re-ranking (optional, graceful fallback)
try:
    from sentence_transformers import CrossEncoder
    RERANK_AVAILABLE = True
except ImportError:
    RERANK_AVAILABLE = False


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
    score: float  # Combined/final score (0-1, higher is better)
    semantic_score: float = 0.0  # Score from semantic/vector search
    keyword_score: float = 0.0  # Score from BM25 keyword search

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
            "semantic_score": self.semantic_score,
            "keyword_score": self.keyword_score,
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
    """Semantic and hybrid search over indexed codebase."""

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

        # Cross-encoder for re-ranking (lazy load)
        self._reranker: Optional["CrossEncoder"] = None
        self._rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

        # BM25 index (lazy load)
        self._bm25_index: Optional["BM25Okapi"] = None
        self._bm25_documents: List[str] = []
        self._bm25_doc_ids: List[str] = []
        self._bm25_metadatas: List[Dict] = []

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

    @property
    def reranker(self) -> Optional["CrossEncoder"]:
        """Lazy load the cross-encoder re-ranking model."""
        if self._reranker is None and RERANK_AVAILABLE:
            self._reranker = CrossEncoder(self._rerank_model)
        return self._reranker

    def _rerank(
        self,
        query: str,
        results: List[SearchResult],
        top_k: int = 10,
    ) -> List[SearchResult]:
        """Re-rank search results using cross-encoder.

        Cross-encoders jointly encode query and document, providing more accurate
        relevance scores than bi-encoder (embedding) similarity.

        Args:
            query: Original search query
            results: Initial search results to re-rank
            top_k: Number of results to return after re-ranking

        Returns:
            Re-ranked list of SearchResult with updated scores
        """
        if not RERANK_AVAILABLE or self.reranker is None or not results:
            return results[:top_k]

        # Prepare query-document pairs for cross-encoder
        pairs = [(query, result.content) for result in results]

        # Get cross-encoder scores
        rerank_scores = self.reranker.predict(pairs, show_progress_bar=False)

        # Normalize scores to 0-1 range (cross-encoder scores can be arbitrary)
        min_score = min(rerank_scores)
        max_score = max(rerank_scores)
        score_range = max_score - min_score if max_score > min_score else 1.0

        # Create new results with updated scores
        reranked_results = []
        for result, rerank_score in zip(results, rerank_scores):
            normalized_score = (rerank_score - min_score) / score_range
            reranked_results.append(SearchResult(
                content=result.content,
                file_path=result.file_path,
                start_line=result.start_line,
                end_line=result.end_line,
                chunk_type=result.chunk_type,
                name=result.name,
                language=result.language,
                score=normalized_score,
                semantic_score=result.semantic_score,
                keyword_score=result.keyword_score,
            ))

        # Sort by new score and take top_k
        reranked_results.sort(key=lambda x: x.score, reverse=True)
        return reranked_results[:top_k]

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text for BM25 search.

        Handles code-specific tokenization including:
        - camelCase and snake_case splitting
        - ALL_CAPS words preserved as single tokens
        - Preserving important symbols
        - Lowercasing
        """
        # Split on whitespace, punctuation, and common separators
        # But preserve underscores and dots within identifiers
        # Don't lowercase yet - we need case info for camelCase splitting
        tokens = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*|[0-9]+', text)

        # Also split camelCase and snake_case
        expanded_tokens = []
        for token in tokens:
            # First split by underscore (snake_case)
            parts_by_underscore = token.split('_')
            for part in parts_by_underscore:
                if not part:
                    continue
                # Check if it's all uppercase (like "AUTH", "HTTP", "API")
                if part.isupper():
                    expanded_tokens.append(part.lower())
                else:
                    # Split camelCase: "processRequest" -> ["process", "Request"]
                    # Handles: lowercase runs, Uppercase+lowercase, numbers, and uppercase sequences
                    camel_parts = re.findall(r'[a-z]+|[A-Z]+(?=[A-Z][a-z]|$|[0-9])|[A-Z][a-z]*|[0-9]+', part)
                    expanded_tokens.extend([p.lower() for p in camel_parts if p])

        return expanded_tokens

    def _build_bm25_index(self) -> None:
        """Build BM25 index from ChromaDB documents."""
        if not BM25_AVAILABLE:
            return

        # Fetch all documents from ChromaDB
        all_docs = self._collection.get(include=["documents", "metadatas"])

        if not all_docs["documents"]:
            return

        self._bm25_documents = all_docs["documents"]
        self._bm25_doc_ids = all_docs["ids"]
        self._bm25_metadatas = all_docs["metadatas"]

        # Tokenize documents for BM25
        tokenized_docs = [self._tokenize(doc) for doc in self._bm25_documents]

        # Build BM25 index
        self._bm25_index = BM25Okapi(tokenized_docs)

    @property
    def bm25_index(self) -> Optional["BM25Okapi"]:
        """Lazy load the BM25 index."""
        if self._bm25_index is None and BM25_AVAILABLE:
            self._build_bm25_index()
        return self._bm25_index

    def _bm25_search(
        self,
        query: str,
        top_k: int = 10,
        file_filter: Optional[str] = None,
        language_filter: Optional[str] = None,
    ) -> List[Tuple[str, Dict, float]]:
        """Perform BM25 keyword search.

        Returns:
            List of (document, metadata, score) tuples
        """
        if not BM25_AVAILABLE or self.bm25_index is None:
            return []

        # Tokenize query
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Get BM25 scores for all documents
        scores = self.bm25_index.get_scores(query_tokens)

        # Create list of (doc, metadata, score) with filtering
        results = []
        for idx, score in enumerate(scores):
            if score <= 0:
                continue

            meta = self._bm25_metadatas[idx]

            # Apply filters
            if file_filter:
                file_path = meta.get("file_path", "")
                if file_filter.lower() not in file_path.lower():
                    continue

            if language_filter:
                if meta.get("language", "") != language_filter:
                    continue

            results.append((
                self._bm25_documents[idx],
                meta,
                score
            ))

        # Sort by score descending and take top_k
        results.sort(key=lambda x: x[2], reverse=True)
        return results[:top_k]
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.0,
        file_filter: Optional[str] = None,
        language_filter: Optional[str] = None,
    ) -> SearchResponse:
        """Search for relevant code using semantic (vector) search only.

        For combined semantic + keyword search, use hybrid_search() instead.

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
                    semantic_score=score,
                    keyword_score=0.0,
                ))

        return SearchResponse(
            query=query,
            results=search_results,
            total_results=len(search_results),
        )

    def hybrid_search(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.0,
        alpha: float = 0.5,
        file_filter: Optional[str] = None,
        language_filter: Optional[str] = None,
        rerank: bool = False,
        rerank_top_k: int = 20,
    ) -> SearchResponse:
        """Search for relevant code using hybrid search (semantic + BM25 keyword).

        Combines vector-based semantic search with BM25 keyword search for better
        retrieval of exact matches (function names, class names, error codes).

        Optionally applies cross-encoder re-ranking for improved precision.

        Args:
            query: Natural language or code search query
            top_k: Maximum number of results
            min_score: Minimum combined score (0-1)
            alpha: Balance between semantic (1.0) and keyword (0.0) search.
                   Default 0.5 gives equal weight to both.
            file_filter: Filter by file path (substring match)
            language_filter: Filter by programming language
            rerank: Whether to apply cross-encoder re-ranking
            rerank_top_k: Number of candidates to fetch for re-ranking

        Returns:
            SearchResponse with results sorted by combined score
        """
        # If BM25 not available, fall back to semantic search
        if not BM25_AVAILABLE:
            return self.search(
                query=query,
                top_k=top_k,
                min_score=min_score,
                file_filter=file_filter,
                language_filter=language_filter,
            )

        # Get more results from each method for better fusion
        # If re-ranking, fetch more candidates
        fetch_k = rerank_top_k if rerank else min(top_k * 3, 100)

        # 1. Semantic search (vector-based)
        semantic_response = self.search(
            query=query,
            top_k=fetch_k,
            min_score=0.0,  # Don't filter yet
            file_filter=file_filter,
            language_filter=language_filter,
        )

        # 2. BM25 keyword search
        bm25_results = self._bm25_search(
            query=query,
            top_k=fetch_k,
            file_filter=file_filter,
            language_filter=language_filter,
        )

        # Create lookup maps for score fusion
        # Key: (file_path, start_line) to identify unique chunks
        semantic_scores: Dict[Tuple[str, int], Tuple[SearchResult, float]] = {}
        for result in semantic_response.results:
            key = (result.file_path, result.start_line)
            semantic_scores[key] = (result, result.score)

        keyword_scores: Dict[Tuple[str, int], Tuple[str, Dict, float]] = {}
        if bm25_results:
            # Normalize BM25 scores to 0-1 range
            max_bm25 = max(r[2] for r in bm25_results) if bm25_results else 1.0
            for doc, meta, score in bm25_results:
                key = (meta.get("file_path", ""), int(meta.get("start_line", 0)))
                normalized_score = score / max_bm25 if max_bm25 > 0 else 0
                keyword_scores[key] = (doc, meta, normalized_score)

        # 3. Score fusion using weighted combination
        all_keys = set(semantic_scores.keys()) | set(keyword_scores.keys())

        fused_results: List[SearchResult] = []
        for key in all_keys:
            sem_score = 0.0
            kw_score = 0.0

            if key in semantic_scores:
                result, sem_score = semantic_scores[key]
                doc = result.content
                meta = {
                    "file_path": result.file_path,
                    "start_line": result.start_line,
                    "end_line": result.end_line,
                    "chunk_type": result.chunk_type,
                    "name": result.name,
                    "language": result.language,
                }
            elif key in keyword_scores:
                doc, meta, kw_score = keyword_scores[key]
            else:
                continue

            if key in keyword_scores:
                _, _, kw_score = keyword_scores[key]

            # Weighted combination: alpha * semantic + (1-alpha) * keyword
            combined_score = alpha * sem_score + (1 - alpha) * kw_score

            # Apply minimum score filter
            if combined_score < min_score:
                continue

            fused_results.append(SearchResult(
                content=doc,
                file_path=meta.get("file_path", ""),
                start_line=int(meta.get("start_line", 0)),
                end_line=int(meta.get("end_line", 0)),
                chunk_type=meta.get("chunk_type", "unknown"),
                name=meta.get("name", ""),
                language=meta.get("language", ""),
                score=combined_score,
                semantic_score=sem_score,
                keyword_score=kw_score,
            ))

        # Sort by combined score
        fused_results.sort(key=lambda x: x.score, reverse=True)

        # Apply re-ranking if enabled
        if rerank and RERANK_AVAILABLE:
            # Re-rank the top candidates and take top_k
            final_results = self._rerank(query, fused_results[:rerank_top_k], top_k)
        else:
            final_results = fused_results[:top_k]

        return SearchResponse(
            query=query,
            results=final_results,
            total_results=len(final_results),
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

