from __future__ import annotations

from dataclasses import dataclass
from random import Random
from re import findall
from time import sleep
from typing import Iterable
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag
from pydantic import ValidationError

from job_scraper_ai.config import Settings, get_settings
from job_scraper_ai.models import JobListing
from job_scraper_ai.scrapers.base import ScraperBase
from job_scraper_ai.scrapers.browser import PlaywrightBrowserFetcher, is_blocked_html, detect_block_reason, BrowserFetchError
from job_scraper_ai.utils.parsing import normalize_whitespace


INDEED_BASE_URL = "https://www.indeed.com"


@dataclass(slots=True)
class ScrapedCard:
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


class IndeedScraper(ScraperBase):
    source_name = "indeed"

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
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    def build_search_url(self, keyword: str, location: str | None = None, *, start: int = 0) -> str:
        query = quote_plus(keyword.strip())
        params = [f"q={query}"]
        if location:
            params.append(f"l={quote_plus(location.strip())}")
        params.append(f"start={start}")
        return f"{INDEED_BASE_URL}/jobs?{'&'.join(params)}"

    def scrape(
        self,
        keyword: str,
        *,
        location: str | None = None,
        max_pages: int = 1,
    ) -> list[JobListing]:
        jobs: list[JobListing] = []
        seen_job_urls: set[str] = set()

        for page_index in range(max_pages):
            start = page_index * 10
            search_url = self.build_search_url(keyword, location, start=start)
            html_content = self.fetch_search_page(search_url)
            page_jobs = self.parse_search_results(html_content)

            if not page_jobs:
                break

            for job in page_jobs:
                job_url = str(job.job_url)
                if job_url in seen_job_urls:
                    continue
                seen_job_urls.add(job_url)
                jobs.append(job)

            if page_index < max_pages - 1:
                self._apply_delay()

        return jobs

    def fetch_search_page(self, url: str) -> str:
        if self.use_browser:
            if self.browser_fetcher is None:
                raise RuntimeError("Browser mode is enabled but no browser fetcher is configured")
            return self.browser_fetcher.fetch_html(url)

        try:
            response = self.session.get(url, timeout=self.settings.request_timeout)
            # if site explicitly returns forbidden, treat as block
            if response.status_code == 403:
                raise RuntimeError(f"HTTP 403 Forbidden when fetching {url} — likely blocked by remote site")
            response.raise_for_status()
            html = response.text
            if is_blocked_html(html):
                reason = detect_block_reason(html) or "blocked by remote site"
                raise RuntimeError(f"Blocked page detected when fetching {url}: {reason}")
            return html
        except BrowserFetchError:
            # propagate browser-specific errors
            raise
        except Exception:
            raise

    def parse_search_results(self, html_content: str) -> list[JobListing]:
        soup = BeautifulSoup(html_content, "html.parser")
        cards = self.extract_job_cards(soup)
        parsed_jobs: list[JobListing] = []

        for card in cards:
            scraped_card = self.parse_job_card(card)
            if scraped_card is None:
                continue

            try:
                parsed_jobs.append(
                    JobListing(
                        job_id=scraped_card.job_id,
                        title=scraped_card.title,
                        company=scraped_card.company,
                        city=scraped_card.city,
                        work_type=scraped_card.work_type,
                        salary_min=scraped_card.salary_min,
                        salary_max=scraped_card.salary_max,
                        currency=scraped_card.currency,
                        job_description=scraped_card.job_description,
                        job_url=scraped_card.job_url,
                        source=self.source_name,
                    )
                )
            except ValidationError:
                continue

        return parsed_jobs

    def extract_job_cards(self, soup: BeautifulSoup) -> list[Tag]:
        job_card_xpaths = [
            "div.job_seen_beacon",
            "a.tapItem",
            "[data-jk]",
        ]
        cards: list[Tag] = []
        seen_paths: set[str] = set()

        for selector in job_card_xpaths:
            for card in soup.select(selector):
                path = card.get("data-jk") or str(id(card))
                if path in seen_paths:
                    continue
                seen_paths.add(path)
                cards.append(card)

        return cards

    def parse_job_card(self, card: Tag) -> ScrapedCard | None:
        title = self._first_text(
            card,
            [
                "h2.jobTitle span",
                "a.jcs-JobTitle",
                "a[href*='/viewjob']",
                "a[href*='/rc/clk']",
            ],
        )
        company = self._first_text(
            card,
            [
                ".companyName",
                ".companyHeading",
            ],
        )
        job_url = self._first_attribute(
            card,
            [
                "a.jcs-JobTitle",
                "a[href*='/viewjob']",
                "a[href*='/rc/clk']",
            ],
        )

        if not title or not company or not job_url:
            return None

        city = self._first_text(
            card,
            [
                ".companyLocation",
                ".resultContent .location",
            ],
            default=None,
        )
        work_type = self._detect_work_type(card)
        salary_text = self._first_text(
            card,
            [
                ".salary-snippet",
                ".salaryText",
            ],
            default=None,
        )

        salary_min, salary_max, currency = self._parse_salary(salary_text)

        return ScrapedCard(
            title=title,
            company=company,
            job_url=job_url,
            city=city,
            work_type=work_type,
            salary_min=salary_min,
            salary_max=salary_max,
            currency=currency,
            job_description=self._first_text(
                card,
                [
                    ".job-snippet",
                    ".summary",
                ],
                default=None,
            ),
            job_id=self._extract_job_id(card, job_url),
        )

    def _apply_delay(self) -> None:
        minimum = self.settings.request_delay_min
        maximum = self.settings.request_delay_max
        if maximum < minimum:
            minimum, maximum = maximum, minimum
        delay = self.random_source.uniform(minimum, maximum)
        self.sleep_fn(delay)

    def _first_text(
        self,
        element: Tag,
        selectors: Iterable[str],
        *,
        default: str | None = "",
    ) -> str | None:
        for selector in selectors:
            selected = element.select_one(selector)
            if selected is None:
                continue
            text = normalize_whitespace(selected.get_text(" ", strip=True))
            if text:
                return text
        return default

    def _first_attribute(self, element: Tag, selectors: Iterable[str]) -> str | None:
        for selector in selectors:
            selected = element.select_one(selector)
            if selected is None:
                continue
            value = str(selected.get("href", "")).strip()
            if value:
                return urljoin(INDEED_BASE_URL, value)
        return None

    def _extract_job_id(self, element: Tag, job_url: str) -> str | None:
        data_jk = element.get("data-jk")
        if data_jk:
            cleaned_data_jk = data_jk.strip()
            if cleaned_data_jk:
                return cleaned_data_jk

        parsed_url = urlparse(job_url)
        query_params = parse_qs(parsed_url.query)
        job_keys = query_params.get("jk")
        if job_keys:
            cleaned_job_key = job_keys[0].strip()
            if cleaned_job_key:
                return cleaned_job_key

        return None

    def _parse_salary(self, salary_text: str | None) -> tuple[int | None, int | None, str | None]:
        if not salary_text:
            return None, None, None

        clean_text = normalize_whitespace(
            salary_text.replace("a year", "")
            .replace("a month", "")
            .replace("a week", "")
            .replace("an hour", "")
            .replace("per year", "")
            .replace("per month", "")
            .replace("per week", "")
            .replace("per hour", "")
        )

        currency = None
        for symbol, code in (("$", "USD"), ("€", "EUR"), ("£", "GBP")):
            if symbol in clean_text:
                currency = code
                break

        numeric_values: list[int] = []
        for segment in findall(r"\d[\d,]*(?:\.\d+)?", clean_text):
            numeric_values.append(int(float(segment.replace(",", ""))))

        if not numeric_values:
            return None, None, currency

        if len(numeric_values) == 1:
            return numeric_values[0], numeric_values[0], currency

        return min(numeric_values), max(numeric_values), currency

    def _detect_work_type(self, element: Tag) -> str | None:
        card_text = normalize_whitespace(element.get_text(" ", strip=True)).lower()
        explicit_text = self._first_text(
            element,
            [
                ".jobType",
                ".workType",
            ],
            default=None,
        )
        source_text = normalize_whitespace(explicit_text).lower() if explicit_text else card_text

        work_type_patterns: tuple[tuple[str, tuple[str, ...]], ...] = (
            ("hybrid", ("hybrid",)),
            ("homeoffice", ("home office", "homeoffice", "remote", "work from home", "wfh")),
            ("vorort", ("vor ort", "onsite", "on-site", "in person", "in-person")),
        )

        for normalized_value, patterns in work_type_patterns:
            if any(pattern in source_text for pattern in patterns):
                return normalized_value

        return None
