"""Audit a built page: accessibility, legibility, motion safety, responsiveness and craft.

Rendered mode (Playwright) measures what users see: text contrast is computed against the real
pixels behind each text element (text is made transparent, the page is screenshotted, the
background under each text box is sampled), so text over gradients, images and WebGL shaders is
checked too. Static mode only parses HTML/CSS.
"""
from __future__ import annotations

import io
import json
import re
import time
from pathlib import Path

from . import analyze, browser, color, fingerprints, web
from .capture import EXTRACT_JS, _normalize_url

AUDIT_JS = (Path(__file__).parent / "audit.js").read_text()
RAF_COUNTER = ("window.__dsRaf = 0; const __r = window.requestAnimationFrame.bind(window);"
               "window.requestAnimationFrame = (cb) => { window.__dsRaf++; return __r(cb); };")
HIDE_TEXT_CSS = ("*, *::before, *::after, *::marker { color: transparent !important; -webkit-text-fill-color: transparent !important;"
                 " text-shadow: none !important; caret-color: transparent !important; -webkit-text-stroke: 0 !important; }")
LOREM = re.compile(r"lorem ipsum dolor|dolor sit amet|consectetur adipiscing", re.I)  # real filler, not a mention
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
MOTION_LIBS = {"GSAP", "GSAP ScrollTrigger", "Lenis", "Locomotive Scroll", "three.js", "Spline", "Rive", "Lottie",
               "Paper Shaders", "Unicorn Studio", "PixiJS", "AOS", "Swiper"}


class Report:
    def __init__(self, target: str, mode: str):
        self.target, self.mode = target, mode
        self.findings: list[dict] = []
        self.metrics: dict = {}
        self.shots: dict[str, list[str]] = {}

    def add(self, fid: str, severity: str, title: str, fix: str, examples=None, count: int | None = None,
            source: str | None = None, detail: str | None = None):
        examples = list(examples or [])
        self.findings.append({"id": fid, "severity": severity, "title": title, "detail": detail,
                              "count": count if count is not None else (len(examples) or 1),
                              "examples": examples[:6], "fix": fix, "source": source})

    def finish(self, min_score: int) -> dict:
        order = {"error": 0, "warning": 1, "info": 2}
        self.findings.sort(key=lambda f: (order[f["severity"]], -f["count"]))
        errors = sum(f["severity"] == "error" for f in self.findings)
        warnings = sum(f["severity"] == "warning" for f in self.findings)
        score = max(0, 100 - 10 * errors - 3 * warnings)
        return {"target": self.target, "mode": self.mode, "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "score": score, "pass": errors == 0 and score >= min_score, "min_score": min_score,
                "errors": errors, "warnings": warnings, "metrics": self.metrics,
                "findings": self.findings, "screenshots": self.shots}


# ------------------------------------------------------------------ source loading

def _load_source(target: str) -> tuple[str, str, str]:
    """Return (url_for_browser, html, css) for a local file or URL."""
    url = _normalize_url(target)
    if url.startswith("file:"):
        path = Path(url[len("file://"):])
        html = path.read_text(errors="replace")
        page = web.parse_page(html)
        css = "\n".join(page.inline_css)
        for href in page.stylesheets:
            if re.match(r"^(https?:)?//", href):
                try:
                    _, st, text = web.fetch(href if href.startswith("http") else "https:" + href, accept="text/css,*/*")
                    css += "\n" + (text if st == 200 else "")
                except web.FetchError:
                    pass
            else:
                p = (path.parent / href.split("?")[0]).resolve()
                if p.exists():
                    css += "\n" + p.read_text(errors="replace")
        return url, html, css
    raw = web.static_raw(url)
    return url, raw["_html"], raw["_css"]


# ------------------------------------------------------------------ static checks

