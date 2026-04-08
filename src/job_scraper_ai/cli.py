from __future__ import annotations

import argparse
import logging
from pathlib import Path

from job_scraper_ai.config import get_settings
from job_scraper_ai.scrapers import IndeedScraper
from job_scraper_ai.services import Exporter
from job_scraper_ai.utils.logging import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="job-scraper-ai")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor", help="Show resolved settings")
    doctor_parser.set_defaults(handler=handle_doctor)

    scrape_parser = subparsers.add_parser("scrape", help="Run a source scraper")
    scrape_parser.add_argument("--site", default=None)
    scrape_parser.add_argument("--keyword", default=None)
    scrape_parser.add_argument("--location", default=None)
    scrape_parser.add_argument("--format", choices=("csv", "json"), default="csv")
    scrape_parser.add_argument("--output", default=None)
    scrape_parser.set_defaults(handler=handle_scrape)

    return parser


def handle_doctor(_: argparse.Namespace) -> int:
    settings = get_settings()
    print(f"default_site={settings.default_site}")
    print(f"default_keyword={settings.default_keyword}")
    print(f"output_dir={settings.output_dir}")
    return 0


def handle_scrape(args: argparse.Namespace) -> int:
    settings = get_settings()
    site = args.site or settings.default_site
    keyword = args.keyword or settings.default_keyword
    location = args.location if args.location is not None else settings.default_location or None

    if site.lower() != "indeed":
        raise SystemExit(f"Unsupported site: {site}")

    scraper = IndeedScraper()
    jobs = scraper.scrape(keyword, location=location)

    exporter = Exporter()
    output_dir = Path(args.output) if args.output else settings.output_dir
    output_path = output_dir / f"{site.lower()}_{keyword.lower().replace(' ', '_')}.{args.format}"

    if args.format == "csv":
        exporter.export_csv(jobs, output_path)
    else:
        exporter.export_json(jobs, output_path)

    logging.getLogger(__name__).info("Exported %s jobs to %s", len(jobs), output_path)
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
