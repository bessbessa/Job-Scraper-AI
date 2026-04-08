from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


def _utc_now() -> datetime:
    return datetime.now(UTC)


class JobListing(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str | None = None
    title: str
    company: str
    location: str
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    job_description: str | None = None
    job_url: HttpUrl
    source: str
    date_posted: datetime | None = None
    scraped_at: datetime = Field(default_factory=_utc_now)

    @classmethod
    def csv_headers(cls) -> list[str]:
        return [
            "job_id",
            "title",
            "company",
            "location",
            "salary_min",
            "salary_max",
            "currency",
            "job_description",
            "job_url",
            "source",
            "date_posted",
            "scraped_at",
        ]

    def to_csv_row(self) -> dict[str, str]:
        data = self.model_dump()
        return {
            "job_id": "" if data["job_id"] is None else str(data["job_id"]),
            "title": str(data["title"]),
            "company": str(data["company"]),
            "location": str(data["location"]),
            "salary_min": "" if data["salary_min"] is None else str(data["salary_min"]),
            "salary_max": "" if data["salary_max"] is None else str(data["salary_max"]),
            "currency": "" if data["currency"] is None else str(data["currency"]),
            "job_description": "" if data["job_description"] is None else str(data["job_description"]),
            "job_url": str(data["job_url"]),
            "source": str(data["source"]),
            "date_posted": "" if data["date_posted"] is None else data["date_posted"].isoformat(),
            "scraped_at": data["scraped_at"].isoformat(),
        }

    def to_jsonable(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
