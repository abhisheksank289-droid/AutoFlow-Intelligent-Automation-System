"""Select important news and create a concise daily briefing."""

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from pymongo.collection import Collection

from config import NEWS_TIMEZONE
from models import CATEGORIES, normalize_title_key

SECTION_CATEGORIES: dict[str, tuple[str, ...]] = {
    "AI": ("AI",),
    "AGENTIC AI": ("Agentic AI",),
    "QUANTUM COMPUTING": ("Quantum Computing",),
    "CLOUD & SOFTWARE": ("Cloud", "Programming", "Developer Tools"),
    "CYBERSECURITY": ("Cybersecurity",),
    "TECHNOLOGY BUSINESS": ("Startups", "Technology Companies", "Other Technology"),
}

CATEGORY_SCORES = {
    "Agentic AI": 5,
    "AI": 5,
    "Quantum Computing": 5,
    "Cybersecurity": 4,
    "Cloud": 4,
    "Programming": 3,
    "Developer Tools": 3,
    "Startups": 3,
    "Technology Companies": 3,
    "Other Technology": 1,
}

IMPACT_KEYWORDS = (
    "launch",
    "breakthrough",
    "funding",
    "breach",
    "outage",
    "acquisition",
    "regulation",
    "critical",
    "record",
    "announced",
)

MAX_BRIEFING_ARTICLES = 12
MAX_ARTICLES_PER_SECTION = 2

WHY_IT_MATTERS = {
    "AI": "AI developments can change how people and organizations build and use products.",
    "Agentic AI": (
        "Agentic systems can take actions across tools, making reliability and "
        "human oversight important."
    ),
    "Quantum Computing": (
        "Quantum progress may affect scientific research and long-term "
        "encryption planning."
    ),
    "Cloud": (
        "Cloud changes can affect application cost, reliability, and deployment "
        "choices."
    ),
    "Cybersecurity": (
        "Security developments can change how organizations protect systems "
        "and data."
    ),
    "Programming": (
        "Programming changes can affect how software teams build and maintain "
        "applications."
    ),
    "Developer Tools": (
        "Developer tools can affect software quality and day-to-day team "
        "productivity."
    ),
    "Startups": (
        "Startup developments can influence competition, investment, and new "
        "product ideas."
    ),
    "Technology Companies": (
        "Major company decisions can influence products, competition, and the "
        "technology ecosystem."
    ),
    "Other Technology": (
        "This development adds context to the wider technology landscape."
    ),
}

LEARNING_TOPICS = {
    "AI": "Build a small Python application that calls an AI API and checks its output.",
    "Agentic AI": (
        "Learn how an AI agent calls tools, and why each action needs clear "
        "permissions."
    ),
    "Quantum Computing": (
        "Learn the basics of qubits and quantum gates using a beginner simulator."
    ),
    "Cloud": "Deploy a small REST API and learn how its configuration is managed.",
    "Cybersecurity": (
        "Practice basic threat modeling for a web API and its stored data."
    ),
    "Programming": "Write a small Python program and add a few unit tests.",
    "Developer Tools": (
        "Practice using the VS Code debugger, formatter, and test runner."
    ),
    "Startups": "Study how a technology startup validates a product idea.",
    "Technology Companies": (
        "Compare how technology companies describe a product launch and its "
        "target users."
    ),
    "Other Technology": "Explore how a REST API returns technology data as JSON.",
}

CAREER_SKILLS = {
    "AI": "AI application developer - Python, APIs, and model evaluation.",
    "Agentic AI": (
        "AI agent developer - Python, tool integration, testing, and safe "
        "permission design."
    ),
    "Quantum Computing": (
        "Quantum software learner - Python, linear algebra, and quantum "
        "simulators."
    ),
    "Cloud": "Cloud backend developer - REST APIs, deployment, and cloud fundamentals.",
    "Cybersecurity": (
        "Security analyst - networking, secure coding, and incident analysis."
    ),
    "Programming": "Backend developer - Python, Git, APIs, and automated testing.",
    "Developer Tools": (
        "Developer productivity engineer - debugging, CI, and developer tools."
    ),
    "Startups": (
        "Technology business analyst - product research, data analysis, and "
        "market understanding."
    ),
    "Technology Companies": (
        "Technology product analyst - product research, communication, and "
        "business analysis."
    ),
    "Other Technology": (
        "Junior technology analyst - research, clear writing, and data literacy."
    ),
}


