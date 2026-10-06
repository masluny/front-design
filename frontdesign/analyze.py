"""Turn raw page data (rendered or static) into a compact design-token summary."""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from . import color, fingerprints, scale, web

GENERIC = {"serif", "sans-serif", "monospace", "system-ui", "ui-sans-serif", "ui-serif", "ui-monospace",
           "cursive", "fantasy", "-apple-system", "blinkmacsystemfont"}
MONO_HINT = re.compile(r"mono|code|consol|courier|menlo|jetbrains|fira code|ibm plex mono|sf mono", re.I)
SERIF_HINT = re.compile(r"serif|garamond|times|georgia|tiempos|playfair|lora|merriweather|caslon|"
                        r"baskerville|didot|bodoni|freight|canela|editorial|fraunces|newsreader|instrument serif|"
                        r"source serif|ibm plex serif|libre|domaine|gt super|reckless|signifier", re.I)
TAILWIND_DEFAULT_ACCENTS = {"#6366f1", "#4f46e5", "#8b5cf6", "#7c3aed", "#a855f7", "#9333ea"}


def _px(v: str | None) -> float | None:
    if not v:
        return None
    m = re.match(r"^(-?\d+(?:\.\d+)?)px$", v.strip())
    return float(m.group(1)) if m else None


def classify_font(family: str, stack: str = "") -> str:
    s = f"{family} {stack}"
    if MONO_HINT.search(s):
        return "mono"
    if "sans-serif" in stack.lower() or re.search(r"\bsans\b|grotesk|grotesque|helvetica|inter\b|geist|arial", s, re.I):
        return "sans"
    if SERIF_HINT.search(s):
        return "serif"
    return "sans" if not stack else "display/other"


def _share(counter: dict, limit: int = 10, min_share: float = 0.0) -> list[tuple[str, float]]:
    total = sum(counter.values()) or 1
    items = sorted(counter.items(), key=lambda kv: -kv[1])
    return [(k, round(v / total, 3)) for k, v in items[:limit] if v / total >= min_share]


def summarize(raw: dict) -> dict:
    if raw.get("mode") == "static":
        return _summarize_static(raw)
    return _summarize_rendered(raw)


# ------------------------------------------------------------------ rendered

