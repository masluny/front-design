"""Design project folder: brief, research notes, references, direction, tokens, audit."""
from __future__ import annotations

import json
import re
import time
import tomllib
from pathlib import Path

from . import catalog, web

BRIEF = "brief.toml"

BRIEF_TEMPLATE = '''# front-design brief. Fill the empty fields before research (ask the user or state assumptions).

[brief]
title = {title}
summary = """
{summary}
"""
type = "{type}"          # {types}
stack = "{stack}"        # react-tailwind | next | vanilla | vue | astro | svelte | unknown
audience = ""            # who, in one sentence
primary_action = ""      # the ONE thing a visitor should do
brand_adjectives = []    # 3 words, e.g. ["calm", "precise", "warm"]
constraints = []         # existing brand colors/fonts, WCAG level, performance budget, languages...
competitors = []         # URLs of direct competitors (captured as references)
language = "{language}"

[research]
topics = {topics}
'''

PROJECT_DIRS = ["research", "refs", "build", "audit"]


class ProjectError(Exception):
    pass


def slugify(text: str, n: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:n].rstrip("-") or "design"


def find_root(start: Path | None = None) -> Path:
    p = (start or Path.cwd()).resolve()
    for cand in [p, *p.parents]:
        if (cand / BRIEF).exists():
            return cand
    raise ProjectError("no brief.toml found here or in a parent folder; run `front-design init \"<brief>\"` first")


def init(brief: str, directory: Path | None, page_type: str, stack: str, language: str = "en") -> Path:
    root = directory or Path("design") / slugify(brief)
    root.mkdir(parents=True, exist_ok=True)
    if (root / BRIEF).exists():
        raise ProjectError(f"{root / BRIEF} already exists")
    for d in PROJECT_DIRS:
        (root / d).mkdir(exist_ok=True)
    topics = catalog.TYPE_TOPICS.get(page_type, [])
    title = json.dumps(brief.strip().splitlines()[0][:80])
    (root / BRIEF).write_text(BRIEF_TEMPLATE.format(
        title=title, summary=brief.strip().replace('"""', "'''"), type=page_type, stack=stack,
        types=" | ".join(catalog.PAGE_TYPES), topics=json.dumps(topics), language=language))
    (root / "research" / "notes.json").write_text("[]\n")
    (root / "direction.md").write_text(DIRECTION_TEMPLATE)
    return root


def load_brief(root: Path) -> dict:
    with open(root / BRIEF, "rb") as fh:
        return tomllib.load(fh)


# ------------------------------------------------------------------ research notes

def notes_path(root: Path) -> Path:
    return root / "research" / "notes.json"


def load_notes(root: Path) -> list[dict]:
    p = notes_path(root)
    return json.loads(p.read_text()) if p.exists() else []


def save_notes(root: Path, notes: list[dict]):
    notes_path(root).write_text(json.dumps(notes, indent=2, ensure_ascii=False) + "\n")


_PAGE_CACHE: dict[str, str] = {}


def page_text(url: str) -> tuple[str, int]:
    if url not in _PAGE_CACHE:
        _, status, html = web.fetch(url)
        if web.looks_blocked(status, html):
            return "", status
        _PAGE_CACHE[url] = web.html_to_text(html)
        return _PAGE_CACHE[url], status
    return _PAGE_CACHE[url], 200


def add_note(root: Path, source: str, principle: str, quote: str | None, topic: str | None,
             verify: bool = True, title: str | None = None, kind: str | None = None) -> dict:
    src = catalog.source_by_key(source)
    if src:
        url, title, kind, key = src["url"], title or src["title"], kind or src["kind"], src["key"]
        author = src.get("author", "")
    elif source.startswith("http"):
        url, key, author = source, None, ""
        kind = kind or "web"
    else:
        raise ProjectError(f"unknown source '{source}': use a key from `front-design sources` or a full URL")
    status, score = "unchecked", None
    if quote and verify:
        try:
            text, http = page_text(url)
            if not text:
                status = f"unverifiable (HTTP {http} or bot wall)"
            else:
                status, score = web.verify_quote(quote, text)
                if not title:
                    m = re.match(r"\s*(.{5,120}?)\n", text)
                    title = m.group(1).strip() if m else url
        except web.FetchError as e:
            status = f"unverifiable ({e})"
    notes = load_notes(root)
    nid = f"P{max([int(n['id'][1:]) for n in notes if n['id'][1:].isdigit()] or [0]) + 1}"
    note = {"id": nid, "source_key": key, "url": url, "title": title or url, "author": author, "kind": kind,
            "topic": topic, "principle": principle, "quote": quote, "verified": status, "match": score,
            "added": time.strftime("%Y-%m-%d")}
    notes.append(note)
    save_notes(root, notes)
    return note


def remove_note(root: Path, nid: str) -> bool:
    notes = load_notes(root)
    kept = [n for n in notes if n["id"] != nid]
    save_notes(root, kept)
    return len(kept) != len(notes)


# ------------------------------------------------------------------ refs / effects

def load_refs(root: Path) -> list[dict]:
    out = []
    for tj in sorted((root / "refs").glob("*/tokens.json")):
        try:
            t = json.loads(tj.read_text())
        except json.JSONDecodeError:
            continue
        t["dir"] = str(tj.parent)
        notes = tj.parent / "notes.md"
        t["notes_md"] = notes.read_text() if notes.exists() else ""
        out.append(t)
    return out


def effects_path(root: Path) -> Path:
    return root / "effects.json"


def load_picks(root: Path) -> list[dict]:
    p = effects_path(root)
    return json.loads(p.read_text()) if p.exists() else []


def pick_effect(root: Path, key: str, role: str, why: str) -> dict:
    eff = catalog.effect_by_key(key)
    if not eff:
        raise ProjectError(f"unknown effect '{key}' (see `front-design effects`)")
    picks = [p for p in load_picks(root) if p["key"] != key]
    if role == "signature":
        for p in picks:
            if p["role"] == "signature":
                p["role"] = "support"
    pick = {"key": key, "name": f"{eff['library']}: {eff['name']}", "role": role, "why": why,
            "package": eff["package"], "version": eff["version"], "url": eff["url"]}
    picks.append(pick)
    effects_path(root).write_text(json.dumps(picks, indent=2) + "\n")
    return pick


DIRECTION_TEMPLATE = """# Design direction

<!-- Write this after research. Every decision should point to a principle (P#) or a reference (refs/<slug>). -->

## Options considered

### A. <name>
- Idea:
- Draws from: refs/...
- Honors: P#, P#
- Risk:

### B. <name>

### C. <name>

## Chosen direction and why

## Tokens
- Type: display <family>, text <family>; scale ratio <r> (front-design scale ...)
- Color: background, surface, text, muted, accent (contrast checked with front-design contrast)
- Space: base unit, section rhythm
- Shape: radius, borders, shadows

## Layout and sections
1. Hero:
2.
3.

## Signature effect and motion
- Signature: <effect key> (why, where, reduced-motion fallback)
- Supporting:
- Motion rules: durations, easing

## Principle checklist (fill during critique)
| Principle | Where it is honored | Status |
|---|---|---|
"""
