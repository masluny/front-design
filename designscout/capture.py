"""Capture a reference site: screenshots (desktop + mobile) and computed design tokens."""
from __future__ import annotations

import json
from pathlib import Path

from . import analyze, browser, fingerprints, web

EXTRACT_JS = (Path(__file__).parent / "extract.js").read_text()
MAX_CSS_BYTES = 4_000_000


def _normalize_url(url: str) -> str:
    url = url.strip()
    if "://" not in url and not url.startswith("file:"):
        p = Path(url).expanduser()
        if p.exists():
            return p.resolve().as_uri()
        url = "https://" + url
    return url


def rendered_raw(url: str, out_dir: Path, slices: int = 6, mobile_slices: int = 3,
                 timeout_ms: int = 45000) -> tuple[dict, dict]:
    """Open the page in Chromium, scroll-capture screenshots and extract computed styles."""
    shots: dict[str, list[str]] = {}
    with browser.browser() as b:
        ctx = browser.new_context(b)
        page = ctx.new_page()
        css_responses = []
        page.on("response", lambda r: css_responses.append(r) if r.request.resource_type == "stylesheet" else None)
        status = browser.goto(page, url, timeout_ms)
        shots["desktop"] = browser.scroll_slices(page, out_dir, "desktop", slices)
        raw = page.evaluate(EXTRACT_JS, fingerprints.GLOBALS_TO_PROBE)
        raw["_html"] = page.content()[:1_500_000]
        extra, size = [], 0
        for r in css_responses:
            try:
                t = r.text()
            except Exception:
                continue
            size += len(t)
            if size > MAX_CSS_BYTES:
                break
            extra.append(t)
        raw["_css_extra"] = "\n".join(extra)
        raw["final_url"] = page.url
        raw["status"] = status
        raw["blocked"] = web.looks_blocked(status or 200, raw["_html"])
        ctx.close()
        if mobile_slices:
            mctx = browser.new_context(b, mobile=True)
            mpage = mctx.new_page()
            browser.goto(mpage, url, timeout_ms)
            shots["mobile"] = browser.scroll_slices(mpage, out_dir, "mobile", mobile_slices)
            raw["mobile_overflow_px"] = mpage.evaluate("document.documentElement.scrollWidth - innerWidth")
            mctx.close()
    raw["mode"] = "rendered"
    raw["url"] = url
    return raw, shots


def capture(url: str, refs_dir: Path, static: bool = False, slices: int = 6, mobile: bool = True,
            name: str | None = None) -> dict:
    url = _normalize_url(url)
    slug = name or browser.slug_for(url)
    out = refs_dir / slug
    out.mkdir(parents=True, exist_ok=True)
    shots: dict = {}
    mode_note = None
    if not static:
        ok, msg = browser.available()
        if not ok:
            static, mode_note = True, msg
    if static:
        raw = web.static_raw(url)
    else:
        try:
            raw, shots = rendered_raw(url, out, slices=slices, mobile_slices=3 if mobile else 0)
        except browser.BrowserUnavailable as e:
            mode_note = str(e)
            raw = web.static_raw(url)
    tokens = analyze.summarize(raw)
    if mode_note:
        tokens.setdefault("notes", []).append(mode_note)
    tokens["screenshots"] = shots
    tokens["slug"] = slug
    lean = {k: v for k, v in raw.items() if not k.startswith("_") and k not in ("css_text",)}
    (out / "raw.json").write_text(json.dumps(lean, indent=1, default=str))
    (out / "tokens.json").write_text(json.dumps(tokens, indent=2, default=str))
    notes = out / "notes.md"
    summary = analyze.to_markdown(tokens, shots)
    (out / "summary.md").write_text(summary)
    if not notes.exists():
        notes.write_text(f"# {tokens.get('title') or url}\n\nURL: {url}\n\n"
                         "## Observations\n\n- Layout and grid:\n- Hero pattern:\n- Section sequence:\n"
                         "- Type pairing and voice:\n- Color strategy:\n- Signature detail / effect:\n"
                         "- What to borrow:\n- What to avoid:\n")
    tokens["dir"] = str(out)
    return tokens
