from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dotenv import load_dotenv


DEFAULT_OUTPUT_DIR: Final = Path("data/output")


@dataclass(frozen=True, slots=True)
class Settings:
    default_site: str = "indeed"
    default_keyword: str = "python"
    default_location: str = ""
    output_dir: Path = DEFAULT_OUTPUT_DIR
    request_timeout: int = 30
    request_delay_min: float = 2.0
    request_delay_max: float = 5.0
    user_agent: str = "Job-Scraper-AI/0.1.0"


def get_settings() -> Settings:
    load_dotenv()

    from os import getenv

    return Settings(
        default_site=getenv("DEFAULT_SITE", "indeed"),
        default_keyword=getenv("DEFAULT_KEYWORD", "python"),
        default_location=getenv("DEFAULT_LOCATION", ""),
        output_dir=Path(getenv("OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR))),
        request_timeout=int(getenv("REQUEST_TIMEOUT", "30")),
        request_delay_min=float(getenv("REQUEST_DELAY_MIN", "2")),
        request_delay_max=float(getenv("REQUEST_DELAY_MAX", "5")),
        user_agent=getenv("USER_AGENT", "Job-Scraper-AI/0.1.0"),
    )
