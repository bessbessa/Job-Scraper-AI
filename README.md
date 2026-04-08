# Job-Scraper-AI

Job Scraper in Q2 2026.

## Milestone Roadmap

### Weeks 1-2: Foundation and first scraper
Establish the Python project structure, dependency management, and configuration baseline. In parallel, define the job listing data model, implement the first Indeed scraper, and add the initial unit test coverage needed to validate the core pipeline.

Chosen stack for Week 1-2: requests, lxml, pydantic, python-dotenv, pytest, pytest-cov, tenacity.

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

## Recommended Deliverables For Week 1-2

- A working virtual environment and reproducible dependency install.
- A clear `src/`, `tests/`, and `data/` layout.
- A validated `JobListing` model that becomes the contract for later features.
- An Indeed scraper that can extract structured listings.
- A test suite that proves the scraper and model behave correctly without live network dependency.
- A short setup guide so the project is easy to run and review.

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
job-scraper-ai scrape --site indeed --keyword python
```

Expected behavior:

- The scraper reads config from environment variables.
- Results are validated before export.
- Output is saved to `data/output/` or a similar configured path.
- Tests run without hitting live job boards.
