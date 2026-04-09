from __future__ import annotations

from pathlib import Path

from job_scraper_ai.config import Settings
from job_scraper_ai.scrapers.indeed import IndeedScraper


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.headers: dict[str, str] = {}
        self.requests: list[tuple[str, int]] = []

    def get(self, url: str, timeout: int) -> FakeResponse:
        self.requests.append((url, timeout))
        return FakeResponse(self.responses[url])


def test_build_search_url_includes_keyword_location_and_start() -> None:
    scraper = IndeedScraper(settings=Settings())

    url = scraper.build_search_url("python developer", "remote", start=10)

    assert "q=python+developer" in url
    assert "l=remote" in url
    assert "start=10" in url


def test_parse_search_results_extracts_job_cards() -> None:
    html_content = Path("tests/fixtures/indeed_page_1.html").read_text(encoding="utf-8")
    scraper = IndeedScraper(settings=Settings())

    jobs = scraper.parse_search_results(html_content)

    assert len(jobs) == 2

    first_job = jobs[0]
    assert first_job.title == "Python Developer"
    assert first_job.company == "Acme Labs"
    assert first_job.location == "Remote"
    assert str(first_job.job_url) == "https://www.indeed.com/viewjob?jk=abc123"
    assert first_job.salary_min == 100000
    assert first_job.salary_max == 140000
    assert first_job.currency == "USD"

    second_job = jobs[1]
    assert second_job.location == "New York, NY"
    assert second_job.salary_min is None
    assert second_job.salary_max is None


def test_scrape_paginates_and_applies_delay() -> None:
    page_1 = Path("tests/fixtures/indeed_page_1.html").read_text(encoding="utf-8")
    page_2 = Path("tests/fixtures/indeed_page_2.html").read_text(encoding="utf-8")
    settings = Settings(request_delay_min=2.0, request_delay_max=2.0)
    first_url = "https://www.indeed.com/jobs?q=python&start=0"
    second_url = "https://www.indeed.com/jobs?q=python&start=10"
    session = FakeSession({first_url: page_1, second_url: page_2})
    delays: list[float] = []

    def record_delay(value: float) -> None:
        delays.append(value)

    scraper = IndeedScraper(settings=settings, session=session, sleep_fn=record_delay)

    jobs = scraper.scrape("python", max_pages=2)

    assert len(jobs) == 3
    assert session.requests[0][0] == first_url
    assert session.requests[1][0] == second_url
    assert delays == [2.0]


def test_parse_search_results_skips_cards_missing_required_fields() -> None:
    html_content = """
    <html><body>
      <div class='job_seen_beacon'>
        <span class='companyName'>No title company</span>
      </div>
    </body></html>
    """
    scraper = IndeedScraper(settings=Settings())

    jobs = scraper.parse_search_results(html_content)

    assert jobs == []