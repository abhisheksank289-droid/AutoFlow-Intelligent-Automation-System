"""Shared article categories and keyword-based categorization."""

import re

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Agentic AI": (
        "agentic ai",
        "agentic",
        "ai agent",
        "ai agents",
        "artificial intelligence agent",
        "artificial intelligence agents",
        "autonomous agent",
    ),
    "Quantum Computing": (
        "quantum computing",
        "quantum",
        "qubit",
    ),
    "Cybersecurity": (
        "cybersecurity",
        "cyber security",
        "ransomware",
        "data breach",
        "zero-day",
        "zero day",
    ),
    "Cloud": (
        "cloud computing",
        "cloud",
        "serverless",
        "aws",
        "azure",
    ),
    "AI": (
        "artificial intelligence",
        "generative ai",
        "machine learning",
        "large language model",
        "llm",
        "neural network",
    ),
    "Developer Tools": (
        "developer tool",
        "developer tools",
        "ide",
        "code editor",
        "compiler",
        "debugger",
        "devops",
        "github copilot",
    ),
    "Programming": (
        "programming",
        "programming language",
        "software development",
        "open source",
        "python",
        "javascript",
        "typescript",
        "golang",
        "rust",
    ),
    "Startups": (
        "startup",
        "startups",
        "venture capital",
        "seed funding",
        "series a",
        "series b",
        "funding round",
        "initial public offering",
        "ipo",
        "acquisition",
        "valuation",
    ),
    "Technology Companies": (
        "apple",
        "google",
        "microsoft",
        "amazon",
        "meta",
        "nvidia",
        "openai",
        "tesla",
        "intel",
        "samsung",
        "qualcomm",
        "oracle",
        "ibm",
    ),
}

CATEGORIES = tuple(CATEGORY_KEYWORDS) + ("Other Technology",)


def normalize_title_key(title: str) -> str:
    """Create a case- and punctuation-insensitive key for exact title deduplication."""
    return " ".join(re.findall(r"\w+", title.casefold()))


def categorize_article(title: str, description: str = "") -> str:
    """Choose the first matching category using title and description keywords."""
    article_text = f"{title} {description}".casefold()

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(
            re.search(rf"\b{re.escape(keyword)}\b", article_text)
            for keyword in keywords
        ):
            return category

    return "Other Technology"
