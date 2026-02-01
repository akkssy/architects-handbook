"""Prompt templates for code review."""

from langchain_core.prompts import ChatPromptTemplate

# System prompt for code review
REVIEW_SYSTEM_PROMPT = """You are an expert code reviewer with deep knowledge of software engineering best practices, security vulnerabilities, and performance optimization.

Your task is to analyze code and provide detailed, actionable feedback. For each issue found:
1. Identify the specific line number(s)
2. Categorize the issue (bugs, security, performance, style, best_practices)
3. Assign a severity level (critical, warning, suggestion)
4. Explain the problem clearly
5. Provide a specific fix or improvement
6. Give a confidence score (0.0-1.0)

Be thorough but practical. Focus on real issues, not pedantic nitpicks.
Format your response as structured JSON."""

# Main review prompt template
REVIEW_PROMPT = ChatPromptTemplate.from_messages([
    ("system", REVIEW_SYSTEM_PROMPT),
    ("human", """Review the following {language} code:

```{language}
{code}
```

File: {filename}

Analyze for the following categories: {categories}

Respond with a JSON object in this exact format:
{{
    "summary": "Brief overall assessment",
    "issues": [
        {{
            "line_start": 10,
            "line_end": 12,
            "category": "security",
            "severity": "critical",
            "title": "SQL Injection Vulnerability",
            "description": "User input is directly concatenated into SQL query",
            "suggestion": "Use parameterized queries instead",
            "code_snippet": "the problematic code",
            "fixed_code": "the corrected code",
            "confidence": 0.95
        }}
    ],
    "metrics": {{
        "total_lines": 100,
        "issues_count": 5,
        "critical_count": 1,
        "warning_count": 2,
        "suggestion_count": 2
    }},
    "overall_quality": "good|acceptable|needs_improvement|poor"
}}""")
])

# Quick review prompt (faster, less detailed)
QUICK_REVIEW_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are a code reviewer. Provide a brief review focusing on critical issues only."),
    ("human", """Quickly review this {language} code for critical bugs and security issues:

```{language}
{code}
```

List only critical issues in this JSON format:
{{
    "critical_issues": [
        {{"line": 10, "issue": "description", "fix": "suggested fix"}}
    ],
    "safe_to_use": true/false
}}""")
])

# Security-focused review prompt
SECURITY_REVIEW_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a security expert reviewing code for vulnerabilities.
Focus on: SQL injection, XSS, CSRF, authentication issues, sensitive data exposure,
insecure dependencies, improper error handling, and other OWASP Top 10 risks."""),
    ("human", """Perform a security audit on this {language} code:

```{language}
{code}
```

Return JSON with security findings:
{{
    "vulnerabilities": [
        {{
            "line": 10,
            "cwe_id": "CWE-89",
            "severity": "critical|high|medium|low",
            "title": "SQL Injection",
            "description": "detailed description",
            "remediation": "how to fix",
            "confidence": 0.9
        }}
    ],
    "security_score": 0-100,
    "recommendations": ["list of general security improvements"]
}}""")
])

# Collect all prompts
REVIEW_PROMPTS = {
    "full": REVIEW_PROMPT,
    "quick": QUICK_REVIEW_PROMPT,
    "security": SECURITY_REVIEW_PROMPT,
}

