# Contributing to Software Engineering Study Guides

Thank you for your interest in contributing! This guide will help you get started.

## 📚 Project Overview

This repository contains two study guides:
- **DSA Study Guide** (`index.html`) - Data Structures & Algorithms
- **Architect's Handbook** (`software-engineering-knowledge-base.html`) - System Design

## 🎯 Ways to Contribute

### 1. Report Issues
- Found a bug or typo? [Open an issue](../../issues/new)
- Include screenshots if relevant
- Describe the expected vs actual behavior

### 2. Suggest Improvements
- Have an idea for a new topic? Open an issue with the `enhancement` label
- Want to improve an explanation? PRs are welcome!

### 3. Add Content

**For DSA Study Guide:**
- New LeetCode problems with solutions
- Additional video tutorial links
- Solutions in other languages (Java, JavaScript, C++)
- Better explanations of algorithms

**For Architect's Handbook:**
- New architecture patterns
- Additional code examples
- Updated best practices
- New Q&A entries

## 📝 Content Guidelines

### Writing Style
- **Clear and concise** - Avoid jargon where possible
- **Practical examples** - Show real-world usage
- **Time/Space complexity** - Always include for algorithms
- **Up-to-date** - Use current versions and practices

### Code Examples

**DSA Guide (Python):**
```python
def two_sum(nums, target):
    seen = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in seen:
            return [seen[complement], i]
        seen[num] = i
    return []
# Time: O(n), Space: O(n)
```

**Architect's Handbook (C#):**
- Use modern C# features (C# 12+, .NET 8+)
- Include comments for complex logic
- Follow .NET naming conventions

### Formatting
- Use semantic HTML5 elements
- Follow existing CSS class conventions
- Maintain consistent indentation (4 spaces)
- Test responsive design

## 🔧 Development Setup

1. **Fork the repository**

2. **Clone your fork:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/dsa-study-guide.git
   cd dsa-study-guide
   ```

3. **Run locally:**
   ```bash
   python3 -m http.server 8080
   # Visit http://localhost:8080
   ```

4. **Make changes** to the appropriate HTML file

5. **Test locally** in multiple browsers

6. **Commit with a descriptive message:**
   ```bash
   git commit -m "Add: Binary search tree deletion problem"
   ```

7. **Push and create a Pull Request**

## ✅ Pull Request Checklist

- [ ] Content is accurate and well-researched
- [ ] Code examples are correct and tested
- [ ] Tested on multiple browsers (Chrome, Firefox, Safari)
- [ ] Mobile responsive layout preserved
- [ ] Progress tracking checkboxes work correctly
- [ ] No console errors in browser dev tools

## 📋 Commit Message Format

```
Type: Short description

Longer description if needed
```

**Types:**
- `Add:` New content or features
- `Fix:` Bug fixes or corrections
- `Update:` Improvements to existing content
- `Refactor:` Code restructuring
- `Docs:` Documentation changes

**Examples:**
- `Add: Dijkstra's algorithm problem and solution`
- `Fix: Typo in merge sort explanation`
- `Update: Improve two pointers visualization`

## 🙏 Code of Conduct

- Be respectful and constructive
- Welcome newcomers
- Focus on the content, not the person
- Assume good intentions

## 📬 Questions?

Open an issue with the `question` label or reach out to the maintainers.

---

Thank you for helping improve these study guides! 🚀

