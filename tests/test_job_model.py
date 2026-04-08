from datetime import UTC, datetime

from pydantic import ValidationError

from job_scraper_ai.models import JobListing


def test_job_listing_to_csv_row_serializes_expected_fields() -> None:
    listing = JobListing(
        job_id="123",
        title="Python Developer",
        company="Acme",
        location="Remote",
        salary_min=100000,
        salary_max=140000,
        currency="USD",
        job_description="Build job automation.",
        job_url="https://example.com/jobs/123",
        source="indeed",
        date_posted=datetime(2026, 4, 1, tzinfo=UTC),
    )

    row = listing.to_csv_row()

    assert row["title"] == "Python Developer"
    assert row["job_url"] == "https://example.com/jobs/123"
    assert row["date_posted"] == "2026-04-01T00:00:00+00:00"


def test_job_listing_rejects_extra_fields() -> None:
    try:
        JobListing(
            job_id="123",
            title="Python Developer",
            company="Acme",
            location="Remote",
            job_url="https://example.com/jobs/123",
            source="indeed",
            unexpected="value",  # type: ignore[arg-type]
        )
    except ValidationError as exc:
        assert "unexpected" in str(exc)
    else:
        raise AssertionError("Expected validation error")
