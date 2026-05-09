from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BrowserFetchError(RuntimeError):
    message: str

    def __str__(self) -> str:
        return self.message


class PlaywrightBrowserFetcher:
    def __init__(self, *, headless: bool = True, timeout_ms: int = 30_000) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms

    def fetch_html(self, url: str) -> str:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserFetchError(
                "Browser mode requires Playwright. Install with: pip install -e \".[browser]\""
            ) from exc

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.headless)
            page = browser.new_page()
            try:
                page.goto(url, wait_until="networkidle", timeout=self.timeout_ms)
                html = page.content()
                # detect common block/challenge pages (CAPTCHA, bot checks, access denied)
                if is_blocked_html(html):
                    reason = detect_block_reason(html) or "blocked by remote site"
                    raise BrowserFetchError(f"Blocked page detected when fetching {url}: {reason}")
                return html
            except Exception as exc:
                raise BrowserFetchError(f"Browser fetch failed for {url}: {exc}") from exc
            finally:
                browser.close()


def is_blocked_html(html: str) -> bool:
    if not html:
        return False
    lower = html.lower()
    # Common indicators of bot-blocking / challenges
    indicators = (
        "blocked - indeed",
        "access denied",
        "captcha",
        "are you human",
        "please verify",
        "verify you are human",
        "cf-chl-bypass",
        "cloudflare",
        "recaptcha",
        "bot detection",
        "please enable javascript",
        "access to this site is restricted",
    )
    return any(ind in lower for ind in indicators)


def detect_block_reason(html: str) -> str | None:
    lower = html.lower()
    if "blocked - indeed" in lower:
        return "indeed: blocked page"
    if "access denied" in lower:
        return "access denied"
    if "captcha" in lower or "recaptcha" in lower:
        return "captcha/challenge"
    if "cloudflare" in lower or "cf-chl-bypass" in lower:
        return "cloudflare challenge"
    if "are you human" in lower or "please verify" in lower:
        return "human verification required"
    return None
