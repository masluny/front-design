"""Fluid type and space scales (Utopia method) and scale inference from measured sizes.

A step is interpolated between a small viewport (min) and a large viewport (max):
    size = clamp(min, intercept + slope * 100vw, max)
See https://utopia.fyi/blog/designing-with-fluid-type-scales/
"""
from __future__ import annotations

import math
from dataclasses import dataclass

SPACE_MULTIPLIERS = {
    "3xs": 0.25, "2xs": 0.5, "xs": 0.75, "s": 1.0, "m": 1.5,
    "l": 2.0, "xl": 3.0, "2xl": 4.0, "3xl": 6.0,
}
SPACE_PAIRS = [("s", "l"), ("m", "xl"), ("l", "2xl"), ("xl", "3xl")]

NAMED_RATIOS = {
    1.067: "minor second", 1.125: "major second", 1.2: "minor third", 1.25: "major third",
    1.333: "perfect fourth", 1.414: "augmented fourth", 1.5: "perfect fifth", 1.618: "golden ratio",
}


@dataclass
class Fluid:
    name: str
    min_px: float
    max_px: float
    min_vw: float
    max_vw: float

    def clamp(self, root_px: float = 16) -> str:
        lo, hi = sorted((self.min_px, self.max_px))
        if abs(self.max_px - self.min_px) < 0.01:
            return f"{_r(self.min_px / root_px)}rem"
        slope = (self.max_px - self.min_px) / (self.max_vw - self.min_vw)
        intercept = self.min_px - slope * self.min_vw
        sign = "-" if slope < 0 else "+"
        return (f"clamp({_r(lo / root_px)}rem, {_r(intercept / root_px)}rem {sign} {_r(abs(slope) * 100)}vw, "
                f"{_r(hi / root_px)}rem)")


def _r(x: float) -> str:
    return f"{x:.4f}".rstrip("0").rstrip(".") or "0"


def type_scale(min_base=16.0, max_base=19.0, min_ratio=1.2, max_ratio=1.25,
               min_vw=360.0, max_vw=1440.0, steps=(-2, 5)) -> list[Fluid]:
    lo, hi = steps
    out = []
    for step in range(lo, hi + 1):
        out.append(Fluid(f"step-{step}" if step >= 0 else f"step--{-step}",
                         min_base * min_ratio ** step, max_base * max_ratio ** step, min_vw, max_vw))
    return out


def space_scale(min_base=16.0, max_base=19.0, min_vw=360.0, max_vw=1440.0) -> list[Fluid]:
    out = [Fluid(f"space-{k}", min_base * m, max_base * m, min_vw, max_vw) for k, m in SPACE_MULTIPLIERS.items()]
    for a, b in SPACE_PAIRS:  # one-up pairs: grow more aggressively across viewports
        out.append(Fluid(f"space-{a}-{b}", min_base * SPACE_MULTIPLIERS[a], max_base * SPACE_MULTIPLIERS[b],
                         min_vw, max_vw))
    return out


def to_css(items: list[Fluid], root_px: float = 16, selector: str = ":root") -> str:
    lines = [f"{selector} {{"]
    for f in items:
        lines.append(f"  --{f.name}: {f.clamp(root_px)};  /* {f.min_px:.1f}px -> {f.max_px:.1f}px */")
    lines.append("}")
    return "\n".join(lines)


def nearest_named_ratio(r: float) -> tuple[float, str]:
    best = min(NAMED_RATIOS, key=lambda k: abs(k - r))
    return best, NAMED_RATIOS[best]


def infer_ratio(sizes_px: list[float], base_px: float | None = None) -> float | None:
    """Estimate a modular ratio from distinct heading/body sizes (largest first or any order)."""
    vals = sorted(s for s in sizes_px if s > 0)
    if base_px:
        vals = [v for v in vals if v >= base_px * 0.99]
    merged: list[float] = []  # merge sizes within 4% (rounding noise, fluid clamp at one viewport)
    for v in vals:
        if not merged or v / merged[-1] > 1.04:
            merged.append(v)
    if len(merged) < 3:
        return None
    ratios = sorted(b / a for a, b in zip(merged, merged[1:]))
    mid = len(ratios) // 2
    median = ratios[mid] if len(ratios) % 2 else math.sqrt(ratios[mid - 1] * ratios[mid])
    return round(median, 3)


def infer_base_unit(values_px: dict[float, int]) -> tuple[int | None, float]:
    """Which grid (4 or 8) explains the spacing values best. Returns (unit, share on-grid)."""
    total = sum(values_px.values())
    if not total:
        return None, 0.0
    best = (None, 0.0)
    for unit in (8, 4):
        on = sum(c for v, c in values_px.items() if abs(v / unit - round(v / unit)) < 0.06)
        share = on / total
        if share >= 0.6 and share > best[1] + (0.12 if unit == 4 else 0):
            best = (unit, share)
    if best[0] is None:
        on4 = sum(c for v, c in values_px.items() if abs(v / 4 - round(v / 4)) < 0.06) / total
        return None, round(on4, 3)
    return best[0], round(best[1], 3)