def _summarize_rendered(raw: dict) -> dict:
    text_rows = []
    for key, chars in raw.get("text", {}).items():
        fam, size, weight, lh, ls, col, transform, role, stack = (key.split("|") + [""] * 9)[:9]
        text_rows.append(dict(family=fam, size=_px(size), weight=weight, lh=lh, ls=ls, color=col,
                              transform=transform, role=role, stack=stack, chars=chars))
    total_chars = sum(r["chars"] for r in text_rows) or 1

    # fonts
    fam_chars = Counter()
    fam_roles: dict[str, Counter] = defaultdict(Counter)
    fam_weights: dict[str, set] = defaultdict(set)
    fam_stack = {}
    for r in text_rows:
        fam_chars[r["family"]] += r["chars"]
        fam_roles[r["family"]][r["role"]] += r["chars"]
        fam_weights[r["family"]].add(r["weight"])
        fam_stack.setdefault(r["family"], r["stack"])
    fonts = []
    for fam, ch in fam_chars.most_common(6):
        roles = fam_roles[fam]
        heading_chars = sum(v for k, v in roles.items() if k.startswith("h"))
        role = ("headings" if heading_chars > 0.5 * ch else "code" if roles.get("code", 0) > 0.5 * ch
                else "body/ui")
        fonts.append({"family": fam, "share": round(ch / total_chars, 3), "role": role,
                      "class": classify_font(fam, fam_stack.get(fam, "")),
                      "weights": sorted(fam_weights[fam], key=lambda w: int(w) if w.isdigit() else 0)})
    heading_fams = Counter()
    for h in raw.get("headings", []):
        heading_fams[h.get("family", "")] += 1

    # type sizes
    body_rows = [r for r in text_rows if r["role"] in ("text", "small", "link") and r["size"]]
    size_chars = Counter()
    for r in body_rows:
        size_chars[r["size"]] += r["chars"]
    body_px = size_chars.most_common(1)[0][0] if size_chars else None
    body_row = max((r for r in body_rows if r["size"] == body_px), key=lambda r: r["chars"], default=None)
    lh_ratio = None
    if body_row and _px(body_row["lh"]) and body_px:
        lh_ratio = round(_px(body_row["lh"]) / body_px, 2)
    heading_sizes = sorted({_px(h["size"]) for h in raw.get("headings", []) if _px(h["size"])}, reverse=True)
    all_sizes = Counter()
    for r in text_rows:
        if r["size"]:
            all_sizes[round(r["size"])] += r["chars"]
    distinct_sizes = [s for s, c in all_sizes.items() if c / total_chars >= 0.01]
    ratio = scale.infer_ratio(heading_sizes + ([body_px] if body_px else []), base_px=body_px)
    named = scale.nearest_named_ratio(ratio) if ratio else None

    # colors
    bg = color.cluster(raw.get("bg", {}), limit=6)
    page_bg = None
    for cand in (raw.get("page_bg"), raw.get("root_bg")):
        c = color.parse(cand)
        if c and c[3] > 0.5:
            page_bg = c
            break
    if page_bg is None:  # transparent body: the largest painted surface decides
        page_bg = color.parse(bg[0][0]) if bg else (1.0, 1.0, 1.0, 1.0)
    text_colors = Counter()
    for r in text_rows:
        text_colors[r["color"]] += r["chars"]
    text_pal = color.cluster(dict(text_colors), limit=6)
    accent_votes = Counter()
    for c in raw.get("ctas", []):
        for v in (c.get("bg"), c.get("color")):
            p = color.parse(v)
            if p and p[3] > 0.5 and color.chroma(p) > 0.06:
                accent_votes[color.to_hex(p)] += 2 if c.get("above_fold") else 1
    for r in text_rows:
        p = color.parse(r["color"])
        if r["role"] in ("link", "button") and p and color.chroma(p) > 0.06:
            accent_votes[color.to_hex(p)] += 0.5
    for hexv, share in bg:
        p = color.parse(hexv)
        if p and color.chroma(p) > 0.08:
            accent_votes[hexv] += share * 4
    accents = color.cluster(dict(accent_votes), limit=4)
    body_color = color.parse(body_row["color"]) if body_row else None
    body_contrast = round(color.contrast(color.blend(body_color, page_bg), page_bg), 2) if body_color else None
    dark = color.luminance(page_bg) < 0.2

    # spacing / shape
    spacing_px = Counter()
    for k, v in list(raw.get("spacing", {}).items()) + list(raw.get("gaps", {}).items()):
        px = _px(k)
        if px and 0 < px <= 400:
            spacing_px[round(px, 1)] += v
    unit, on_grid = scale.infer_base_unit(dict(spacing_px))
    radii = [(k, s) for k, s in _share(raw.get("radii", {}), 5, 0.04)]
    shadows = _share(raw.get("shadows", {}), 3, 0.0)
    maxw = sorted(((_px(k), v) for k, v in raw.get("maxw", {}).items() if _px(k)), key=lambda t: -t[1])
    content_width = maxw[0][0] if maxw else None

    css = raw.get("css_text", "") + "\n" + raw.get("_css_extra", "")
    feats = web.css_features(css)
    root_vars = web.root_variables(css)
    libs = fingerprints.detect(scripts=raw.get("scripts"), html=raw.get("_html", ""), css=css,
                               globals_=raw.get("globals"), generator=raw.get("meta", {}).get("generator", ""))
    notes = []
    if accents and accents[0][0] in TAILWIND_DEFAULT_ACCENTS:
        notes.append("dominant accent is a stock Tailwind indigo/violet")
    if raw.get("center_paragraphs", 0) > 2:
        notes.append(f"{raw['center_paragraphs']} centered multi-line paragraphs")

    return {
        "mode": "rendered",
        "url": raw.get("url"),
        "final_url": raw.get("final_url"),
        "title": raw.get("title", "").strip(),
        "description": raw.get("meta", {}).get("description", ""),
        "lang": raw.get("lang", ""),
        "blocked": raw.get("blocked", False),
        "theme": "dark" if dark else "light",
        "fonts": fonts,
        "fonts_loaded": sorted({f["family"] for f in raw.get("fonts_loaded", [])})[:12],
        "type": {
            "body_px": body_px,
            "body_line_height": lh_ratio,
            "h1_px": heading_sizes[0] if heading_sizes else None,
            "heading_sizes_px": heading_sizes[:8],
            "ratio": ratio,
            "ratio_name": f"~{named[1]} ({named[0]})" if named else None,
            "distinct_sizes": len(distinct_sizes),
            "heading_tracking": [h.get("tracking") for h in raw.get("headings", [])[:3]],
            "uppercase_share": round(sum(r["chars"] for r in text_rows if r["transform"] == "uppercase") / total_chars, 3),
        },
        "palette": {
            "page_bg": color.to_hex(page_bg),
            "backgrounds": bg,
            "text": text_pal,
            "accents": accents,
            "body_text_contrast": body_contrast,
            "gradients": raw.get("gradients", 0),
            "border_colors": [h for h, _ in color.cluster(raw.get("borders", {}), limit=3)],
        },
        "spacing": {"base_unit": unit, "on_grid_share": on_grid,
                    "common_px": [p for p, _ in spacing_px.most_common(10)]},
        "shape": {"radii": radii, "shadows": [s for s, _ in shadows], "shadow_count": len(raw.get("shadows", {}))},
        "layout": {"content_width_px": content_width, "sections": raw.get("counts", {}).get("sections"),
                   "sticky_header": raw.get("sticky_header"), "page_height_px": raw.get("doc", {}).get("height"),
                   "viewports_tall": round(raw.get("doc", {}).get("height", 0) / max(1, raw.get("doc", {}).get("viewport_h", 900)), 1)},
        "content": {"headings": raw.get("headings", [])[:12], "ctas": raw.get("ctas", []), "nav": raw.get("nav", [])},
        "media": raw.get("counts", {}),
        "motion": {"running_animations": raw.get("animations_running", 0), "keyframes": feats.get("keyframes", 0),
                   "reduced_motion_css": feats.get("reduced_motion_media", 0) > 0},
        "css_features": {k: v for k, v in feats.items() if v},
        "css_variables": dict(list(root_vars.items())[:80]),
        "css_variable_count": len(root_vars),
        "libraries": libs,
        "perf": raw.get("perf", {}),
        "notes": notes,
    }


