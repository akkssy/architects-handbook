"""Code analyzer for reviewing code files."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from ai_code_assistant.config import Config, get_language_by_extension
from ai_code_assistant.llm import LLMManager
from ai_code_assistant.reviewer.prompts import REVIEW_PROMPTS


# Retry prompt for when JSON parsing fails
RETRY_JSON_PROMPT = """Your previous response was not valid JSON. Please provide ONLY valid JSON output.

Here is the code to review again:
```{language}
{code}
```

Return ONLY a JSON object with this structure:
{{
  "summary": "Brief summary",
  "issues": [
    {{
      "line_start": 1,
      "line_end": 1,
      "category": "bugs|security|performance|style|best_practices",
      "severity": "critical|warning|suggestion",
      "title": "Short title",
      "description": "What's wrong",
      "suggestion": "How to fix it",
      "confidence": 0.8
    }}
  ],
  "overall_quality": "good|acceptable|needs_improvement|poor"
}}

Return ONLY the JSON, no other text."""


@dataclass
class ReviewIssue:
    """Represents a single code review issue."""
    line_start: int
    line_end: int
    category: str
    severity: str
    title: str
    description: str
    suggestion: str
    code_snippet: str = ""
    fixed_code: str = ""
    confidence: float = 0.0


@dataclass
class ReviewResult:
    """Complete review result for a file."""
    filename: str
    language: str
    summary: str
    issues: List[ReviewIssue] = field(default_factory=list)
    metrics: Dict = field(default_factory=dict)
    overall_quality: str = "unknown"
    raw_response: str = ""
    error: Optional[str] = None

    @property
    def critical_issues(self) -> List[ReviewIssue]:
        return [i for i in self.issues if i.severity == "critical"]

    @property
    def warnings(self) -> List[ReviewIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def suggestions(self) -> List[ReviewIssue]:
        return [i for i in self.issues if i.severity == "suggestion"]


class CodeAnalyzer:
    """Analyzes code files for issues and improvements."""

    def __init__(self, config: Config, llm_manager: LLMManager):
        self.config = config
        self.llm = llm_manager

    def review_file(
        self,
        file_path: Path,
        review_type: str = "full",
        categories: Optional[List[str]] = None,
    ) -> ReviewResult:
        """Review a single code file."""
        if not file_path.exists():
            return ReviewResult(
                filename=str(file_path),
                language="unknown",
                summary="",
                error=f"File not found: {file_path}"
            )

        # Check file size
        file_size_kb = file_path.stat().st_size / 1024
        if file_size_kb > self.config.review.max_file_size_kb:
            return ReviewResult(
                filename=str(file_path),
                language="unknown",
                summary="",
                error=f"File too large: {file_size_kb:.1f}KB (max: {self.config.review.max_file_size_kb}KB)"
            )

        # Detect language
        language = get_language_by_extension(self.config, file_path)
        if not language:
            language = "unknown"

        # Read code
        code = file_path.read_text()
        
        # Use configured categories if not specified
        if categories is None:
            categories = self.config.review.categories

        return self._analyze_code(
            code=code,
            filename=str(file_path),
            language=language,
            review_type=review_type,
            categories=categories,
        )

    def review_code(
        self,
        code: str,
        language: str = "python",
        filename: str = "code_snippet",
        review_type: str = "full",
        categories: Optional[List[str]] = None,
    ) -> ReviewResult:
        """Review a code string directly."""
        if categories is None:
            categories = self.config.review.categories

        return self._analyze_code(
            code=code,
            filename=filename,
            language=language,
            review_type=review_type,
            categories=categories,
        )

    def _analyze_code(
        self,
        code: str,
        filename: str,
        language: str,
        review_type: str,
        categories: List[str],
        max_retries: int = 2,
    ) -> ReviewResult:
        """Internal method to analyze code using LLM with retry logic."""
        prompt_template = REVIEW_PROMPTS.get(review_type, REVIEW_PROMPTS["full"])

        try:
            response = self.llm.invoke_with_template(
                prompt_template,
                code=code,
                language=language,
                filename=filename,
                categories=", ".join(categories),
            )
            result = self._parse_review_response(response, filename, language)

            # Retry if parsing failed
            retries = 0
            while result.error and "Parse error" in result.error and retries < max_retries:
                retries += 1
                retry_prompt = RETRY_JSON_PROMPT.format(language=language, code=code)
                response = self.llm.invoke(retry_prompt)
                result = self._parse_review_response(response, filename, language)

            return result
        except Exception as e:
            return ReviewResult(
                filename=filename,
                language=language,
                summary="",
                error=f"Analysis failed: {str(e)}",
                raw_response=""
            )

    def _extract_json(self, response: str) -> str:
        """Extract JSON from LLM response, handling various formats."""
        # Try to find JSON in code blocks
        if "```json" in response:
            match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if match:
                return match.group(1)

        if "```" in response:
            match = re.search(r'```\s*(.*?)\s*```', response, re.DOTALL)
            if match:
                return match.group(1)

        # Try to find JSON object directly
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            return match.group(0)

        return response

    def _repair_json(self, json_str: str) -> str:
        """Attempt to repair common JSON issues."""
        # Remove trailing commas before } or ]
        json_str = re.sub(r',\s*([}\]])', r'\1', json_str)

        # Fix unquoted keys (simple cases)
        json_str = re.sub(r'(\{|\,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', json_str)

        # Fix single quotes to double quotes
        json_str = json_str.replace("'", '"')

        # Remove comments
        json_str = re.sub(r'//.*$', '', json_str, flags=re.MULTILINE)

        return json_str

    def _parse_review_response(
        self, response: str, filename: str, language: str
    ) -> ReviewResult:
        """Parse LLM response into ReviewResult."""
        try:
            json_str = self._extract_json(response)

            try:
                data = json.loads(json_str.strip())
            except json.JSONDecodeError:
                # Try to repair JSON
                repaired = self._repair_json(json_str)
                data = json.loads(repaired.strip())

            issues = [
                ReviewIssue(
                    line_start=i.get("line_start", i.get("line", 0)),
                    line_end=i.get("line_end", i.get("line", 0)),
                    category=i.get("category", "unknown"),
                    severity=i.get("severity", "suggestion"),
                    title=i.get("title", "Issue"),
                    description=i.get("description", ""),
                    suggestion=i.get("suggestion", i.get("fix", "")),
                    code_snippet=i.get("code_snippet", ""),
                    fixed_code=i.get("fixed_code", ""),
                    confidence=float(i.get("confidence", 0.5)),
                )
                for i in data.get("issues", data.get("critical_issues", []))
            ]

            return ReviewResult(
                filename=filename,
                language=language,
                summary=data.get("summary", "Review complete"),
                issues=issues,
                metrics=data.get("metrics", {}),
                overall_quality=data.get("overall_quality", "unknown"),
                raw_response=response,
            )
        except (json.JSONDecodeError, KeyError) as e:
            return ReviewResult(
                filename=filename,
                language=language,
                summary="Failed to parse review response",
                raw_response=response,
                error=f"Parse error: {str(e)}"
            )

