"""Knowledge base manager for persistent learning and context."""

import os
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


@dataclass
class KnowledgeEntry:
    """A single knowledge entry."""
    id: str
    title: str
    content: str
    tags: List[str] = field(default_factory=list)
    category: str = "general"
    created_at: str = ""
    updated_at: str = ""
    file_path: str = ""
    source: str = ""  # Where this knowledge came from (user, ai, code)
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeEntry":
        return cls(**data)
    
    def to_markdown(self) -> str:
        """Convert entry to markdown format."""
        lines = [
            f"# {self.title}",
            "",
            f"**ID:** {self.id}",
            f"**Category:** {self.category}",
            f"**Tags:** {', '.join(self.tags) if self.tags else 'none'}",
            f"**Created:** {self.created_at}",
            f"**Updated:** {self.updated_at}",
            f"**Source:** {self.source}",
            "",
            "---",
            "",
            self.content,
        ]
        return "\n".join(lines)
    
    @classmethod
    def from_markdown(cls, content: str, file_path: str = "") -> Optional["KnowledgeEntry"]:
        """Parse a markdown file into a KnowledgeEntry."""
        try:
            lines = content.split("\n")
            title = ""
            entry_id = ""
            category = "general"
            tags: List[str] = []
            created_at = ""
            updated_at = ""
            source = ""
            body_start = 0
            
            for i, line in enumerate(lines):
                if line.startswith("# "):
                    title = line[2:].strip()
                elif line.startswith("**ID:**"):
                    entry_id = line.replace("**ID:**", "").strip()
                elif line.startswith("**Category:**"):
                    category = line.replace("**Category:**", "").strip()
                elif line.startswith("**Tags:**"):
                    tags_str = line.replace("**Tags:**", "").strip()
                    tags = [t.strip() for t in tags_str.split(",") if t.strip() and t.strip() != "none"]
                elif line.startswith("**Created:**"):
                    created_at = line.replace("**Created:**", "").strip()
                elif line.startswith("**Updated:**"):
                    updated_at = line.replace("**Updated:**", "").strip()
                elif line.startswith("**Source:**"):
                    source = line.replace("**Source:**", "").strip()
                elif line == "---":
                    body_start = i + 2
                    break
            
            body = "\n".join(lines[body_start:]).strip()
            
            if not entry_id:
                entry_id = hashlib.md5(title.encode()).hexdigest()[:12]
            
            return cls(
                id=entry_id,
                title=title,
                content=body,
                tags=tags,
                category=category,
                created_at=created_at,
                updated_at=updated_at,
                file_path=file_path,
                source=source,
            )
        except Exception:
            return None


