"""Detect frameworks, effect libraries and font services on a page.

Signals: script URLs, HTML markup, CSS text, window globals (rendered mode only) and the
generator meta tag. Each rule lists regexes per signal; any hit counts.
"""
from __future__ import annotations

import re

# name, group, {signal: [regex, ...]}
RULES: list[tuple[str, str, dict[str, list[str]]]] = [
    # --- effects / motion
    ("Paper Shaders", "effects", {"html": [r"data-paper-shader"], "script": [r"paper-design/shaders"]}),
    ("Unicorn Studio", "effects", {"html": [r"data-us-project"], "script": [r"unicornstudio", r"unicorn\.studio"], "global": ["UnicornStudio"]}),
    ("GSAP", "effects", {"script": [r"/gsap(?:@|/|\.min\.js|\.js)", r"greensock"], "global": ["gsap", "TweenMax"]}),
    ("GSAP ScrollTrigger", "effects", {"script": [r"ScrollTrigger"], "global": ["ScrollTrigger"]}),
    ("Lenis", "effects", {"html": [r"<html[^>]*class=\"[^\"]*\blenis\b"], "script": [r"/lenis(?:@|/|\.min)"], "global": ["lenis", "Lenis"]}),
    ("Locomotive Scroll", "effects", {"html": [r"data-scroll-container"], "script": [r"locomotive-scroll"]}),
    ("three.js", "effects", {"script": [r"/three(?:@[\d.]+)?(?:/build)?/three(?:\.module)?(?:\.min)?\.js", r"three\.module"], "global": ["__THREE__", "THREE"]}),
    ("Spline", "effects", {"html": [r"<spline-viewer", r"prod\.spline\.design"], "script": [r"splinetool", r"spline-viewer"]}),
    ("Rive", "effects", {"script": [r"rive-app", r"/rive(?:\.min)?\.js"], "html": [r"\.riv[\"']"]}),
    ("Lottie", "effects", {"html": [r"<lottie-player", r"<dotlottie-player", r"<dotlottie-wc", r"\.lottie[\"']"], "script": [r"lottie"], "global": ["lottie", "bodymovin"]}),
    ("PixiJS", "effects", {"script": [r"pixi(?:\.min)?\.js"], "global": ["PIXI"]}),
    ("p5.js", "effects", {"script": [r"/p5(?:\.min)?\.js"], "global": ["p5"]}),
    ("Matter.js", "effects", {"script": [r"matter(?:\.min)?\.js"], "global": ["Matter"]}),
    ("Swiper", "effects", {"html": [r"swiper-wrapper"], "script": [r"swiper"]}),
    ("Splide", "effects", {"html": [r"class=\"[^\"]*\bsplide\b"]}),
    ("Barba.js", "effects", {"html": [r"data-barba"]}),
    ("Swup", "effects", {"html": [r"id=\"swup\"", r"data-swup"]}),
    ("AOS", "effects", {"html": [r"data-aos="]}),
    ("Splitting.js", "effects", {"html": [r"data-splitting"]}),
    ("View Transitions", "effects", {"css": [r"view-transition"]}),
    ("CSS scroll-driven animations", "effects", {"css": [r"animation-timeline"]}),
    # --- frameworks / builders
    ("Next.js", "framework", {"html": [r"/_next/static", r"__NEXT_DATA__", r"next-route-announcer"], "global": ["__NEXT_DATA__", "next"]}),
    ("Nuxt", "framework", {"html": [r"/_nuxt/", r"__NUXT__"], "global": ["__NUXT__"]}),
    ("Astro", "framework", {"html": [r"<astro-island", r"/_astro/"]}),
    ("SvelteKit", "framework", {"html": [r"/_app/immutable", r"__sveltekit"]}),
    ("Gatsby", "framework", {"html": [r"___gatsby"]}),
    ("Remix / React Router", "framework", {"html": [r"__remixContext", r"__reactRouterContext"]}),
    ("Framer (site builder)", "framework", {"generator": [r"framer"], "html": [r"framerusercontent\.com"]}),
    ("Webflow", "framework", {"html": [r"data-wf-page", r"data-wf-site"], "generator": [r"webflow"], "global": ["Webflow"]}),
    ("WordPress", "framework", {"html": [r"/wp-content/", r"/wp-includes/"], "generator": [r"wordpress"]}),
    ("Shopify", "framework", {"html": [r"cdn\.shopify\.com", r"Shopify\.theme"], "global": ["Shopify"]}),
    ("Squarespace", "framework", {"html": [r"static1\.squarespace\.com"], "generator": [r"squarespace"]}),
    ("Wix", "framework", {"html": [r"static\.wixstatic\.com"], "generator": [r"wix"]}),
    ("Alpine.js", "framework", {"html": [r"\sx-data="]}),
    ("htmx", "framework", {"html": [r"\shx-(?:get|post|boost)="]}),
    ("jQuery", "framework", {"script": [r"jquery"], "global": ["jQuery"]}),
    # --- styling / components
    ("Tailwind CSS", "styling", {"css": [r"--tw-", r"tailwindcss"]}),
    ("Radix UI", "styling", {"html": [r"data-radix-"]}),
    ("shadcn/ui (likely)", "styling", {"html": [r"data-slot=\"(?:button|card|dialog|input|badge)\""]}),
    ("Headless UI", "styling", {"html": [r"data-headlessui-state"]}),
    ("Bootstrap", "styling", {"css": [r"--bs-body-"], "script": [r"bootstrap(?:\.bundle)?(?:\.min)?\.js"]}),
    # --- fonts / media
    ("Google Fonts", "fonts", {"html": [r"fonts\.googleapis\.com", r"fonts\.gstatic\.com"], "css": [r"fonts\.gstatic\.com"]}),
    ("Adobe Fonts", "fonts", {"html": [r"use\.typekit\.net", r"p\.typekit\.net"]}),
    ("Fontshare", "fonts", {"html": [r"api\.fontshare\.com"]}),
    ("Vercel Geist font", "fonts", {"css": [r"Geist"]}),
    ("YouTube embed", "media", {"html": [r"youtube(?:-nocookie)?\.com/embed"]}),
    ("Vimeo embed", "media", {"html": [r"player\.vimeo\.com"]}),
    ("Mux video", "media", {"html": [r"stream\.mux\.com", r"<mux-player"]}),
]


def detect(scripts: list[str] | None = None, html: str = "", css: str = "",
           globals_: list[str] | None = None, generator: str = "") -> dict[str, list[str]]:
    """Return {group: [library names]}."""
    signals = {
        "script": "\n".join(scripts or []),
        "html": html or "",
        "css": css or "",
        "generator": (generator or "").lower(),
    }
    gl = set(globals_ or [])
    found: dict[str, list[str]] = {}
    for name, group, rules in RULES:
        hit = False
        for signal, patterns in rules.items():
            if signal == "global":
                hit = any(g in gl for g in patterns)
            else:
                text = signals.get(signal, "")
                hit = any(re.search(p, text, re.I) for p in patterns) if text else False
            if hit:
                break
        if hit:
            found.setdefault(group, []).append(name)
    return found


GLOBALS_TO_PROBE = sorted({g for _, _, r in RULES for g in r.get("global", [])})