def _as_utc(value: datetime) -> datetime:
    """Treat naive datetimes as UTC and convert aware datetimes to UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def score_article(article: dict[str, Any], now: Optional[datetime] = None) -> int:
    """Score a story by topic priority, recency, and impact-related keywords."""
    current_time = _as_utc(now or datetime.now(timezone.utc))
    category = article.get("category", "Other Technology")
    score = CATEGORY_SCORES.get(category, 1)

    published_at = article.get("published_at")
    if isinstance(published_at, datetime):
        age = current_time - _as_utc(published_at)
        if timedelta(0) <= age <= timedelta(days=1):
            score += 3
        elif timedelta(days=1) < age <= timedelta(days=3):
            score += 2
        elif timedelta(days=3) < age <= timedelta(days=7):
            score += 1

    article_text = (
        f"{article.get('title', '')} {article.get('description', '')}".casefold()
    )
    impact_matches = sum(
        1 for keyword in IMPACT_KEYWORDS if keyword in article_text
    )
    score += min(impact_matches, 2)
    return score


def _summary_for(article: dict[str, Any]) -> str:
    """Use up to two provider description sentences without inventing details."""
    description = article.get("description", "").strip()
    category = article.get("category", "Other Technology")

    if not description:
        return (
            f"{article['title']}. The source did not provide a description; "
            "open the article for details."
        )

    sentences = re.split(r"(?<=[.!?])\s+", description)
    summary = " ".join(sentences[:2])
    if len(sentences) == 1:
        summary += f" This story relates to {category.lower()}."
    return summary


def _section_for(category: str) -> str:
    for section, section_categories in SECTION_CATEGORIES.items():
        if category in section_categories:
            return section
    return "TECHNOLOGY BUSINESS"


def select_top_news(
    articles: list[dict[str, Any]],
    now: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    """Select high-scoring, recent stories while limiting repeated coverage."""
    current_time = _as_utc(now or datetime.now(timezone.utc))
    candidates = []
    seen_urls = set()
    seen_titles = set()

    for article in articles:
        url = article.get("url", "")
        title = article.get("title", "")
        title_key = article.get("title_key") or normalize_title_key(title)
        if url and url in seen_urls:
            continue
        if title_key and title_key in seen_titles:
            continue

        if url:
            seen_urls.add(url)
        if title_key:
            seen_titles.add(title_key)

        published_at = article.get("published_at")
        published_timestamp = (
            _as_utc(published_at).timestamp()
            if isinstance(published_at, datetime)
            else 0
        )
        candidates.append(
            (
                score_article(article, current_time),
                published_timestamp,
                title.casefold(),
                article,
            )
        )

    candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)

    selected = []
    section_counts = {section: 0 for section in SECTION_CATEGORIES}
    for score, _, _, article in candidates:
        if len(selected) >= MAX_BRIEFING_ARTICLES:
            break

        section = _section_for(article.get("category", "Other Technology"))
        if section_counts[section] >= MAX_ARTICLES_PER_SECTION:
            continue

        selected.append(
            {
                "title": article["title"],
                "summary": _summary_for(article),
                "why_it_matters": WHY_IT_MATTERS.get(
                    article.get("category"),
                    WHY_IT_MATTERS["Other Technology"],
                ),
                "source": article.get("source") or "Unknown source",
                "url": article.get("url", ""),
                "category": article.get("category", "Other Technology"),
                "section": section,
                "score": score,
            }
        )
        section_counts[section] += 1

    return selected


def generate_daily_briefing(
    articles: list[dict[str, Any]],
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Build a dated briefing document from collected articles."""
    generated_at = _as_utc(now or datetime.now(timezone.utc))
    briefing_date = generated_at.astimezone(ZoneInfo(NEWS_TIMEZONE)).date().isoformat()
    top_news = select_top_news(articles, generated_at)

    categories = {category: 0 for category in CATEGORIES}
    for article in articles:
        category = article.get("category", "Other Technology")
        if category in categories:
            categories[category] += 1
        else:
            categories["Other Technology"] += 1

    if top_news:
        lead_category = top_news[0]["category"]
    else:
        lead_category = "Other Technology"

    return {
        "briefing_date": briefing_date,
        "generated_at": generated_at,
        "total_news": len(articles),
        "categories": categories,
        "top_news": top_news,
        "learning_of_the_day": LEARNING_TOPICS[lead_category],
        "career_opportunity": CAREER_SKILLS[lead_category],
        "created_at": generated_at,
    }


def save_daily_briefing(
    briefing: dict[str, Any],
    briefing_collection: Collection,
) -> None:
    """Insert or refresh one briefing for its date while retaining created_at."""
    briefing_data = {
        key: value
        for key, value in briefing.items()
        if key not in ("briefing_date", "created_at")
    }
    briefing_collection.update_one(
        {"briefing_date": briefing["briefing_date"]},
        {
            "$set": briefing_data,
            "$setOnInsert": {"created_at": briefing["created_at"]},
        },
        upsert=True,
    )


def format_briefing(briefing: dict[str, Any]) -> str:
    """Return a readable terminal version of the briefing."""
    lines = [
        "DAILY GLOBAL TECH BRIEFING",
        f"Date: {briefing['briefing_date']}",
        "",
    ]

    for number, section in enumerate(SECTION_CATEGORIES, start=1):
        lines.append(f"{number}. {section}")
        section_articles = [
            article for article in briefing["top_news"] if article["section"] == section
        ]
        if not section_articles:
            lines.append("- No significant articles selected today.")

        for article in section_articles:
            lines.extend(
                [
                    f"- {article['title']}",
                    f"  Summary: {article['summary']}",
                    f"  Why it matters: {article['why_it_matters']}",
                    f"  Source: {article['source']}",
                ]
            )
        lines.append("")

    lines.extend(
        [
            "7. LEARNING OF THE DAY",
            f"- {briefing['learning_of_the_day']}",
            "",
            "8. CAREER OPPORTUNITY",
            f"- {briefing['career_opportunity']}",
        ]
    )
    return "\n".join(lines)