# ------------------------------------------------------------------ static

def _summarize_static(raw: dict) -> dict:
    css = raw.get("_css", "")
    feats = web.css_features(css)
    root_vars = web.root_variables(css)
    fams = raw.get("css_font_families", {})
    fonts = [{"family": f, "share": s, "role": "?", "class": classify_font(f)} for f, s in _share(fams, 5)]
    sizes = []
    for v, c in raw.get("css_font_sizes", {}).items():
        px = _px(v)
        if px is None:
            m = re.match(r"^(\d*\.?\d+)rem$", v.strip())
            px = float(m.group(1)) * 16 if m else None
        if px:
            sizes.extend([px] * c)
    size_counts = Counter(round(s) for s in sizes)
    pal = color.cluster(raw.get("css_colors", {}), limit=10)
    accents = [(h, s) for h, s in pal if (p := color.parse(h)) and color.chroma(p) > 0.08][:4]
    libs = fingerprints.detect(scripts=raw.get("scripts"), html=raw.get("_html", ""), css=css,
                               generator=raw.get("meta", {}).get("generator", ""))
    return {
        "mode": "static",
        "url": raw.get("url"),
        "final_url": raw.get("final_url"),
        "title": raw.get("title", ""),
        "description": raw.get("meta", {}).get("description", ""),
        "lang": raw.get("lang", ""),
        "blocked": raw.get("blocked", False),
        "theme": "?",
        "fonts": fonts,
        "font_faces": web.font_faces(css)[:12],
        "type": {"common_sizes_px": [s for s, _ in size_counts.most_common(10)],
                 "ratio": scale.infer_ratio(list(size_counts)),
                 "note": "from CSS declarations, not weighted by on-screen use"},
        "palette": {"declared": pal, "accents": accents,
                    "note": "frequency in CSS, not area on screen"},
        "shape": {"radii": _share(raw.get("css_radii", {}), 5)},
        "content": {"headings": raw.get("headings", [])[:12]},
        "media": raw.get("counts", {}),
        "motion": {"keyframes": feats.get("keyframes", 0), "reduced_motion_css": feats.get("reduced_motion_media", 0) > 0},
        "css_features": {k: v for k, v in feats.items() if v},
        "css_variables": dict(list(root_vars.items())[:80]),
        "css_variable_count": len(root_vars),
        "libraries": libs,
        "css_errors": raw.get("css_errors", []),
        "notes": ["static mode: install Playwright for screenshots and computed styles"],
    }


# ------------------------------------------------------------------ text report

def _fmt_pal(items) -> str:
    out = []
    for h, s in items:
        p = color.parse(h)
        out.append(f"{h} {color.describe(p)} {round(s * 100)}%" if p else h)
    return ", ".join(out)


