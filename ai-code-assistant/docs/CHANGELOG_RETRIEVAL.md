# Codebase Indexing & Search Feature

**Date:** 2026-01-23  
**Version:** 0.2.0  
**Feature:** RAG (Retrieval Augmented Generation) Capabilities

## Overview

Added semantic search capabilities to the AI Code Assistant, enabling natural language queries to find relevant code in your codebase.

## New Dependencies

```toml
chromadb>=1.0.0        # Vector database for embeddings
sentence-transformers>=2.0.0  # Local embedding models
watchdog>=4.0.0        # File system monitoring (future use)
```

## New Files

### `src/ai_code_assistant/retrieval/`

| File | Purpose |
|------|---------|
| `__init__.py` | Module exports |
| `chunker.py` | Code chunking with AST parsing |
| `indexer.py` | ChromaDB indexer with embeddings |
| `search.py` | Semantic search implementation |

### `tests/test_retrieval.py`
- 18 comprehensive unit tests
- Tests for chunking, indexing, and search

## Modified Files

### `pyproject.toml`
- Added new dependencies

### `src/ai_code_assistant/config.py`
- Added `RetrievalConfig` class

### `config.yaml`
- Added `retrieval` configuration section

### `src/ai_code_assistant/cli.py`
- Added `index` command
- Added `search` command
- Updated `status` to show index info

## New CLI Commands

### Index Command
```bash
ai-assist index [DIRECTORY] [--clear]
```

### Search Command
```bash
ai-assist search "QUERY" [-k N] [-f FILE] [-l LANG] [--format FORMAT]
```

## Configuration Options

```yaml
retrieval:
  embedding_model: "all-MiniLM-L6-v2"
  persist_directory: ".ai-assistant-index"
  collection_name: "codebase"
  chunk_size: 50
  chunk_overlap: 10
  max_file_size_kb: 1024
```

## Architecture

```
User Query → Embedding Model → Vector Search → Ranked Results
     ↓
Code Files → Chunker → Embeddings → ChromaDB Index
```

## Key Classes

- `CodeChunker` - Splits code into semantic chunks
- `CodebaseIndexer` - Creates and manages the index
- `CodebaseSearch` - Performs semantic searches
- `SearchResult` - Individual search result
- `SearchResponse` - Collection of results with formatting

