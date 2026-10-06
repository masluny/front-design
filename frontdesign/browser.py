"""Thin Playwright layer shared by `capture` and `audit` (optional dependency)."""
from __future__ import annotations

import contextlib
import importlib.util
import re
from pathlib import Path

DESKTOP = {"width": 1440, "height": 900}
MOBILE = {"width": 390, "height": 844}

# Hide (never accept) common consent banners so they do not cover screenshots.
HIDE_CONSENT_CSS = """
#onetrust-consent-sdk, #onetrust-banner-sdk, #CybotCookiebotDialog, #usercentrics-root,
#didomi-host, #qc-cmp2-container, .fc-consent-root, .osano-cm-window, #truste-consent-track,
#cookie-banner, #cookie-consent, #cookiebanner, .cookie-banner, .cookie-consent, .cc-window,
.cky-consent-container, #hs-eu-cookie-confirmation, [aria-label*="cookie" i][role="dialog"],
[id*="cookie-notice" i], [class*="cookie-notice" i], [class*="CookieBanner" i], #termly-code-snippet-support
{ display: none !important; visibility: hidden !important; }
"""


# Fallback for custom banners: fixed/sticky/dialog elements that talk about cookies/consent.
HIDE_CONSENT_JS = r"""() => {
  const re = /cookie|consent|gdpr|rgpd|ciasteczk|datenschutz|tracking technologies/i;
  let hidden = 0;
  for (const el of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(el);
    const overlay = cs.position === 'fixed' || cs.position === 'sticky' || el.getAttribute('role') === 'dialog'
      || el.getAttribute('aria-modal') === 'true' || el.tagName === 'DIALOG';
    if (!overlay) continue;
    const t = (el.innerText || '').slice(0, 3000);
    if (t.length > 10 && t.length < 2500 && re.test(t) && el.querySelector('button, a, [role="button"]')) {
      el.style.setProperty('display', 'none', 'important');
      hidden++;
    }
  }
  if (hidden) { document.documentElement.style.overflow = ''; document.body.style.overflow = ''; }
  return hidden;
}"""


class BrowserUnavailable(RuntimeError):
    pass


def available() -> tuple[bool, str]:
    if importlib.util.find_spec("playwright") is None:
        return False, "playwright not installed: pip install 'front-design[capture]' && python -m playwright install chromium"
    return True, "ok"


@contextlib.contextmanager
def browser():
    ok, msg = available()
    if not ok:
        raise BrowserUnavailable(msg)
    from playwright.sync_api import Error, sync_playwright
    with sync_playwright() as p:
        b = None
        errors = []
        for kwargs in ({}, {"channel": "chrome"}, {"channel": "msedge"}):
            try:
                b = p.chromium.launch(**kwargs)
                break
            except Error as e:
                errors.append(str(e).splitlines()[0])
        if b is None:
            raise BrowserUnavailable("could not launch Chromium (run: python -m playwright install chromium). "
                                     + " | ".join(errors))
        try:
            yield b
        finally:
            b.close()


def new_context(b, mobile: bool = False, reduced_motion: str = "no-preference", color_scheme: str = "light"):
    v = b.version
    ua = (f"Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v} Mobile Safari/537.36"
          if mobile else
          f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v} Safari/537.36")
    opts = dict(
        viewport=MOBILE if mobile else DESKTOP,
        device_scale_factor=2 if mobile else 1,
        is_mobile=mobile,
        has_touch=mobile,
        reduced_motion=reduced_motion,
        color_scheme=color_scheme,
        user_agent=ua,
        locale="en-US",
    )
    return b.new_context(**opts)


def goto(page, url: str, timeout_ms: int = 45000) -> int | None:
    """Navigate and wait for the page to settle. Returns the HTTP status (None for file://)."""
    from playwright.sync_api import TimeoutError as PWTimeout
    resp = None
    try:
        resp = page.goto(url, wait_until="load", timeout=timeout_ms)
    except PWTimeout:
        pass  # heavy sites: continue with whatever rendered
    with contextlib.suppress(PWTimeout):
        page.wait_for_load_state("networkidle", timeout=8000)
    with contextlib.suppress(Exception):
        page.add_style_tag(content=HIDE_CONSENT_CSS)
    with contextlib.suppress(Exception):
        page.evaluate(HIDE_CONSENT_JS)
    with contextlib.suppress(Exception):
        page.evaluate("document.fonts && document.fonts.ready")
    page.wait_for_timeout(800)
    return resp.status if resp else None


def scroll_slices(page, out_dir: Path, prefix: str, max_slices: int, quality: int = 72,
                  settle_ms: int = 700) -> list[str]:
    """Scroll viewport by viewport, screenshot each (captures scroll-revealed content)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    vh = page.viewport_size["height"]
    total = page.evaluate("Math.max(document.documentElement.scrollHeight, document.body ? document.body.scrollHeight : 0)")
    files = []
    n = max(1, min(max_slices, -(-total // vh)))
    for i in range(n):
        y = i * vh
        page.evaluate(f"window.scrollTo({{top: {y}, behavior: 'instant'}})")
        page.wait_for_timeout(settle_ms)
        name = f"{prefix}-{i + 1:02d}.jpg"
        page.screenshot(path=str(out_dir / name), type="jpeg", quality=quality)
        files.append(name)
    page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
    page.wait_for_timeout(400)
    return files


def slug_for(url: str) -> str:
    s = re.sub(r"^https?://(www\.)?", "", url.strip().lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:60] or "page"
