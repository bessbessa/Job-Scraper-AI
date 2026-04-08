from pathlib import Path

from job_scraper_ai.models import JobListing
from job_scraper_ai.services import Exporter


def test_exporter_writes_csv(tmp_path: Path) -> None:
    jobs = [
        JobListing(
            title="Python Developer",
            company="Acme",
            location="Remote",
            job_url="https://example.com/jobs/123",
            source="indeed",
        )
    ]

    output_path = tmp_path / "jobs.csv"
    result_path = Exporter().export_csv(jobs, output_path)

    assert result_path == output_path
    content = output_path.read_text(encoding="utf-8")
    assert "Python Developer" in content
    assert "job_id" in content.splitlines()[0]
