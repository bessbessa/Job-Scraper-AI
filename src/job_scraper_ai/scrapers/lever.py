from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from random import Random
from re import findall
from time import sleep
from typing import Any

import requests
from pydantic import ValidationError

from job_scraper_ai.config import Settings, get_settings
from job_scraper_ai.models import JobListing
from job_scraper_ai.scrapers.base import ScraperBase
from job_scraper_ai.utils.parsing import normalize_whitespace


LEVER_API_URL = "https://api.lever.co/v0/postings/{company}?mode=json"


@dataclass(slots=True)
class ParsedLeverPosting:
    title: str
    company: str
    job_url: str
    city: str | None = None
    work_type: str | None = None
    job_description: str | None = None
    job_id: str | None = None
    date_posted: datetime | None = None


class LeverScraper(ScraperBase):
    source_name = "lever"

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        session: requests.Session | None = None,
        company: str | None = None,
        random_source: Random | None = None,
        sleep_fn=sleep,
    ) -> None:
        self.settings = settings or get_settings()
        self.session = session or requests.Session()
        self.company = company or self.settings.lever_company
        self.random_source = random_source or Random()
        self.sleep_fn = sleep_fn
        self.session.headers.update(
            {
                "User-Agent": self.settings.user_agent,
                "Accept": "application/json",
            }
        )

    def scrape(
        self,
        keyword: str,
        *,
        location: str | None = None,
        max_pages: int = 1,
    ) -> list[JobListing]:
        if not self.company:
            return []

        postings = self._load_postings()
        jobs: list[JobListing] = []

        for posting in postings:
            parsed_posting = self.parse_posting(posting)
            if parsed_posting is None:
                continue
            if not self._matches_query(parsed_posting, keyword=keyword, location=location):
                continue

            try:
                jobs.append(
                    JobListing(
                        job_id=parsed_posting.job_id,
                        title=parsed_posting.title,
                        company=parsed_posting.company,
                        city=parsed_posting.city,
                        work_type=parsed_posting.work_type,
                        job_description=parsed_posting.job_description,
                        job_url=parsed_posting.job_url,
                        source=self.source_name,
                        date_posted=parsed_posting.date_posted,
                    )
                )
            except ValidationError:
                continue

        return jobs[: max(1, max_pages) * 50]

    def _load_postings(self) -> list[dict[str, Any]]:
        url = LEVER_API_URL.format(company=self.company)
        response = self.session.get(url, timeout=self.settings.request_timeout)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        return []

    def parse_posting(self, posting: dict[str, Any]) -> ParsedLeverPosting | None:
        title = normalize_whitespace(str(posting.get("text", "")))
        hosted_url = normalize_whitespace(str(posting.get("hostedUrl", "")))
        if not title or not hosted_url:
            return None

        categories = posting.get("categories") if isinstance(posting.get("categories"), dict) else {}
        location = normalize_whitespace(str(categories.get("location", ""))) if isinstance(categories, dict) else None
        commitment = normalize_whitespace(str(categories.get("commitment", ""))) if isinstance(categories, dict) else None
        team = normalize_whitespace(str(categories.get("team", ""))) if isinstance(categories, dict) else None
        work_type = self._normalize_work_type(commitment or team)
        company = self._extract_company(posting)
        job_description = normalize_whitespace(str(posting.get("descriptionPlain", ""))) or None
        job_id = normalize_whitespace(str(posting.get("id", ""))) or self._slug_from_url(hosted_url)
        date_posted = self._parse_datetime(posting.get("createdAt"))

        return ParsedLeverPosting(
            title=title,
            company=company,
            job_url=hosted_url,
            city=location or None,
            work_type=work_type,
            job_description=job_description,
            job_id=job_id,
            date_posted=date_posted,
        )

    def _matches_query(self, posting: ParsedLeverPosting, *, keyword: str, location: str | None = None) -> bool:
        keyword_tokens = self._tokenize(keyword)
        location_tokens = self._tokenize(location or "")

        searchable_text = " ".join(
            part
            for part in (
                posting.title,
                posting.company,
                posting.city or "",
                posting.work_type or "",
                posting.job_description or "",
                posting.job_url,
            )
            if part
        ).lower()

        if location_tokens:
            location_text = (posting.city or "").lower() + " " + posting.job_url.lower()
            if not any(token in location_text for token in location_tokens):
                return False

        if not keyword_tokens:
            return True

        return all(token in searchable_text for token in keyword_tokens)

    def _extract_company(self, posting: dict[str, Any]) -> str:
        company_name = normalize_whitespace(self.company.replace("-", " "))
        if company_name:
            return company_name.title()
        return "Lever"

    def _normalize_work_type(self, value: str | None) -> str | None:
        if not value:
            return None
        normalized = value.lower().replace("-", "_")
        return normalized or None

    def _parse_datetime(self, value: Any) -> datetime | None:
        if value is None:
            return None
        try:
            milliseconds = int(float(str(value)))
        except (TypeError, ValueError):
            return None

        return datetime.fromtimestamp(milliseconds / 1000, tz=UTC)

    def _slug_from_url(self, url: str) -> str | None:
        slug = url.rstrip("/").split("/")[-1].strip()
        return slug or None

    def _tokenize(self, text: str) -> list[str]:
        return [token for token in findall(r"[a-z0-9]+", text.lower()) if token]
