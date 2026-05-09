from __future__ import annotations

import gzip
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from random import Random
from re import findall
from time import sleep
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from pydantic import ValidationError

from job_scraper_ai.config import Settings, get_settings
from job_scraper_ai.models import JobListing
from job_scraper_ai.scrapers.base import ScraperBase
from job_scraper_ai.scrapers.browser import BrowserFetchError, PlaywrightBrowserFetcher, detect_block_reason, is_blocked_html
from job_scraper_ai.utils.parsing import normalize_whitespace


JOBMENSA_BASE_URL = "https://www.jobmensa.de"
JOBMENSA_SITEMAP_URL = f"{JOBMENSA_BASE_URL}/sitemaps/jobsearch_jobs.xml.gz"


@dataclass(slots=True)
class ParsedJobMensaPosting:
    title: str
    company: str
    job_url: str
    city: str | None = None
    work_type: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    job_description: str | None = None
    job_id: str | None = None
    date_posted: datetime | None = None


class JobmensaScraper(ScraperBase):
    source_name = "jobmensa"

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        session: requests.Session | None = None,
        use_browser: bool = False,
        browser_fetcher: PlaywrightBrowserFetcher | None = None,
        random_source: Random | None = None,
        sleep_fn=sleep,
    ) -> None:
        self.settings = settings or get_settings()
        self.session = session or requests.Session()
        self.use_browser = use_browser
        self.browser_fetcher = browser_fetcher or (PlaywrightBrowserFetcher() if use_browser else None)
        self.random_source = random_source or Random()
        self.sleep_fn = sleep_fn
        self.session.headers.update(
            {
                "User-Agent": self.settings.user_agent,
                "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )

    def scrape(
        self,
        keyword: str,
        *,
        location: str | None = None,
        max_pages: int = 1,
    ) -> list[JobListing]:
        candidate_urls = self._filtered_job_urls(keyword=keyword, location=location)
        if not candidate_urls:
            return []

        limit = max(1, max_pages) * 10
        jobs: list[JobListing] = []

        for index, job_url in enumerate(candidate_urls[:limit]):
            html_content = self.fetch_job_page(job_url)
            parsed_job = self.parse_job_page(html_content, job_url)
            if parsed_job is None:
                continue

            if not self._matches_query(parsed_job, keyword=keyword, location=location):
                continue

            try:
                jobs.append(
                    JobListing(
                        job_id=parsed_job.job_id,
                        title=parsed_job.title,
                        company=parsed_job.company,
                        city=parsed_job.city,
                        work_type=parsed_job.work_type,
                        salary_min=parsed_job.salary_min,
                        salary_max=parsed_job.salary_max,
                        currency=parsed_job.currency,
                        job_description=parsed_job.job_description,
                        job_url=parsed_job.job_url,
                        source=self.source_name,
                        date_posted=parsed_job.date_posted,
                    )
                )
            except ValidationError:
                continue

            if index < min(len(candidate_urls), limit) - 1:
                self._apply_delay()

        return jobs

    def fetch_job_page(self, url: str) -> str:
        if self.use_browser:
            if self.browser_fetcher is None:
                raise RuntimeError("Browser mode is enabled but no browser fetcher is configured")
            return self.browser_fetcher.fetch_html(url)

        try:
            response = self.session.get(url, timeout=self.settings.request_timeout)
            if response.status_code == 403:
                if self.browser_fetcher is not None:
                    return self.browser_fetcher.fetch_html(url)
                raise RuntimeError(f"HTTP 403 Forbidden when fetching {url} — likely blocked by remote site")
            response.raise_for_status()
            html_content = response.text
            if is_blocked_html(html_content):
                reason = detect_block_reason(html_content) or "blocked by remote site"
                if self.browser_fetcher is not None:
                    return self.browser_fetcher.fetch_html(url)
                raise RuntimeError(f"Blocked page detected when fetching {url}: {reason}")
            return html_content
        except BrowserFetchError:
            raise

    def _filtered_job_urls(self, *, keyword: str, location: str | None = None) -> list[str]:
        keyword_tokens = self._tokenize(keyword)
        location_tokens = self._tokenize(location or "")
        urls = self._load_job_urls()

        filtered_urls: list[str] = []
        for job_url in urls:
            slug = job_url.lower()
            if location_tokens and not all(token in slug for token in location_tokens):
                continue
            if keyword_tokens and not any(token in slug for token in keyword_tokens):
                continue
            filtered_urls.append(job_url)

        return filtered_urls if filtered_urls else urls

    def _load_job_urls(self) -> list[str]:
        response = self.session.get(JOBMENSA_SITEMAP_URL, timeout=self.settings.request_timeout)
        response.raise_for_status()

        raw_bytes = getattr(response, "content", b"") or b""
        xml_text: str
        if raw_bytes.startswith(b"\x1f\x8b"):
            xml_text = gzip.decompress(raw_bytes).decode("utf-8", errors="replace")
        else:
            try:
                xml_text = raw_bytes.decode("utf-8")
            except AttributeError:
                xml_text = response.text
            except UnicodeDecodeError:
                xml_text = response.text

        return self._parse_sitemap_urls(xml_text)

    def _parse_sitemap_urls(self, xml_text: str) -> list[str]:
        root = ET.fromstring(xml_text)
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [element.text.strip() for element in root.findall("sm:url/sm:loc", namespace) if element.text]
        return [url for url in urls if url and url != JOBMENSA_BASE_URL]

    def parse_job_page(self, html_content: str, job_url: str) -> ParsedJobMensaPosting | None:
        soup = BeautifulSoup(html_content, "html.parser")
        payload = self._extract_job_posting_payload(soup)
        if payload is None:
            return None

        title = normalize_whitespace(str(payload.get("title", "")))
        if not title:
            return None

        company = self._extract_company(payload) or "Jobmensa"
        city = self._extract_city(payload)
        work_type = self._normalize_work_type(payload.get("employmentType"))
        salary_min, salary_max, currency = self._extract_salary(payload.get("baseSalary"))
        description = self._extract_description(payload.get("description"))
        job_id = self._extract_job_id(payload, job_url)
        date_posted = self._parse_datetime(payload.get("datePosted"))

        return ParsedJobMensaPosting(
            title=title,
            company=company,
            job_url=job_url,
            city=city,
            work_type=work_type,
            salary_min=salary_min,
            salary_max=salary_max,
            currency=currency,
            job_description=description,
            job_id=job_id,
            date_posted=date_posted,
        )

    def _extract_job_posting_payload(self, soup: BeautifulSoup) -> dict[str, Any] | None:
        for script in soup.select('script[type="application/ld+json"]'):
            raw_text = script.get_text(" ", strip=True)
            if not raw_text:
                continue
            try:
                payload = json.loads(raw_text)
            except json.JSONDecodeError:
                continue

            for candidate in self._iter_json_ld_candidates(payload):
                if self._is_job_posting(candidate):
                    return candidate

        return None

    def _iter_json_ld_candidates(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            return [payload]
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        return []

    def _is_job_posting(self, payload: dict[str, Any]) -> bool:
        payload_type = payload.get("@type")
        if isinstance(payload_type, str):
            return payload_type.lower() == "jobposting"
        if isinstance(payload_type, list):
            return any(str(item).lower() == "jobposting" for item in payload_type)
        return False

    def _extract_company(self, payload: dict[str, Any]) -> str | None:
        hiring_organization = payload.get("hiringOrganization")
        if isinstance(hiring_organization, dict):
            company_name = normalize_whitespace(str(hiring_organization.get("name", "")))
            if company_name:
                return company_name
        return None

    def _extract_city(self, payload: dict[str, Any]) -> str | None:
        job_location = payload.get("jobLocation")
        locations = job_location if isinstance(job_location, list) else [job_location]

        for location in locations:
            if not isinstance(location, dict):
                continue
            address = location.get("address")
            if not isinstance(address, dict):
                continue
            city = normalize_whitespace(str(address.get("addressLocality", "")))
            if city:
                return city
        return None

    def _normalize_work_type(self, employment_type: Any) -> str | None:
        if isinstance(employment_type, str):
            normalized = employment_type.strip().lower().replace("-", "_")
            return normalized or None
        if isinstance(employment_type, list):
            values = [str(item).strip().lower().replace("-", "_") for item in employment_type if str(item).strip()]
            return ", ".join(values) if values else None
        return None

    def _extract_salary(self, base_salary: Any) -> tuple[int | None, int | None, str | None]:
        if not isinstance(base_salary, dict):
            return None, None, None

        value = base_salary.get("value")
        if isinstance(value, dict):
            min_value = self._coerce_int(value.get("minValue"))
            max_value = self._coerce_int(value.get("maxValue"))
            currency = normalize_whitespace(str(value.get("currency", ""))) or None
            return min_value, max_value, currency

        min_value = self._coerce_int(base_salary.get("minValue"))
        max_value = self._coerce_int(base_salary.get("maxValue"))
        currency = normalize_whitespace(str(base_salary.get("currency", ""))) or None
        return min_value, max_value, currency

    def _extract_description(self, description: Any) -> str | None:
        if not description:
            return None

        if isinstance(description, str):
            stripped = normalize_whitespace(BeautifulSoup(description, "html.parser").get_text(" ", strip=True))
            return stripped or None

        return normalize_whitespace(str(description)) or None

    def _extract_job_id(self, payload: dict[str, Any], job_url: str) -> str | None:
        identifier = payload.get("identifier")
        if isinstance(identifier, dict):
            identifier_value = normalize_whitespace(str(identifier.get("value", "")))
            if identifier_value:
                return identifier_value

        slug = urlparse(job_url).path.rstrip("/").split("/")[-1]
        return slug or None

    def _parse_datetime(self, value: Any) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None

        normalized_value = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized_value)
        except ValueError:
            return None

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed

    def _coerce_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            numeric_text = normalize_whitespace(str(value)).replace(",", "")
            if not numeric_text:
                return None
            return int(float(numeric_text))
        except (TypeError, ValueError):
            return None

    def _tokenize(self, text: str) -> list[str]:
        return [token for token in findall(r"[a-z0-9]+", text.lower()) if token]

    def _matches_query(self, job: ParsedJobMensaPosting, *, keyword: str, location: str | None = None) -> bool:
        keyword_tokens = self._tokenize(keyword)
        location_tokens = self._tokenize(location or "")

        searchable_text = " ".join(
            part
            for part in (
                job.title,
                job.company,
                job.city or "",
                job.job_description or "",
                job.job_url,
            )
            if part
        ).lower()

        if location_tokens:
            location_text = (job.city or "").lower() + " " + job.job_url.lower()
            if not any(token in location_text for token in location_tokens):
                return False

        if not keyword_tokens:
            return True

        return all(token in searchable_text for token in keyword_tokens)

    def _apply_delay(self) -> None:
        minimum = self.settings.request_delay_min
        maximum = self.settings.request_delay_max
        if maximum < minimum:
            minimum, maximum = maximum, minimum
        delay = self.random_source.uniform(minimum, maximum)
        self.sleep_fn(delay)