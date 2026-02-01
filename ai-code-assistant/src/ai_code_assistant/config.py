"""Configuration management for AI Code Assistant."""

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class LLMConfig(BaseModel):
    """LLM configuration settings."""
    model: str = "deepseek-coder:6.7b"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.1
    max_tokens: int = 4096
    timeout: int = 120


class ReviewConfig(BaseModel):
    """Code review configuration settings."""
    severity_levels: List[str] = Field(default=["critical", "warning", "suggestion"])
    categories: List[str] = Field(
        default=["bugs", "security", "performance", "style", "best_practices"]
    )
    max_file_size_kb: int = 500
    include_line_numbers: bool = True
    include_confidence: bool = True


class GenerationConfig(BaseModel):
    """Code generation configuration settings."""
    include_type_hints: bool = True
    include_docstrings: bool = True
    default_mode: str = "function"
    max_lines: int = 500


class OutputConfig(BaseModel):
    """Output configuration settings."""
    default_format: str = "console"
    use_colors: bool = True
    output_dir: str = "./output"
    verbose: bool = False


class RetrievalConfig(BaseModel):
    """Codebase retrieval configuration settings."""
    embedding_model: str = "all-MiniLM-L6-v2"
    persist_directory: str = ".ai-assistant-index"
    collection_name: str = "codebase"
    chunk_size: int = 50
    chunk_overlap: int = 10
    max_file_size_kb: int = 1024


class EditorConfig(BaseModel):
    """File editing configuration settings."""
    create_backup: bool = True
    show_diff: bool = True
    max_file_size_kb: int = 500
    auto_format: bool = False


class RefactorConfig(BaseModel):
    """Multi-file refactoring configuration settings."""
    max_files: int = 20
    max_file_size_kb: int = 500
    create_backup: bool = True
    require_confirmation: bool = True
    show_plan: bool = True


class LanguageConfig(BaseModel):
    """Language-specific configuration."""
    extensions: List[str]
    comment_style: str


class Config(BaseSettings):
    """Main configuration class."""
    llm: LLMConfig = Field(default_factory=LLMConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    editor: EditorConfig = Field(default_factory=EditorConfig)
    refactor: RefactorConfig = Field(default_factory=RefactorConfig)
    languages: Dict[str, LanguageConfig] = Field(default_factory=dict)

    class Config:
        env_prefix = "AI_ASSIST_"


def find_config_file() -> Optional[Path]:
    """Find configuration file in standard locations."""
    locations = [
        Path.cwd() / "config.yaml",
        Path.cwd() / ".ai-code-assistant.yaml",
        Path.home() / ".ai-code-assistant" / "config.yaml",
        Path.home() / ".config" / "ai-code-assistant" / "config.yaml",
    ]
    for path in locations:
        if path.exists():
            return path
    return None


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load configuration from file or use defaults."""
    if config_path is None:
        config_path = find_config_file()

    if config_path and config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f)
        return _parse_config(data)
    
    return Config()


def _parse_config(data: Dict[str, Any]) -> Config:
    """Parse configuration dictionary into Config object."""
    languages = {}
    if "languages" in data:
        for lang_name, lang_data in data["languages"].items():
            languages[lang_name] = LanguageConfig(**lang_data)
        data["languages"] = languages
    
    return Config(**data)


def get_language_by_extension(config: Config, file_path: Path) -> Optional[str]:
    """Detect language from file extension."""
    ext = file_path.suffix.lower()
    for lang_name, lang_config in config.languages.items():
        if ext in lang_config.extensions:
            return lang_name
    
    # Fallback detection
    extension_map = {
        ".py": "python", ".pyw": "python",
        ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
        ".ts": "typescript", ".tsx": "typescript",
        ".java": "java", ".go": "go", ".rs": "rust",
    }
    return extension_map.get(ext)