def static_checks(rep: Report, html: str, css: str, libs: dict):
    page = web.parse_page(html)
    if not page.lang:
        rep.add("html-lang", "error", "Missing <html lang>", "Add lang=\"en\" (or the page language) to <html>.", source="wcag22")
    if not page.title.strip():
        rep.add("title", "warning", "Missing <title>", "Give every page a unique, descriptive title.")
    vp = page.meta.get("viewport", "")
    if not vp:
        rep.add("viewport", "error", "Missing viewport meta", "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">.")
    elif re.search(r"user-scalable\s*=\s*(no|0)|maximum-scale\s*=\s*1(\.0)?\b", vp):
        rep.add("zoom-blocked", "error", "Viewport blocks zoom", "Remove user-scalable=no / maximum-scale=1 (WCAG 1.4.4 Resize Text).", source="wcag22")
    if not page.meta.get("description"):
        rep.add("meta-description", "info", "No meta description", "Add a 120-160 character description.")
    h1 = [h for h in page.headings if h["tag"] == "h1"]
    if page.counts.get("h1", 0) == 0:
        rep.add("no-h1", "warning", "No <h1>", "Mark up the main headline as the single <h1>.", source="nng-visual-hierarchy")
    elif page.counts.get("h1", 0) > 1:
        rep.add("multi-h1", "info", f"{page.counts['h1']} <h1> elements", "Prefer one <h1> per page.", examples=[h["text"] for h in h1])
    levels = [int(t) for t in re.findall(r"<h([1-6])\b", html, re.I)]
    skips = [f"h{a} -> h{b}" for a, b in zip(levels, levels[1:]) if b > a + 1]
    if skips:
        rep.add("heading-skip", "warning", "Heading levels skip", "Do not jump heading levels (h2 -> h4); style with CSS instead.",
                examples=sorted(set(skips)), source="wcag22")
    imgs = re.findall(r"<img\b[^>]*>", html, re.I)
    no_alt = [re.search(r"src=[\"']([^\"']+)", i).group(1)[-60:] if re.search(r"src=[\"']([^\"']+)", i) else i[:60]
              for i in imgs if not re.search(r"\balt\s*=", i, re.I)]
    if no_alt:
        rep.add("img-alt", "error", "Images without alt attribute", "Add alt text (or alt=\"\" for purely decorative images).",
                examples=no_alt, count=len(no_alt), source="wcag22")
    if page.counts.get("main", 0) == 0:
        rep.add("landmark-main", "warning", "No <main> landmark", "Wrap the primary content in <main>.", source="a11y-project-checklist")
    for v in re.findall(r"<video\b[^>]*>", html, re.I):
        if re.search(r"\bautoplay\b", v, re.I) and not re.search(r"\bmuted\b", v, re.I):
            rep.add("video-autoplay-sound", "error", "Autoplaying video without muted", "Autoplay only muted video, with playsinline and a pause control.")
            break
    if re.search(r"tabindex\s*=\s*[\"']?[1-9]", html, re.I):
        rep.add("tabindex-positive", "warning", "Positive tabindex", "Use DOM order instead of tabindex > 0.", source="wcag22")
    text = web.html_to_text(html)
    if LOREM.search(text):
        rep.add("lorem", "error", "Placeholder lorem ipsum text", "Write real copy; design decisions depend on real content length.")
    blocks = re.findall(r"([^{}]+)\{([^{}]*)\}", css)
    removed = [sel.strip() for sel, body in blocks if re.search(r"outline\s*:\s*(none|0)\b", body, re.I)]
    restored = any(":focus" in sel and re.search(r"outline\s*:\s*(?!none|0\b)\S|box-shadow\s*:\s*(?!none)\S", body, re.I)
                   for sel, body in blocks)
    if removed and not restored:
        rep.add("focus-removed", "warning", "Focus outline removed without replacement",
                "Keep a visible :focus-visible style (2px outline with offset).", examples=removed, source="wcag22")
    motion_libs = MOTION_LIBS & set(libs.get("effects", []))
    animated = bool(motion_libs) or bool(re.search(r"@keyframes|animation\s*:|transition\s*:", css, re.I))
    handles = bool(re.search(r"prefers-reduced-motion", html + css, re.I)) or "MotionConfig" in html
    rep.metrics["reduced_motion_handled_in_source"] = handles
    if animated and not handles:
        rep.add("reduced-motion-missing", "error", "Animations without a prefers-reduced-motion path",
                "Gate motion with @media (prefers-reduced-motion: no-preference) / matchMedia; stop shaders (speed 0) and smooth scroll.",
                examples=sorted(motion_libs), source="wcag-animation")


# ------------------------------------------------------------------ rendered checks

def _sample_contrast(png: bytes, items: list[dict], dpr: float) -> list[dict]:
    """Contrast of each text item against the pixels behind it (text hidden in the screenshot)."""
    try:
        from PIL import Image
    except ImportError:
        return []
    img = Image.open(io.BytesIO(png)).convert("RGB")
    W, H = img.size
    out = []
    for it in items:
        x0, y0, x1, y1 = (int(v * dpr) for v in it["rect"])
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(W, max(x0 + 1, x1)), min(H, max(y0 + 1, y1))
        crop = img.crop((x0, y0, x1, y1))
        crop.thumbnail((48, 48))
        px = list(crop.getdata())
        if not px:
            continue
        px.sort(key=lambda p: 0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2])
        picks = [px[int(len(px) * q)] for q in (0.1, 0.5, 0.9)]
        fg = color.parse(it["color"])
        if not fg:
            continue
        fg = (fg[0], fg[1], fg[2], fg[3] * it.get("opacity", 1))
        ratios = []
        for p in picks:
            bg = (p[0] / 255, p[1] / 255, p[2] / 255, 1.0)
            ratios.append(color.contrast(color.blend(fg, bg), bg))
        out.append({**it, "ratio": round(min(ratios), 2), "ratio_median_bg": round(ratios[1], 2),
                    "bg_sample": color.to_hex((picks[1][0] / 255, picks[1][1] / 255, picks[1][2] / 255))})
    return out


