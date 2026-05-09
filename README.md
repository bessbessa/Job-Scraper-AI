# Job-Scraper-AI

Job Scraper in Q2 2026.

## Milestone Roadmap

### Weeks 1-2: Foundation and first scraper
Establish the Python project structure, dependency management, and configuration baseline. In parallel, define the job listing data model, implement the first Indeed scraper, and add the initial unit test coverage needed to validate the core pipeline.

Chosen stack for Week 1-2: requests(fetching), beautifulsoup4(parsing), pydantic, python-dotenv, pytest, pytest-cov, tenacity.

### Weeks 3-4: Matching and filtering
Add the job matching layer, introduce location and seniority filters, and validate the classifier logic with tests.

### Weeks 5-6: Profile-driven generation
Parse resumes, integrate LLM-based generation, build the personalization engine, and support cover letter creation.

### Weeks 7-8: Tracking and workflow management
Connect Notion, log applications, generate weekly summaries, and test the tracking workflow.

### Weeks 9-10: User experience and automation
Add email confirmations, a browsing UI, daily scraping automation, and application automation where feasible.

### Weeks 11-12: Hardening and release readiness
Strengthen logging and error handling, document setup and API keys, optimize performance, and prepare the project for deployment.

## Week 1-2 Priorities

For the first sprint, the project should focus on the smallest set of decisions that unlock everything else:

1. Define the repository structure and Python environment.
2. Select and pin the core dependencies.
3. Create the shared job listing schema.
4. Implement the first Indeed scraper against the schema.
5. Add tests for parsing, exports, and failure cases.
6. Document the expected local setup and run commands.

## Week 1-2 Remaining Work

Tasks 2-7 are still the real sprint work.
That means the scraper fetch, HTML parsing, job-card extraction, field mapping, pagination, rate limiting, and fixture-based tests still need to be finished.


## Runtime Model

This project should be built CLI-first.

- Run locally from your machine during development.
- Move to a VPS, container host, or scheduled cloud environment when automation is ready.
- Do not rely on a laptop staying open for scheduled scraping.

## Installation And Usage

### Installation

1. Clone the repository.
2. Create and activate a Python virtual environment.
3. Install the project dependencies.
4. Copy `.env.example` to `.env` and fill in any required values.

Example:

```bash
git clone https://github.com/bessbessa/Job-Scraper-AI.git
cd Job-Scraper-AI
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
```

### Usage

Run the scraper from the command line and write output to the data folder.

```bash
job-scraper-ai doctor
job-scraper-ai scrape --site auto --keyword "it support" --location Dortmund --browser
job-scraper-ai scrape --site indeed --keyword python
job-scraper-ai scrape --site indeed --keyword python --browser
job-scraper-ai scrape --site jobmensa --keyword consultant --location Aachen
job-scraper-ai scrape --site lever --keyword engineer --location Berlin
```

Example input mapping: "scrape me all jobs in software dev in Dortmund" becomes `job-scraper-ai scrape --site indeed --keyword "software dev" --location Dortmund`.

Browser mode example: add `--browser` when you want the scraper to render the page with Playwright instead of using plain HTTP requests.

Supported sources currently include `indeed`, `jobmensa`, and `lever`. Indeed still depends on site accessibility, Jobmensa uses public sitemap and JSON-LD job pages, and Lever uses the public postings API.
Auto mode tries sources in the configured `SOURCE_ORDER` until one returns jobs. Lever is supported through the public postings API and requires `LEVER_COMPANY` in `.env`.

Expected behavior:

- The scraper reads config from environment variables.
- Results are validated before export.
- Output is saved to `data/output/` or a similar configured path.
- Tests run without hitting live job boards.

## Today's Changes Log

- Switched the parser stack to BeautifulSoup for portability.
- Added browser-based fetch support for blocked pages.
- Added blocked-page detection and clearer failure reporting.
- Added `jobmensa` as a sitemap-plus-JSON-LD source.
- Added `lever` as a public postings API source.
- Added `auto` source routing with fallback across configured scrapers.
- Updated tests and fixtures for the new source model and browser fallback.

## Next Implementation Log

- Improve logging, retries, backoff, and telemetry across all sources.
- Add optional proxy rotation support for the browser-backed path.
- Add optional fingerprint and stealth tuning for Playwright where needed.
- Define a CAPTCHA handling policy before any heavier anti-bot work.
- Add one more compliant source adapter, such as Greenhouse or Workable.
