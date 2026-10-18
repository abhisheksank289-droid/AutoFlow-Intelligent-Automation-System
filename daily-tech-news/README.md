# Daily Global Tech News Scheduler

A beginner-friendly Python application that collects global technology news,
stores and categorizes articles in MongoDB, and creates a concise daily briefing.
It uses one simple Flask application and an in-process APScheduler job.

## Technologies

- Python, Flask, Requests, and APScheduler
- MongoDB and PyMongo
- Google News results via the `gnews` Python package
- Postman for trying the REST endpoints

## Requirements

- Python 3.9 or newer
- MongoDB running locally, or a MongoDB Atlas connection string
- Internet access to retrieve Google News results (no API key required)

## Installation

Open PowerShell in this folder and create a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set your MongoDB connection if it is not local. Keep `.env`
private: Git ignores it. Never put database passwords or other secrets in
Python files or commit them to GitHub. The `gnews` Python package retrieves
Google News results without a separate API key or registration.

## MongoDB setup

Start a local MongoDB server, or create a MongoDB Atlas cluster and use its
connection string in `MONGODB_URI`. The application uses database `tech_news`
with collections `news` and `daily_briefings`.

The application creates these unique indexes on startup:

- `news.url`: prevents the same article URL from being inserted twice.
- `news.title_key`: prevents exact duplicate titles after case and punctuation
  are normalized. It does not identify differently worded versions of the
  same story.
- `daily_briefings.briefing_date`: keeps one briefing document per local date.

To inspect stored data in MongoDB Compass, connect to the same URI as the app,
open database `tech_news`, and select either collection. MongoDB creates the
database and collections when the application first creates indexes or stores
documents.

## Environment variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `MONGODB_URI` | MongoDB connection string | `mongodb://localhost:27017/` |
| `MONGODB_DATABASE` | MongoDB database name | `tech_news` |
| `NEWS_SCHEDULE_HOUR` | Daily schedule hour, 0–23 | `6` |
| `NEWS_SCHEDULE_MINUTE` | Daily schedule minute, 0–59 | `0` |
| `NEWS_TIMEZONE` | IANA timezone for schedule/briefing date | `Asia/Kolkata` |

Schedule values are validated when configuration loads. `tzdata` is included
for timezone support on Windows.

## How to run

Run one collection/briefing cycle immediately (useful for a demonstration):

```powershell
python main.py --run-now
```

Start the API and keep the daily scheduler running:

```powershell
python main.py
```

The API is available at `http://127.0.0.1:5000`. Keep the process running for
the daily job to execute. Press Ctrl+C to stop it. The default schedule is
6:00 AM in `Asia/Kolkata`; update the `.env` schedule variables to change it.

## News categories

`models.py` contains editable keyword tuples for Agentic AI, Quantum Computing,
Cybersecurity, Cloud, AI, Developer Tools, Programming, Startups, and
Technology Companies. An article without a match is categorized as
`Other Technology`. More specific categories are checked first, and matching
uses whole words/phrases to reduce false positives.

## Daily briefing and scoring

Articles are ranked with a small, explainable score:

- Category points: AI, Agentic AI, Quantum Computing = 5; Cybersecurity and
  Cloud = 4; Programming, Developer Tools, Startups, Technology Companies = 3;
  Other Technology = 1.
- Recency points: published within 1 day = 3; within 3 days = 2; within 7 days
  = 1.
- Up to 2 extra points for impact terms such as `breakthrough`, `funding`,
  `breach`, or `outage`.

The selection removes repeated URLs/titles and includes at most two stories per
section and twelve stories total. The briefing summarizes provider descriptions
rather than inventing facts, then adds a category-based “why it matters,”
learning topic, and career skills.

## MongoDB document structure

Example `news` document:

```json
{
  "_id": "MongoDB ObjectId",
  "title": "Example technology headline",
  "title_key": "example technology headline",
  "description": "A short description from the news provider.",
  "source": "Example News",
  "author": null,
  "url": "https://example.com/news",
  "category": "AI",
  "published_at": "2026-10-18T03:30:00+00:00",
  "collected_at": "2026-10-18T06:00:00+00:00"
}
```

Example `daily_briefings` fields:

```json
{
  "briefing_date": "2026-10-18",
  "generated_at": "2026-10-18T00:30:00+00:00",
  "total_news": 12,
  "categories": {"AI": 3, "Cybersecurity": 2},
  "top_news": [
    {
      "title": "Example technology headline",
      "summary": "A concise provider-based summary.",
      "why_it_matters": "AI developments can change how products are built.",
      "source": "Example News",
      "url": "https://example.com/news",
      "category": "AI",
      "section": "AI",
      "score": 10
    }
  ],
  "learning_of_the_day": "Build a small Python application that calls an AI API.",
  "career_opportunity": "AI application developer - Python, APIs, and model evaluation.",
  "created_at": "2026-10-18T00:30:00+00:00"
}
```

## REST API

Use Postman with method `GET` and base URL `http://127.0.0.1:5000`.

| Endpoint | Description |
| --- | --- |
| `/health` | Check application and MongoDB availability |
| `/news` | Return up to 50 latest articles |
| `/news/<id>` | Return an article by MongoDB ObjectId |
| `/news/category/<category>` | Filter by one of the ten categories |
| `/news/search?keyword=python` | Search title, description, and category |
| `/briefings` | Return up to 30 previous briefings |
| `/briefings/<YYYY-MM-DD>` | Return a briefing for a date |

Example Postman requests:

```text
GET http://127.0.0.1:5000/health
GET http://127.0.0.1:5000/news
GET http://127.0.0.1:5000/news/64f123456789abcdef012345
GET http://127.0.0.1:5000/news/category/Quantum%20Computing
GET http://127.0.0.1:5000/news/search?keyword=python
GET http://127.0.0.1:5000/briefings
GET http://127.0.0.1:5000/briefings/2026-10-18
```

Successful list responses use a `count` and an array:

```json
{
  "count": 1,
  "news": [
    {
      "_id": "64f123456789abcdef012345",
      "title": "Example technology headline",
      "category": "AI",
      "url": "https://example.com/news"
    }
  ]
}
```

`/health` returns `200` with `{"status":"ok","database":"connected"}`. Invalid
IDs, categories, dates, or missing search terms return `400`; missing articles
and briefings return `404`; unavailable MongoDB returns `503` with a safe error
message. API responses never include database credentials or provider keys.

## Scheduler flow

At the configured local time, APScheduler calls the daily job. It fetches and
normalizes Google News results, stores non-duplicate articles, selects documents
collected in the last 24 hours, generates and upserts that day's briefing, and
prints it in the terminal. The scheduler runs in the same Python process as
Flask; stopping the process stops scheduled jobs.

## Tests

Run the test suite from this folder:

```powershell
python -m unittest discover -s tests -v
```

Tests use mocked MongoDB collections and HTTP responses; they do not require a
live database, network access, or API key.
