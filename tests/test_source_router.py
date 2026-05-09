from __future__ import annotations

from job_scraper_ai.models import JobListing
from job_scraper_ai.scrapers.base import ScraperBase
from job_scraper_ai.scrapers.router import SourceRouter


class DummyScraper(ScraperBase):
    def __init__(self, source_name: str, result: list[JobListing] | None = None, error: Exception | None = None) -> None:
        self.source_name = source_name
        self.result = result or []
        self.error = error

    def scrape(self, keyword: str, *, location: str | None = None, max_pages: int = 1) -> list[JobListing]:
        if self.error is not None:
            raise self.error
        return self.result


def test_source_router_falls_back_to_next_source() -> None:
    winning_job = JobListing(
        job_id="abc",
        title="Support Specialist",
        company="Example",
        city="Hamburg",
        job_url="https://jobs.example.com/abc",
        source="lever",
    )
    router = SourceRouter(
        [
            DummyScraper("jobmensa", error=RuntimeError("blocked")),
            DummyScraper("lever", result=[winning_job]),
        ]
    )

    jobs = router.scrape("support", location="Hamburg", max_pages=1)

    assert jobs == [winning_job]