def _guess_contrast(items: list[dict]) -> list[dict]:
    out = []
    for it in items:
        fg, bg = color.parse(it["color"]), color.parse(it.get("bg"))
        if not fg or not bg or it.get("over_media"):
            continue
        fg = (fg[0], fg[1], fg[2], fg[3] * it.get("opacity", 1))
        out.append({**it, "ratio": round(color.contrast(color.blend(fg, bg), bg), 2), "bg_sample": color.to_hex(bg)})
    return out


def _contrast_pass(page, out_dir: Path, prefix: str, max_slices: int, dpr: float) -> tuple[list[dict], list[str]]:
    page.evaluate(AUDIT_JS)
    vh = page.viewport_size["height"]
    total = page.evaluate("document.documentElement.scrollHeight")
    n = max(1, min(max_slices, -(-total // vh)))
    results, files = [], []
    for i in range(n):
        page.evaluate(f"window.scrollTo({{top: {i * vh}, behavior: 'instant'}})")
        page.wait_for_timeout(650)
        name = f"{prefix}-{i + 1:02d}.jpg"
        page.screenshot(path=str(out_dir / name), type="jpeg", quality=72)
        files.append(name)
        items = page.evaluate("window.__ds.textInViewport()")
        if not items:
            continue
        handle = page.add_style_tag(content=HIDE_TEXT_CSS)
        page.wait_for_timeout(60)
        png = page.screenshot(type="png")
        handle.evaluate("el => el.remove()")
        sampled = _sample_contrast(png, items, dpr) or _guess_contrast(items)
        for s in sampled:
            s["viewport"] = i + 1
        results.extend(sampled)
    page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
    return results, files


def _report_contrast(rep: Report, results: list[dict], label: str):
    fails, decorative = [], []
    for r in results:
        large = r["size"] >= 24 or (r["size"] >= 18.66 and r["weight"] >= 700)
        need = 3.0 if large else 4.5
        if r["ratio"] < need:
            row = f"\"{r['text'][:40]}\" {r['ratio']}:1 (needs {need}) on {r['bg_sample']} [{r['sel']}, {label} view {r['viewport']}]"
            (decorative if r.get("decorative") else fails).append((r["ratio"], row))
    seen, uniq = set(), []
    for ratio, row in sorted(fails):
        key = row.split(" [")[0]
        if key not in seen:
            seen.add(key)
            uniq.append(row)
    rep.metrics[f"text_checked_{label}"] = len(results)
    if uniq:
        rep.add(f"contrast-{label}", "error", f"Text below WCAG AA contrast ({label})",
                "Darken/lighten the text or add a scrim behind it; for text over shaders/images check the brightest frame.",
                examples=uniq, count=len(uniq), source="wcag-contrast")
    if decorative:
        rep.add(f"contrast-decorative-{label}", "info", f"Low-contrast text inside aria-hidden ({label})",
                "Fine if purely decorative; otherwise fix contrast.", examples=[r for _, r in sorted(decorative)], count=len(decorative))


def rendered_checks(rep: Report, url: str, out_dir: Path, slices: int = 6) -> dict:
    shots_dir = out_dir / "shots"
    shots_dir.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []
    with browser.browser() as b:
        # ---------------- desktop
        ctx = browser.new_context(b)
        ctx.add_init_script(RAF_COUNTER)
        page = ctx.new_page()
        page.on("console", lambda m: console_errors.append(m.text[:200]) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errors.append(str(e)[:200]))
        browser.goto(page, url)
        raw = page.evaluate(EXTRACT_JS, fingerprints.GLOBALS_TO_PROBE)
        raw["_html"] = page.content()[:1_500_000]
        tokens = analyze.summarize({**raw, "mode": "rendered", "url": url})
        page.evaluate(AUDIT_JS)
        normal_motion = page.evaluate("new Promise(r => { const a = window.__dsRaf || 0; setTimeout(() => r({raf: (window.__dsRaf || 0) - a, animations: document.getAnimations ? document.getAnimations().filter(x => x.playState === 'running').length : 0}), 1000) })")
        paragraphs = page.evaluate("window.__ds.paragraphs()")
        overflow_desktop = page.evaluate("window.__ds.overflowers()")
        unnamed = page.evaluate("window.__ds.unnamedControls()")
        unlabeled = page.evaluate("window.__ds.unlabeledInputs()")
        focus = []
        page.evaluate("window.scrollTo(0, 0)")
        page.mouse.click(1, 1)
        for _ in range(14):
            page.keyboard.press("Tab")
            page.wait_for_timeout(60)
            st = page.evaluate("window.__ds.focusState()")
            if st:
                focus.append(st)
        browser.goto(page, url)
        contrast_d, rep.shots["desktop"] = _contrast_pass(page, shots_dir, "desktop", slices, 1.0)
        ctx.close()

        # ---------------- mobile
        mctx = browser.new_context(b, mobile=True)
        mpage = mctx.new_page()
        browser.goto(mpage, url)
        mpage.evaluate(AUDIT_JS)
        overflow = mpage.evaluate("window.__ds.overflowers()")
        targets = mpage.evaluate("window.__ds.targets()")
        mparas = mpage.evaluate("window.__ds.paragraphs()")
        contrast_m, rep.shots["mobile"] = _contrast_pass(mpage, shots_dir, "mobile", max(3, slices // 2), 2.0)
        mctx.close()

        # ---------------- reduced motion
        rctx = browser.new_context(b, reduced_motion="reduce")
        rctx.add_init_script(RAF_COUNTER)
        rpage = rctx.new_page()
        browser.goto(rpage, url)
        reduced_motion = rpage.evaluate("new Promise(r => { const a = window.__dsRaf || 0; setTimeout(() => r({raf: (window.__dsRaf || 0) - a, animations: document.getAnimations ? document.getAnimations().filter(x => x.playState === 'running').length : 0}), 1000) })")
        rctx.close()

    # ---------------- findings
    _report_contrast(rep, contrast_d, "desktop")
    _report_contrast(rep, contrast_m, "mobile")

    if overflow["scroll_width"] > overflow["viewport"] + 1:
        rep.add("mobile-overflow", "error", "Horizontal scroll on mobile (390px)",
                "Find the element wider than the viewport (fixed widths, long words, wide media) and constrain it.",
                examples=[f"{o['sel']} right edge {o['right']}px" for o in overflow["offenders"]], source="defensive-css",
                detail=f"page is {overflow['scroll_width']}px wide in a {overflow['viewport']}px viewport")
    if overflow_desktop["scroll_width"] > overflow_desktop["viewport"] + 1:
        rep.add("desktop-overflow", "error", "Horizontal scroll on desktop (1440px)",
                "Constrain the element wider than the viewport (long unbroken strings, fixed widths, wide media).",
                examples=[f"{o['sel']} right edge {o['right']}px" for o in overflow_desktop["offenders"]], source="defensive-css",
                detail=f"page is {overflow_desktop['scroll_width']}px wide in a {overflow_desktop['viewport']}px viewport")
    small = [t for t in targets if not t["inline"] and (t["w"] < 24 or t["h"] < 24)]
    crowded = []
    for t in small:
        near = [o for o in targets if o is not t and ((o["cx"] - t["cx"]) ** 2 + (o["cy"] - t["cy"]) ** 2) ** 0.5 < 24]
        if near:
            crowded.append(f"{t['sel']} \"{t['name']}\" {round(t['w'])}x{round(t['h'])}px")
    if crowded:
        rep.add("target-size", "error", "Touch targets under 24x24px and crowded (mobile)",
                "Make targets at least 24x24 CSS px (44px for primary actions) or space them apart.",
                examples=crowded, count=len(crowded), source="wcag-target-size")
    primary_small = [t for t in targets if t["tag"] == "button" and t["h"] < 40 and not t["inline"]]
    if primary_small:
        rep.add("target-size-comfort", "info", "Buttons shorter than 40px on mobile",
                "Apple HIG suggests 44pt for comfortable tapping.",
                examples=[f"{t['sel']} \"{t['name']}\" {round(t['h'])}px" for t in primary_small], source="apple-hig")
    if unnamed:
        rep.add("control-name", "error", "Links/buttons without an accessible name",
                "Add visible text or aria-label (icon buttons especially).", examples=unnamed, count=len(unnamed), source="wcag22")
    if unlabeled:
        rep.add("input-label", "error", "Form fields without a label",
                "Use a visible <label for>; placeholders are not labels.",
                examples=[u["sel"] + (" (placeholder only)" if u["placeholder_only"] else "") for u in unlabeled],
                source="nng-placeholders")
    long_lines = [p for p in paragraphs if p["chars_per_line"] > 90]
    if long_lines:
        rep.add("measure", "warning", "Lines longer than 90 characters (desktop)",
                "Constrain text blocks to about 60-75ch (max-width: 65ch).",
                examples=[f"{p['sel']} ~{p['chars_per_line']} chars/line" for p in long_lines], source="butterick-line-length")
    tight = [p for p in paragraphs if p["line_height"] < 1.3]
    if tight:
        rep.add("line-height", "warning", "Body text line-height under 1.3",
                "Use 1.4-1.6 for body copy.", examples=[f"{p['sel']} {p['line_height']:.2f}" for p in tight],
                source="butterick-ten-minutes")
    centered = [p for p in paragraphs if p["centered"]]
    if centered:
        rep.add("centered-paragraphs", "warning", "Centered multi-line paragraphs",
                "Left-align body text longer than ~3 lines; centered ragged edges slow reading.",
                examples=[p["sel"] for p in centered], source="butterick-ten-minutes")
    tiny = [p for p in mparas if p["size"] < 15]
    if tiny:
        rep.add("mobile-body-size", "warning", "Body text under 15px on mobile",
                "Use 16px or larger for body copy on phones.", examples=[f"{p['sel']} {p['size']}px" for p in tiny],
                source="butterick-ten-minutes")
    invisible = [f["sel"] for f in focus if not f["changed"]]
    if invisible:
        rep.add("focus-visible", "error", "Keyboard focus is not visible",
                "Add a :focus-visible style (e.g. outline: 2px solid var(--accent); outline-offset: 2px).",
                examples=invisible, source="wcag22")
    obscured = [f["sel"] for f in focus if f.get("obscured")]
    if obscured:
        rep.add("focus-obscured", "warning", "Focused element hidden under a sticky/fixed element",
                "Add scroll-padding-top equal to the sticky header height.", examples=obscured, source="wcag-focus-not-obscured")
    if not focus:
        rep.add("no-focusables", "info", "Tab did not reach any focusable element", "Check that interactive elements are real links/buttons.")

    moving = normal_motion["raf"] > 5 or normal_motion["animations"] > 0
    still_moving = reduced_motion["raf"] > 5 or reduced_motion["animations"] > 0
    rep.metrics.update(motion_normal=normal_motion, motion_reduced=reduced_motion)
    if moving and still_moving and reduced_motion["raf"] >= 0.6 * normal_motion["raf"] \
            and reduced_motion["animations"] >= normal_motion["animations"]:
        rep.add("reduced-motion-ignored", "warning", "Motion continues with prefers-reduced-motion: reduce",
                "Under reduced motion: stop shader loops (speed 0), skip smooth scroll, disable parallax/autoplay.",
                detail=f"normal: {normal_motion}, reduced: {reduced_motion}", source="wcag-animation")

    if console_errors:
        rep.add("console-errors", "warning", "JavaScript errors in the console", "Fix runtime errors before review.",
                examples=sorted(set(console_errors)), count=len(set(console_errors)))

    perf = tokens.get("perf", {})
    rep.metrics["perf"] = perf
    if perf.get("cls") and perf["cls"] > 0.1:
        rep.add("cls", "warning", f"Layout shift CLS {perf['cls']}", "Reserve space for media/embeds; use font-display and size-adjust.",
                source="webdev-cls")
    if perf.get("transfer_kb", 0) > 3000:
        rep.add("weight", "warning", f"Page transfers {perf['transfer_kb']} kB", "Compress media, lazy-load effects, drop unused libraries.",
                source="webdev-lcp")
    webgl = tokens.get("media", {}).get("webgl_canvases", 0)
    if webgl > 2:
        rep.add("webgl-count", "warning", f"{webgl} WebGL canvases", "Keep one signature effect; each canvas is a GPU context.", source="webdev-animations")

    fonts = [f for f in tokens.get("fonts", []) if f["class"] != "mono" and f["share"] > 0.01]
    if len(fonts) > 3:
        rep.add("font-count", "warning", f"{len(fonts)} text font families", "Use at most two families (display + text) plus mono.",
                examples=[f["family"] for f in fonts], source="butterick-ten-minutes")
    if tokens["type"].get("distinct_sizes", 0) > 10:
        rep.add("type-scale", "warning", f"{tokens['type']['distinct_sizes']} distinct font sizes",
                "Map sizes to a modular scale (front-design scale).", source="utopia-fluid-type")
    sp = tokens.get("spacing", {})
    fluid_space = any(k.startswith("--space") and "clamp(" in v for k, v in tokens.get("css_variables", {}).items())
    if sp.get("on_grid_share", 1) < 0.5 and not fluid_space:  # fluid clamp() spacing is off-grid by design
        rep.add("spacing-grid", "info", f"Only {round(sp['on_grid_share'] * 100)}% of spacing values on a 4px grid",
                "Use spacing tokens from one scale.", source="eightshapes-space")
    if any(n.startswith("dominant accent is a stock Tailwind") for n in tokens.get("notes", [])):
        rep.add("stock-accent", "info", "Accent color is a stock Tailwind indigo/violet",
                "Intentional? A brand-specific accent makes the design less template-like.")
    heads_ctas = " ".join([h["text"] for h in tokens["content"]["headings"]] + [c["text"] for c in tokens["content"]["ctas"]])
    if EMOJI.search(heads_ctas):
        rep.add("emoji-ui", "info", "Emoji in headings or buttons", "Use a consistent icon set (Lucide, Phosphor) unless emoji are the brand voice.")
    rep.metrics["tokens"] = {k: tokens.get(k) for k in ("fonts", "type", "palette", "spacing", "libraries")}
    return tokens


def run(target: str, out_dir: Path, static: bool = False, min_score: int = 85, slices: int = 6) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    url, html, css = _load_source(target)
    libs = fingerprints.detect(html=html, css=css, scripts=re.findall(r"<script[^>]+src=[\"']([^\"']+)", html, re.I))
    mode = "static"
    if not static and browser.available()[0]:
        mode = "rendered"
    rep = Report(target, mode)
    static_checks(rep, html, css, libs)
    if mode == "rendered":
        try:
            rendered_checks(rep, url, out_dir, slices=slices)
        except browser.BrowserUnavailable as e:
            rep.mode = "static"
            rep.add("browser", "info", "Rendered checks skipped", str(e))
    else:
        rep.add("static-only", "info", "Static audit only", "Install Playwright for contrast, target-size, focus and motion checks.")
    result = rep.finish(min_score)
    (out_dir / "latest.json").write_text(json.dumps(result, indent=2))
    hist = out_dir / "history"
    hist.mkdir(exist_ok=True)
    (hist / f"{time.strftime('%Y%m%d-%H%M%S')}.json").write_text(json.dumps({k: result[k] for k in ("time", "score", "pass", "errors", "warnings")}))
    return result


def format_text(result: dict) -> str:
    mark = {"error": "x", "warning": "!", "info": "-"}
    L = [f"audit {result['target']} ({result['mode']}): score {result['score']}/100, "
         f"{result['errors']} errors, {result['warnings']} warnings -> {'PASS' if result['pass'] else 'FAIL'} (min {result['min_score']})"]
    for f in result["findings"]:
        L.append(f"[{mark[f['severity']]}] {f['severity'].upper()} {f['title']}" + (f" (x{f['count']})" if f["count"] > 1 else ""))
        if f.get("detail"):
            L.append(f"      {f['detail']}")
        for e in f["examples"][:4]:
            L.append(f"      - {e}")
        L.append(f"      fix: {f['fix']}" + (f"  [source: {f['source']}]" if f.get("source") else ""))
    if result.get("screenshots"):
        L.append("screenshots: " + ", ".join(f"{k}: {len(v)}" for k, v in result["screenshots"].items()))
    return "\n".join(L)
