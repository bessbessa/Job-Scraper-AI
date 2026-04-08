from __future__ import annotations

import csv
import json
from pathlib import Path

from job_scraper_ai.models import JobListing


class Exporter:
    def export_csv(self, jobs: list[JobListing], output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=JobListing.csv_headers())
            writer.writeheader()
            for job in jobs:
                writer.writerow(job.to_csv_row())

        return output_path

    def export_json(self, jobs: list[JobListing], output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [job.to_jsonable() for job in jobs]
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return output_path