class KnowledgeManager:
    """Manages knowledge base stored in markdown files."""
    
    DEFAULT_DIR = ".cognify/knowledge"
    
    def __init__(self, root_path: Optional[str] = None):
        self.root_path = Path(root_path) if root_path else Path.cwd()
        self.knowledge_dir = self.root_path / self.DEFAULT_DIR
        self._ensure_directory()
    
    def _ensure_directory(self):
        """Ensure knowledge directory exists."""
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        
        # Create .gitignore if it doesn't exist
        gitignore = self.knowledge_dir.parent / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text("# Cognify AI local files\n")
    
    def _generate_id(self, title: str) -> str:
        """Generate a unique ID for an entry."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        hash_part = hashlib.md5(f"{title}{timestamp}".encode()).hexdigest()[:8]
        return f"{timestamp}-{hash_part}"
    
    def _sanitize_filename(self, title: str) -> str:
        """Convert title to a safe filename."""
        # Remove special characters and replace spaces with hyphens
        safe = re.sub(r'[^\w\s-]', '', title.lower())
        safe = re.sub(r'[-\s]+', '-', safe).strip('-')
        return safe[:50]  # Limit length

    def save(self, title: str, content: str, tags: List[str] = None,
             category: str = "general", source: str = "user") -> KnowledgeEntry:
        """Save a new knowledge entry."""
        entry_id = self._generate_id(title)
        filename = f"{self._sanitize_filename(title)}.md"
        file_path = self.knowledge_dir / category / filename

        # Ensure category directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        entry = KnowledgeEntry(
            id=entry_id,
            title=title,
            content=content,
            tags=tags or [],
            category=category,
            source=source,
            file_path=str(file_path.relative_to(self.root_path)),
        )

        file_path.write_text(entry.to_markdown())
        return entry

    def update(self, entry_id: str, content: str = None, title: str = None,
               tags: List[str] = None) -> Optional[KnowledgeEntry]:
        """Update an existing knowledge entry."""
        entry = self.get(entry_id)
        if not entry:
            return None

        if content:
            entry.content = content
        if title:
            entry.title = title
        if tags is not None:
            entry.tags = tags

        entry.updated_at = datetime.now().isoformat()

        file_path = self.root_path / entry.file_path
        file_path.write_text(entry.to_markdown())
        return entry

    def get(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """Get a knowledge entry by ID."""
        for entry in self.list_all():
            if entry.id == entry_id:
                return entry
        return None

    def delete(self, entry_id: str) -> bool:
        """Delete a knowledge entry."""
        entry = self.get(entry_id)
        if not entry:
            return False

        file_path = self.root_path / entry.file_path
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def list_all(self, category: str = None) -> List[KnowledgeEntry]:
        """List all knowledge entries, optionally filtered by category."""
        entries = []

        search_dir = self.knowledge_dir / category if category else self.knowledge_dir
        if not search_dir.exists():
            return entries

        for md_file in search_dir.rglob("*.md"):
            content = md_file.read_text()
            entry = KnowledgeEntry.from_markdown(
                content,
                str(md_file.relative_to(self.root_path))
            )
            if entry:
                entries.append(entry)

        return sorted(entries, key=lambda e: e.updated_at, reverse=True)

    def search(self, query: str, tags: List[str] = None,
               category: str = None, limit: int = 10) -> List[KnowledgeEntry]:
        """Search knowledge entries by query and/or tags."""
        entries = self.list_all(category)
        results = []

        query_lower = query.lower() if query else ""

        for entry in entries:
            score = 0

            # Check title match
            if query_lower and query_lower in entry.title.lower():
                score += 3

            # Check content match
            if query_lower and query_lower in entry.content.lower():
                score += 2

            # Check tag match
            if tags:
                matching_tags = set(tags) & set(entry.tags)
                score += len(matching_tags) * 2

            # Check if query words appear in tags
            if query_lower:
                for word in query_lower.split():
                    if any(word in tag.lower() for tag in entry.tags):
                        score += 1

            if score > 0:
                results.append((score, entry))

        # Sort by score and return top results
        results.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in results[:limit]]

    def get_context_for_query(self, query: str, max_entries: int = 3) -> str:
        """Get relevant knowledge formatted as context for LLM."""
        entries = self.search(query, limit=max_entries)

        if not entries:
            return ""

        parts = ["=== Relevant Knowledge from Project ===\n"]

        for entry in entries:
            parts.append(f"\n### {entry.title}")
            parts.append(f"Category: {entry.category} | Tags: {', '.join(entry.tags)}")
            parts.append(f"\n{entry.content}\n")
            parts.append("---")

        return "\n".join(parts)

    def get_categories(self) -> List[str]:
        """Get all knowledge categories."""
        categories = set()
        for entry in self.list_all():
            categories.add(entry.category)
        return sorted(categories)

    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        entries = self.list_all()
        categories = {}
        tags = {}

        for entry in entries:
            categories[entry.category] = categories.get(entry.category, 0) + 1
            for tag in entry.tags:
                tags[tag] = tags.get(tag, 0) + 1

        return {
            "total_entries": len(entries),
            "categories": categories,
            "tags": tags,
            "knowledge_dir": str(self.knowledge_dir),
        }

