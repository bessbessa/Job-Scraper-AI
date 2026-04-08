from __future__ import annotations

from abc import ABC, abstractmethod

from job_scraper_ai.models import JobListing


class ScraperBase(ABC):
    source_name: str

    @abstractmethod
    def scrape(self, keyword: str, *, location: str | None = None) -> list[JobListing]:
        raise NotImplementedError
