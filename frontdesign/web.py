"""HTTP fetching, HTML-to-text, quote verification and static (no-browser) page analysis."""
from __future__ import annotations

import gzip
import re
import ssl
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zlib
from collections import Counter
from html.parser import HTMLParser

from . import __version__

# An honest UA: several sites (w3.org among them) reject scripts that pretend to be a browser.
UA = f"front-design/{__version__} (UI/UX research CLI; +https://github.com/masluny/front-design)"
MAX_BYTES = 4_000_000
BLOCK_MARKERS = ("just a moment...", "attention required", "access denied", "verify you are human",
                 "are you a robot", "captcha")


class FetchError(Exception):
    pass


def fetch(url: str, timeout: float = 20, max_bytes: int = MAX_BYTES, accept: str = "text/html,*/*") -> tuple[str, int, str]:
    """GET a URL. Returns (final_url, status, text). Raises FetchError on network failure."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": accept, "Accept-Language": "en,pl;q=0.8",
        "Accept-Encoding": "gzip, deflate",
    })
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read(max_bytes)
            status = resp.status
            final = resp.geturl()
            enc = (resp.headers.get("Content-Encoding") or "").lower()
            charset = resp.headers.get_content_charset() or "utf-8"
    except urllib.error.HTTPError as e:
        body = e.read(200_000) if hasattr(e, "read") else b""
        return url, e.code, body.decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, ConnectionError, ssl.SSLError, ValueError) as e:
        raise FetchError(f"{url}: {e}") from e
    if enc == "gzip":
        try:
            raw = gzip.decompress(raw)
        except (OSError, EOFError):
            pass
    elif enc == "deflate":
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            pass
    return final, status, raw.decode(charset, "replace")


def looks_blocked(status: int, html: str) -> bool:
    head = html[:6000].lower()
    title = re.search(r"<title[^>]*>(.*?)</title>", head, re.S)
    t = title.group(1) if title else ""
    return status in (401, 403, 429, 503) or any(m in t for m in BLOCK_MARKERS)


# ------------------------------------------------------------------ html -> text

class _TextParser(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template", "iframe", "canvas"}
    BLOCK = {"p", "div", "section", "article", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6",
             "br", "tr", "td", "th", "blockquote", "pre", "figcaption", "header", "footer", "main", "nav"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    p = _TextParser()
    try:
        p.feed(html)
        p.close()
    except Exception:  # malformed markup: keep what we have
        pass
    text = "".join(p.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


_QUOTE_MAP = str.maketrans({  # curly quotes, dashes, nbsp, ellipsis -> ASCII
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u2032": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"', "\u2033": '"',
    "\u2013": "-", "\u2014": "-", "\u2212": "-", "\u00a0": " ", "\u2026": "...",
    # invisible characters some sites inject (soft hyphens for justification, zero-width joiners)
    "\u00ad": None, "\u200b": None, "\u200c": None, "\u200d": None, "\u2060": None, "\ufeff": None,
})


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_QUOTE_MAP).lower()
    return re.sub(r"\s+", " ", text).strip()


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9À-ɏ]+", normalize(text))


def verify_quote(quote: str, page_text: str) -> tuple[str, float]:
    """Check a quote against page text. Returns (status, score): exact | close | not-found."""
    q, t = normalize(quote), normalize(page_text)
    if q and q in t:
        return "exact", 1.0
    qw, tw = _words(quote), _words(page_text)
    if not qw or not tw:
        return "not-found", 0.0
    # longest run of consecutive quote words appearing consecutively in the page
    index: dict[str, list[int]] = {}
    for i, w in enumerate(tw):
        index.setdefault(w, []).append(i)
    best = 0
    for qi in range(len(qw)):
        for ti in index.get(qw[qi], []):
            k = 0
            while qi + k < len(qw) and ti + k < len(tw) and qw[qi + k] == tw[ti + k]:
                k += 1
            best = max(best, k)
        if best >= len(qw) - qi:
            break
    score = best / len(qw)
    return ("close" if score >= 0.8 else "not-found"), round(score, 3)


# ------------------------------------------------------------------ static analysis

class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self.meta: dict[str, str] = {}
        self.lang = ""
        self.scripts: list[str] = []
        self.stylesheets: list[str] = []
        self.inline_css: list[str] = []
        self._in_style = False
        self.style_attrs: list[str] = []
        self.headings: list[dict] = []
        self._heading: dict | None = None
        self.counts: Counter = Counter()

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        self.counts[tag] += 1
        if tag == "html":
            self.lang = a.get("lang", "")
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = (a.get("name") or a.get("property") or "").lower()
            if key:
                self.meta[key] = a.get("content", "")
        elif tag == "script" and a.get("src"):
            self.scripts.append(a["src"])
        elif tag == "link" and "stylesheet" in a.get("rel", "").lower() and a.get("href"):
            self.stylesheets.append(a["href"])
        elif tag == "style":
            self._in_style = True
        elif tag in ("h1", "h2", "h3"):
            self._heading = {"tag": tag, "text": ""}
        elif tag == "br" and self._heading is not None:
            self._heading["text"] += " "
        if a.get("style"):
            self.style_attrs.append(a["style"])

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "style":
            self._in_style = False
        elif tag in ("h1", "h2", "h3") and self._heading:
            self._heading["text"] = re.sub(r"\s+", " ", self._heading["text"]).strip()[:140]
            if self._heading["text"]:
                self.headings.append(self._heading)
            self._heading = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_style:
            self.inline_css.append(data)
        if self._heading is not None:
            self._heading["text"] += data


def parse_page(html: str) -> _PageParser:
    p = _PageParser()
    try:
        p.feed(html)
        p.close()
    except Exception:
        pass
    return p


CSS_FEATURES = {
    "container_queries": r"@container",
    "has_selector": r":has\(",
    "oklch": r"oklch\(",
    "color_mix": r"color-mix\(",
    "clamp": r"clamp\(",
    "view_transitions": r"view-transition",
    "scroll_driven": r"animation-timeline",
    "backdrop_filter": r"backdrop-filter",
    "at_property": r"@property",
    "text_wrap_balance": r"text-wrap(?:-style)?:\s*(?:balance|pretty)",
    "cascade_layers": r"@layer",
    "subgrid": r"subgrid",
    "starting_style": r"@starting-style",
    "anchor_positioning": r"anchor-name|position-anchor",
    "css_grid": r"display:\s*grid",
    "keyframes": r"@keyframes",
    "dark_mode_media": r"prefers-color-scheme:\s*dark",
    "reduced_motion_media": r"prefers-reduced-motion",
    "variable_fonts": r"font-variation-settings|font-weight:\s*\d+\s+\d+",
}


def css_features(css: str) -> dict[str, int]:
    return {k: len(re.findall(p, css, re.I)) for k, p in CSS_FEATURES.items()}


_ROOT_BLOCK = re.compile(r"(?:^|[{};])\s*([^{}@;]*?(?::root|\bhtml\b)[^{}@;]*)\{([^{}]*)\}", re.I)
_VAR_DECL = re.compile(r"(--[\w-]+)\s*:\s*([^;]+)")


def root_variables(css: str, limit: int = 400) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in _ROOT_BLOCK.finditer(css):
        for name, value in _VAR_DECL.findall(m.group(2)):
            if name not in out:
                out[name] = value.strip()[:200]
            if len(out) >= limit:
                return out
    return out


def font_faces(css: str) -> list[str]:
    fams = re.findall(r"@font-face\s*{[^}]*?font-family\s*:\s*([^;}]+)", css, re.I)
    seen: list[str] = []
    for f in fams:
        f = f.strip().strip("'\"")
        if f and f not in seen:
            seen.append(f)
    return seen


def css_declarations(css: str, prop: str) -> Counter:
    return Counter(v.strip() for v in re.findall(rf"(?<![-\w]){prop}\s*:\s*([^;}}!]+)", css, re.I))


def static_raw(url: str, max_css_files: int = 10) -> dict:
    """Analyze a page without a browser: HTML + linked CSS. No screenshots, unweighted styles."""
    final, status, html = fetch(url)
    page = parse_page(html)
    css_parts = list(page.inline_css)
    css_errors = []
    for href in page.stylesheets[:max_css_files]:
        css_url = urllib.parse.urljoin(final, href)
        try:
            _, st, text = fetch(css_url, max_bytes=2_000_000, accept="text/css,*/*")
            if st == 200:
                css_parts.append(text)
            else:
                css_errors.append(f"{css_url}: HTTP {st}")
        except FetchError as e:
            css_errors.append(str(e))
    css = "\n".join(css_parts) + "\n" + "\n".join(f"x{{{s}}}" for s in page.style_attrs)
    colors = Counter()
    from .color import COLOR_TOKEN_RE
    for tok in COLOR_TOKEN_RE.findall(css):
        colors[tok] += 1
    fam_counts = Counter()
    for v, c in css_declarations(css, "font-family").items():
        first = v.split(",")[0].strip().strip("'\"")
        if first and not first.startswith("var("):
            known = next((k for k in fam_counts if k.lower() == first.lower()), first)
            fam_counts[known] += c
    return {
        "mode": "static",
        "url": url,
        "final_url": final,
        "status": status,
        "blocked": looks_blocked(status, html),
        "title": page.title.strip(),
        "lang": page.lang,
        "meta": page.meta,
        "scripts": [urllib.parse.urljoin(final, s) for s in page.scripts],
        "headings": page.headings[:20],
        "counts": {k: page.counts.get(k, 0) for k in ("img", "video", "svg", "canvas", "iframe", "section", "form", "button", "a")},
        "css_text_len": len(css),
        "css_errors": css_errors,
        "css_colors": dict(colors.most_common(80)),
        "css_font_families": dict(fam_counts.most_common(20)),
        "css_font_sizes": dict(css_declarations(css, "font-size").most_common(40)),
        "css_radii": dict(css_declarations(css, "border-radius").most_common(20)),
        "_html": html,
        "_css": css,
    }
