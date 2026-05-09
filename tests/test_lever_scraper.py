from __future__ import annotations

import json
from pathlib import Path

from job_scraper_ai.config import Settings
from job_scraper_ai.scrapers.lever import LeverScraper


class FakeResponse:
    def __init__(self, json_data: object, status_code: int = 200) -> None:
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> object:
        return self._json_data


class FakeSession:
    def __init__(self, responses: dict[str, object]) -> None:
        self.responses = responses
        self.headers: dict[str, str] = {}
        self.requests: list[str] = []

    def get(self, url: str, timeout: int) -> FakeResponse:
        self.requests.append(url)
        return FakeResponse(self.responses[url])


def test_parse_posting_extracts_lever_fields() -> None:
    payload = json.loads(Path("tests/fixtures/lever_postings.json").read_text(encoding="utf-8"))[0]
    scraper = LeverScraper(settings=Settings(), company="example")

    parsed = scraper.parse_posting(payload)

    assert parsed is not None
    assert parsed.title == "Backend Engineer"
    assert parsed.company == "Example"
    assert parsed.city == "Berlin"
    assert parsed.work_type == "full_time"
    assert parsed.job_id == "abc123"
    assert parsed.date_posted is not None


def test_scrape_filters_by_keyword_and_location() -> None:
    postings = json.loads(Path("tests/fixtures/lever_postings.json").read_text(encoding="utf-8"))
    url = "https://api.lever.co/v0/postings/example?mode=json"
    session = FakeSession({url: postings})
    scraper = LeverScraper(settings=Settings(), session=session, company="example")

    jobs = scraper.scrape("support", location="Hamburg", max_pages=1)

    assert len(jobs) == 1
    assert jobs[0].title == "Support Specialist"
    assert jobs[0].city == "Hamburg"
    assert session.requests == [url]