def to_markdown(t: dict, shots: dict | None = None) -> str:
    L = [f"# {t.get('title') or t.get('url')}", "", f"- URL: {t.get('final_url') or t.get('url')}",
         f"- Mode: {t['mode']}" + (" (BLOCKED: bot protection or error page; do not trust the data)" if t.get("blocked") else "")]
    if t.get("description"):
        L.append(f"- Description: {t['description'][:200]}")
    L.append(f"- Theme: {t.get('theme')}")
    if t.get("fonts"):
        L += ["", "## Typography"]
        for f in t["fonts"]:
            w = f" weights {', '.join(f['weights'])}" if f.get("weights") else ""
            L.append(f"- {f['family']} ({f['class']}, {f['role']}, {round(f['share'] * 100)}% of text){w}")
        ty = t.get("type", {})
        if ty.get("body_px"):
            L.append(f"- Body {ty['body_px']:g}px / line-height {ty.get('body_line_height')}; "
                     f"H1 {ty.get('h1_px')}px; scale ratio {ty.get('ratio')} {ty.get('ratio_name') or ''}; "
                     f"{ty.get('distinct_sizes')} distinct sizes in use")
        elif ty.get("common_sizes_px"):
            L.append(f"- Declared sizes (px): {ty['common_sizes_px']}")
    pal = t.get("palette", {})
    if pal:
        L += ["", "## Color"]
        if "backgrounds" in pal:
            L.append(f"- Page background {pal['page_bg']}; surfaces: {_fmt_pal(pal['backgrounds'])}")
            L.append(f"- Text: {_fmt_pal(pal['text'])}")
            L.append(f"- Body text contrast: {pal.get('body_text_contrast')}:1")
        if pal.get("declared"):
            L.append(f"- Declared: {_fmt_pal(pal['declared'])}")
        if pal.get("accents"):
            L.append(f"- Accent(s): {_fmt_pal(pal['accents'])}")
        if pal.get("gradients"):
            L.append(f"- Gradient backgrounds: {pal['gradients']}")
    sp = t.get("spacing")
    if sp:
        L += ["", "## Space and shape", f"- Base unit: {sp['base_unit'] or 'none'} (on-grid {round(sp['on_grid_share'] * 100)}%); common: {sp['common_px']}"]
    sh = t.get("shape", {})
    if sh.get("radii"):
        L.append(f"- Radii: {', '.join(f'{r} ({round(s * 100)}%)' for r, s in sh['radii'])}")
    if sh.get("shadow_count") is not None:
        L.append(f"- Distinct shadows: {sh['shadow_count']}")
    lay = t.get("layout")
    if lay:
        L.append(f"- Content width: {lay['content_width_px']}px; sections: {lay['sections']}; "
                 f"sticky header: {lay['sticky_header']}; page height: {lay['viewports_tall']} viewports")
    c = t.get("content", {})
    if c.get("headings"):
        L += ["", "## Content"]
        for h in c["headings"][:8]:
            L.append(f"- {h['tag']}: {h['text']}" + (f" ({h['size']})" if h.get("size") else ""))
    if c.get("ctas"):
        L.append("- CTAs: " + "; ".join(f"\"{x['text']}\" ({x.get('style', '?')}, r={x.get('radius')}, h={x.get('height')}px)" for x in c["ctas"][:6]))
    if c.get("nav"):
        L.append("- Nav: " + " | ".join(c["nav"][:10]))
    libs = t.get("libraries", {})
    if libs:
        L += ["", "## Stack and effects"]
        for g, names in libs.items():
            L.append(f"- {g}: {', '.join(names)}")
    m = t.get("media", {})
    if m:
        L.append("- Media: " + ", ".join(f"{k} {v}" for k, v in m.items() if v))
    mo = t.get("motion", {})
    if mo:
        L.append(f"- Motion: {mo.get('running_animations', '?')} running animations, {mo.get('keyframes')} @keyframes, "
                 f"reduced-motion CSS: {mo.get('reduced_motion_css')}")
    if t.get("css_features"):
        L.append("- Modern CSS: " + ", ".join(f"{k} ({v})" for k, v in t["css_features"].items()))
    if t.get("css_variable_count"):
        L.append(f"- {t['css_variable_count']} CSS custom properties on :root (see tokens.json)")
    p = t.get("perf", {})
    if p:
        L.append(f"- Perf (this run, unthrottled): LCP {p.get('lcp_ms')} ms ({p.get('lcp_element')}), CLS {p.get('cls')}, "
                 f"{p.get('requests')} requests, {p.get('transfer_kb')} kB")
    if t.get("notes"):
        L += ["", "## Notes"] + [f"- {n}" for n in t["notes"]]
    if shots:
        L += ["", "## Screenshots"]
        for k, files in shots.items():
            L.append(f"- {k}: " + ", ".join(files))
    return "\n".join(L) + "\n"
