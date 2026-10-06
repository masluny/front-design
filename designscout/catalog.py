"""Load and query the bundled knowledge: expert sources, galleries/exemplars, effects."""
from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).parent / "data"

PAGE_TYPES = ["landing", "saas", "ecommerce", "dashboard", "portfolio", "editorial", "docs", "app", "mobile-app"]

# Topics researched by default for each page type (order = priority).
TYPE_TOPICS = {
    "landing": ["hierarchy", "landing", "conversion", "typography", "color", "motion", "performance", "accessibility", "trust"],
    "saas": ["landing", "conversion", "hierarchy", "typography", "color", "navigation", "motion", "performance", "accessibility"],
    "ecommerce": ["ecommerce", "checkout", "forms", "navigation", "mobile", "performance", "trust", "accessibility"],
    "dashboard": ["dashboard", "data-viz", "hierarchy", "navigation", "empty-states", "forms", "accessibility", "dark-mode"],
    "portfolio": ["typography", "layout", "motion", "craft", "performance", "accessibility"],
    "editorial": ["typography", "layout", "content", "accessibility", "dark-mode", "performance"],
    "docs": ["navigation", "content", "typography", "accessibility", "dark-mode"],
    "app": ["usability", "forms", "navigation", "empty-states", "craft", "motion", "accessibility"],
    "mobile-app": ["mobile", "navigation", "motion", "forms", "onboarding", "accessibility"],
}

KIND_RANK = {"research": 0, "standard": 1, "guideline": 2, "craft": 3, "tool": 4, "web": 5}


@lru_cache(maxsize=None)
def _load(name: str) -> dict:
    with open(DATA / name, "rb") as fh:
        return tomllib.load(fh)


def sources() -> list[dict]:
    return _load("sources.toml")["source"]


def source_by_key(key: str) -> dict | None:
    return next((s for s in sources() if s["key"] == key), None)


def galleries() -> list[dict]:
    return _load("galleries.toml")["gallery"]


def exemplars() -> list[dict]:
    return _load("galleries.toml")["exemplar"]


def effects() -> list[dict]:
    return _load("effects.toml")["effect"]


def effect_by_key(key: str) -> dict | None:
    return next((e for e in effects() if e["key"] == key), None)


def effects_meta() -> dict:
    data = _load("effects.toml")
    return {"checked": data.get("checked"), "helpers": data.get("helpers", {})}


def _type_match(item_types: list[str], page_type: str | None) -> bool:
    return page_type is None or "*" in item_types or page_type in item_types


def find_sources(page_type: str | None = None, topics: list[str] | None = None) -> list[dict]:
    """Sources for a page type and/or topics, best evidence first."""
    wanted = set(topics or [])
    if page_type and not wanted:
        wanted = set(TYPE_TOPICS.get(page_type, []))
    priority = {t: i for i, t in enumerate(TYPE_TOPICS.get(page_type or "", []))}
    out = []
    for s in sources():
        if not _type_match(s.get("types", ["*"]), page_type):
            continue
        hits = wanted & set(s["topics"])
        if wanted and not hits:
            continue
        best_topic = min((priority.get(t, 99) for t in hits), default=99)
        out.append((best_topic, KIND_RANK.get(s["kind"], 9), s))
    out.sort(key=lambda t: (t[0], t[1]))
    return [s for _, _, s in out]


def find_galleries(page_type: str | None = None) -> list[dict]:
    return [g for g in galleries() if _type_match(g.get("types", ["*"]), page_type)]


def find_exemplars(page_type: str | None = None) -> list[dict]:
    return [e for e in exemplars() if _type_match(e.get("types", ["*"]), page_type)]


def find_effects(vibe: str | None = None, category: str | None = None, stack: str | None = None,
                 max_cost: str | None = None) -> list[dict]:
    costs = ["light", "medium", "heavy"]
    out = []
    for e in effects():
        if vibe and vibe not in e["vibes"]:
            continue
        if category and e["category"] != category:
            continue
        if stack and stack not in e["stacks"] and "any" not in e["stacks"]:
            continue
        if max_cost and costs.index(e["cost"]) > costs.index(max_cost):
            continue
        out.append(e)
    return out


def all_topics() -> list[str]:
    return sorted({t for s in sources() for t in s["topics"]})


def all_vibes() -> list[str]:
    return sorted({v for e in effects() for v in e["vibes"]})


def all_categories() -> list[str]:
    return sorted({e["category"] for e in effects()})
