from __future__ import annotations

import logging
from dataclasses import dataclass

from job_scraper_ai.config import Settings
from job_scraper_ai.models import JobListing
from job_scraper_ai.scrapers.base import ScraperBase
from job_scraper_ai.scrapers.indeed import IndeedScraper
from job_scraper_ai.scrapers.jobmensa import JobmensaScraper
from job_scraper_ai.scrapers.lever import LeverScraper


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ScrapeAttempt:
    source_name: str
    job_count: int


class SourceRouter(ScraperBase):
    source_name = "auto"

    def __init__(self, scrapers: list[ScraperBase]) -> None:
        self.scrapers = scrapers

    def scrape(
        self,
        keyword: str,
        *,
        location: str | None = None,
        max_pages: int = 1,
    ) -> list[JobListing]:
        last_error: Exception | None = None
        attempts: list[ScrapeAttempt] = []

        for scraper in self.scrapers:
            try:
                jobs = scraper.scrape(keyword, location=location, max_pages=max_pages)
            except Exception as exc:  # pragma: no cover - fallback logging path
                last_error = exc
                logger.warning("Source %s failed: %s", scraper.source_name, exc)
                continue

            attempts.append(ScrapeAttempt(source_name=scraper.source_name, job_count=len(jobs)))
            if jobs:
                return self._dedupe_jobs(jobs)

        if last_error is not None:
            logger.info("Auto fallback exhausted without results; last error: %s", last_error)

        return []

    def _dedupe_jobs(self, jobs: list[JobListing]) -> list[JobListing]:
        seen_urls: set[str] = set()
        deduped: list[JobListing] = []
        for job in jobs:
            job_url = str(job.job_url)
            if job_url in seen_urls:
                continue
            seen_urls.add(job_url)
            deduped.append(job)
        return deduped


def build_source_router(settings: Settings, *, use_browser: bool = False) -> SourceRouter:
    scrapers: list[ScraperBase] = []
    for source_name in _parse_source_order(settings.source_order):
        if source_name == "jobmensa":
            scrapers.append(JobmensaScraper(settings=settings, use_browser=use_browser))
        elif source_name == "lever":
            if settings.lever_company:
                scrapers.append(LeverScraper(settings=settings))
        elif source_name == "indeed":
            scrapers.append(IndeedScraper(settings=settings, use_browser=use_browser))
    if not scrapers:
        scrapers.append(JobmensaScraper(settings=settings, use_browser=use_browser))
    return SourceRouter(scrapers)


def _parse_source_order(source_order: str) -> list[str]:
    return [source.strip().lower() for source in source_order.split(",") if source.strip()]
