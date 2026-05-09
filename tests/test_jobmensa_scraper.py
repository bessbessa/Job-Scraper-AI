from __future__ import annotations

from pathlib import Path

from job_scraper_ai.config import Settings
from job_scraper_ai.scrapers.jobmensa import JobmensaScraper


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code
        self.content = text.encode("utf-8")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.headers: dict[str, str] = {}
        self.requests: list[str] = []

    def get(self, url: str, timeout: int) -> FakeResponse:
        self.requests.append(url)
        return FakeResponse(self.responses[url])


class FakeBrowserFetcher:
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.requests: list[str] = []

    def fetch_html(self, url: str) -> str:
        self.requests.append(url)
        return self.responses[url]


def test_parse_job_page_extracts_json_ld_fields() -> None:
    html_content = Path("tests/fixtures/jobmensa_job_detail_1.html").read_text(encoding="utf-8")
    scraper = JobmensaScraper(settings=Settings())

    parsed_job = scraper.parse_job_page(html_content, "https://www.jobmensa.de/jobs/ex/associate-consultant-m-w-d-aachen-4f153105d948cbd5")

    assert parsed_job is not None
    assert parsed_job.title == "Associate Consultant (m/w/d)"
    assert parsed_job.company == "jobvalley"
    assert parsed_job.city == "Aachen"
    assert parsed_job.work_type == "full_time"
    assert parsed_job.salary_min == 15
    assert parsed_job.salary_max == 20
    assert parsed_job.currency == "EUR"
    assert parsed_job.job_id == "4f153105d948cbd5"
    assert parsed_job.date_posted is not None


def test_scrape_uses_sitemap_and_filters_by_keyword_and_location() -> None:
    sitemap_xml = Path("tests/fixtures/jobmensa_sitemap.xml").read_text(encoding="utf-8")
    job_1 = Path("tests/fixtures/jobmensa_job_detail_1.html").read_text(encoding="utf-8")
    job_2 = Path("tests/fixtures/jobmensa_job_detail_2.html").read_text(encoding="utf-8")
    sitemap_url = "https://www.jobmensa.de/sitemaps/jobsearch_jobs.xml.gz"
    first_job_url = "https://www.jobmensa.de/jobs/ex/associate-consultant-m-w-d-aachen-4f153105d948cbd5"
    second_job_url = "https://www.jobmensa.de/jobs/ex/backend-engineer-m-w-d-berlin-abcdef1234567890"
    session = FakeSession(
        {
            sitemap_url: sitemap_xml,
            first_job_url: job_1,
            second_job_url: job_2,
        }
    )

    delays: list[float] = []

    def record_delay(value: float) -> None:
        delays.append(value)

    scraper = JobmensaScraper(settings=Settings(request_delay_min=1.5, request_delay_max=1.5), session=session, sleep_fn=record_delay)

    jobs = scraper.scrape("associate consultant", location="Aachen", max_pages=1)

    assert len(jobs) == 1
    assert jobs[0].title == "Associate Consultant (m/w/d)"
    assert jobs[0].city == "Aachen"
    assert session.requests[0] == sitemap_url
    assert session.requests[1] == first_job_url
    assert delays == []


def test_scrape_skips_nonmatching_urls() -> None:
    sitemap_xml = Path("tests/fixtures/jobmensa_sitemap.xml").read_text(encoding="utf-8")
    first_job_url = "https://www.jobmensa.de/jobs/ex/associate-consultant-m-w-d-aachen-4f153105d948cbd5"
    second_job_url = "https://www.jobmensa.de/jobs/ex/backend-engineer-m-w-d-berlin-abcdef1234567890"
    third_job_url = "https://www.jobmensa.de/jobs/ex/it-support-specialist-m-w-d-dortmund-001"
    session = FakeSession(
        {
            "https://www.jobmensa.de/sitemaps/jobsearch_jobs.xml.gz": sitemap_xml,
            first_job_url: Path("tests/fixtures/jobmensa_job_detail_1.html").read_text(encoding="utf-8"),
            second_job_url: Path("tests/fixtures/jobmensa_job_detail_2.html").read_text(encoding="utf-8"),
            third_job_url: Path("tests/fixtures/jobmensa_job_detail_dortmund_it_support.html").read_text(encoding="utf-8"),
        }
    )
    scraper = JobmensaScraper(settings=Settings(), session=session)

    jobs = scraper.scrape("nurse", location="Hamburg", max_pages=1)

    assert jobs == []


def test_scrape_matches_it_support_in_dortmund_by_page_content() -> None:
    sitemap_xml = Path("tests/fixtures/jobmensa_sitemap.xml").read_text(encoding="utf-8")
    it_support_html = Path("tests/fixtures/jobmensa_job_detail_dortmund_it_support.html").read_text(encoding="utf-8")
    first_sitemap_url = "https://www.jobmensa.de/jobs/ex/associate-consultant-m-w-d-aachen-4f153105d948cbd5"
    first_job_url = "https://www.jobmensa.de/jobs/ex/it-support-specialist-m-w-d-dortmund-001"
    second_job_url = "https://www.jobmensa.de/jobs/ex/backend-engineer-m-w-d-berlin-abcdef1234567890"
    session = FakeSession(
        {
            "https://www.jobmensa.de/sitemaps/jobsearch_jobs.xml.gz": sitemap_xml,
            first_sitemap_url: Path("tests/fixtures/jobmensa_job_detail_1.html").read_text(encoding="utf-8"),
            first_job_url: it_support_html,
            second_job_url: Path("tests/fixtures/jobmensa_job_detail_2.html").read_text(encoding="utf-8"),
        }
    )

    scraper = JobmensaScraper(settings=Settings(), session=session)

    jobs = scraper.scrape("it support", location="Dortmund", max_pages=1)

    assert len(jobs) == 1
    assert jobs[0].title == "IT Support Specialist (m/w/d)"
    assert jobs[0].city == "Dortmund"


def test_fetch_job_page_falls_back_to_browser_when_requests_hits_block() -> None:
    blocked_url = "https://www.jobmensa.de/jobs/ex/blocked-example"
    browser_html = Path("tests/fixtures/jobmensa_job_detail_dortmund_it_support.html").read_text(encoding="utf-8")
    session = FakeSession({blocked_url: "<html><title>Blocked</title><body>Cloudflare challenge</body></html>"})
    browser_fetcher = FakeBrowserFetcher({blocked_url: browser_html})
    scraper = JobmensaScraper(settings=Settings(), session=session, browser_fetcher=browser_fetcher)

    html_content = scraper.fetch_job_page(blocked_url)

    assert "IT Support Specialist" in html_content
    assert browser_fetcher.requests == [blocked_url]