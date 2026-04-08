from __future__ import annotations

from urllib.parse import quote_plus

from job_scraper_ai.models import JobListing
from job_scraper_ai.scrapers.base import ScraperBase


class IndeedScraper(ScraperBase):
    source_name = "indeed"

    def build_search_url(self, keyword: str, location: str | None = None) -> str:
        query = quote_plus(keyword.strip())
        if location:
            location_query = quote_plus(location.strip())
            return f"https://www.indeed.com/jobs?q={query}&l={location_query}"
        return f"https://www.indeed.com/jobs?q={query}"

    def scrape(self, keyword: str, *, location: str | None = None) -> list[JobListing]:
        _ = self.build_search_url(keyword, location)
        return []
