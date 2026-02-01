"""Prompt templates for code generation."""

from langchain_core.prompts import ChatPromptTemplate

# System prompt for code generation
GENERATION_SYSTEM_PROMPT = """You are an expert software developer who writes clean, efficient, and well-documented code.

When generating code:
1. Follow best practices and design patterns for the language
2. Include comprehensive docstrings and comments
3. Add type hints where applicable
4. Handle edge cases and errors appropriately
5. Write code that is readable and maintainable

Output ONLY the code, wrapped in appropriate markdown code blocks.
Do not include explanations unless specifically requested."""

# Function generation prompt
FUNCTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", GENERATION_SYSTEM_PROMPT),
    ("human", """Generate a {language} function with the following specification:

**Description:** {description}
**Function name:** {name}
**Parameters:** {parameters}
**Return type:** {return_type}
**Additional requirements:**
- Include type hints: {include_type_hints}
- Include docstring: {include_docstrings}

Generate only the function code, no usage examples.""")
])

# Class generation prompt
CLASS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", GENERATION_SYSTEM_PROMPT),
    ("human", """Generate a {language} class with the following specification:

**Description:** {description}
**Class name:** {name}
**Attributes:** {attributes}
**Methods:** {methods}
**Additional requirements:**
- Include type hints: {include_type_hints}
- Include docstrings: {include_docstrings}
- Follow {language} best practices and conventions

Generate the complete class implementation.""")
])

# Script/module generation prompt
SCRIPT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", GENERATION_SYSTEM_PROMPT),
    ("human", """Generate a complete {language} script/module:

**Description:** {description}
**Features/functionality required:**
{requirements}

**Additional requirements:**
- Include proper imports
- Include type hints: {include_type_hints}
- Include docstrings: {include_docstrings}
- Include a main entry point if applicable
- Handle errors appropriately

Generate the complete script.""")
])

# Test file generation prompt
TEST_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert at writing comprehensive test suites.
Write tests that cover happy paths, edge cases, and error conditions.
Use appropriate testing frameworks and assertions."""),
    ("human", """Generate {language} tests for the following code:

```{language}
{source_code}
```

**Test framework:** {test_framework}
**Coverage requirements:**
- Test all public functions/methods
- Include edge case tests
- Include error handling tests
- Use descriptive test names

Generate a complete test file.""")
])

# Generic code generation prompt
GENERIC_PROMPT = ChatPromptTemplate.from_messages([
    ("system", GENERATION_SYSTEM_PROMPT),
    ("human", """Generate {language} code for the following request:

{description}

Requirements:
- Include type hints: {include_type_hints}
- Include docstrings: {include_docstrings}
- Follow best practices

Generate clean, production-ready code.""")
])

# Collect all prompts
GENERATION_PROMPTS = {
    "function": FUNCTION_PROMPT,
    "class": CLASS_PROMPT,
    "script": SCRIPT_PROMPT,
    "test": TEST_PROMPT,
    "generic": GENERIC_PROMPT,
}

