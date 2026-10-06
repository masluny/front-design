"""CSS color parsing, WCAG contrast and perceptual clustering (stdlib only).

Colors are handled as (r, g, b, a) floats in 0..1 sRGB. Parsing covers what browsers
return from getComputedStyle (rgb/rgba, and since 2023 also oklch/oklab/lab/lch/color())
plus what people write in CSS (hex, hsl, named colors).
"""
from __future__ import annotations

import math
import re

RGBA = tuple[float, float, float, float]

NAMED = {
    "black": "#000000", "white": "#ffffff", "red": "#ff0000", "green": "#008000",
    "blue": "#0000ff", "yellow": "#ffff00", "orange": "#ffa500", "purple": "#800080",
    "gray": "#808080", "grey": "#808080", "silver": "#c0c0c0", "navy": "#000080",
    "teal": "#008080", "maroon": "#800000", "olive": "#808000", "lime": "#00ff00",
    "aqua": "#00ffff", "cyan": "#00ffff", "fuchsia": "#ff00ff", "magenta": "#ff00ff",
    "pink": "#ffc0cb", "brown": "#a52a2a", "gold": "#ffd700", "indigo": "#4b0082",
    "violet": "#ee82ee", "beige": "#f5f5dc", "ivory": "#fffff0", "whitesmoke": "#f5f5f5",
    "gainsboro": "#dcdcdc", "lightgray": "#d3d3d3", "darkgray": "#a9a9a9",
    "dimgray": "#696969", "slategray": "#708090", "tomato": "#ff6347", "coral": "#ff7f50",
}

_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?%?"
_FUNC_RE = re.compile(r"^(rgba?|hsla?|oklch|oklab|lab|lch|color)\((.*)\)$", re.I | re.S)
COLOR_TOKEN_RE = re.compile(
    r"#[0-9a-fA-F]{3,8}\b|(?:rgba?|hsla?|oklch|oklab|lab|lch)\([^()]*\)", re.I
)


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def _num(tok: str, scale: float = 1.0, pct_base: float = 1.0) -> float:
    tok = tok.strip()
    if tok.lower() == "none":
        return 0.0
    if tok.endswith("%"):
        return float(tok[:-1]) / 100.0 * pct_base
    return float(tok) * scale


def _hue(tok: str) -> float:
    tok = tok.strip().lower()
    if tok == "none":
        return 0.0
    for unit, factor in (("deg", 1.0), ("grad", 0.9), ("rad", 180 / math.pi), ("turn", 360.0)):
        if tok.endswith(unit):
            return float(tok[: -len(unit)]) * factor
    return float(tok)


def _split_args(body: str) -> tuple[list[str], str | None]:
    body = body.replace(",", " ")
    alpha = None
    if "/" in body:
        body, alpha = body.split("/", 1)
        alpha = alpha.strip()
    return body.split(), alpha


def _alpha(tok: str | None) -> float:
    if tok is None:
        return 1.0
    return _clamp(_num(tok))


# ------------------------------------------------------------------ conversions

def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c: float) -> float:
    c = _clamp(c, 0.0, 1.0)
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def oklab_to_rgb(L: float, a: float, b: float) -> tuple[float, float, float]:
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return linear_to_srgb(r), linear_to_srgb(g), linear_to_srgb(bb)


def rgb_to_oklab(r: float, g: float, b: float) -> tuple[float, float, float]:
    r, g, b = srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (math.copysign(abs(v) ** (1 / 3), v) for v in (l, m, s))
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def rgb_to_oklch(r: float, g: float, b: float) -> tuple[float, float, float]:
    L, a, bb = rgb_to_oklab(r, g, b)
    C = math.hypot(a, bb)
    H = math.degrees(math.atan2(bb, a)) % 360 if C > 1e-4 else 0.0
    return L, C, H


_BRADFORD_D50_D65 = (
    (0.9554734527042182, -0.023098536874261423, 0.0632593086610217),
    (-0.028369706963208136, 1.0099954580058226, 0.021041398966943008),
    (0.012314001688319899, -0.020507696433477912, 1.3303659366080753),
)
_XYZ65_TO_LSRGB = (
    (3.2409699419045226, -1.537383177570094, -0.4986107602930034),
    (-0.9692436362808796, 1.8759675015077202, 0.04155505740717559),
    (0.05563007969699366, -0.20397695888897652, 1.0569715142428786),
)
_P3_TO_XYZ65 = (
    (0.4865709486482162, 0.26566769316909306, 0.1982172852343625),
    (0.2289745640697488, 0.6917385218365064, 0.079286914093745),
    (0.0, 0.04511338185890264, 1.043944368900976),
)


def _mat(m, v):
    return tuple(sum(m[i][j] * v[j] for j in range(3)) for i in range(3))


def lab_to_rgb(L: float, a: float, b: float) -> tuple[float, float, float]:
    e, k = 216 / 24389, 24389 / 27
    fy = (L + 16) / 116
    fx, fz = a / 500 + fy, fy - b / 200
    xr = fx ** 3 if fx ** 3 > e else (116 * fx - 16) / k
    yr = ((L + 16) / 116) ** 3 if L > k * e else L / k
    zr = fz ** 3 if fz ** 3 > e else (116 * fz - 16) / k
    xyz50 = (xr * 0.96422, yr, zr * 0.82521)
    lin = _mat(_XYZ65_TO_LSRGB, _mat(_BRADFORD_D50_D65, xyz50))
    return tuple(linear_to_srgb(c) for c in lin)  # type: ignore[return-value]


def p3_to_rgb(r: float, g: float, b: float) -> tuple[float, float, float]:
    lin = _mat(_XYZ65_TO_LSRGB, _mat(_P3_TO_XYZ65, tuple(srgb_to_linear(c) for c in (r, g, b))))
    return tuple(linear_to_srgb(c) for c in lin)  # type: ignore[return-value]


def _hsl_to_rgb(h: float, s: float, l: float) -> tuple[float, float, float]:
    h = (h % 360) / 360
    if s == 0:
        return l, l, l

    def hue(p, q, t):
        t %= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    return hue(p, q, h + 1 / 3), hue(p, q, h), hue(p, q, h - 1 / 3)


# ------------------------------------------------------------------ parsing

def parse(value: str | None) -> RGBA | None:
    """Parse a CSS color string. Returns None for transparent/unknown/currentcolor."""
    if not value:
        return None
    s = value.strip().lower()
    if s in ("transparent", "none", "currentcolor", "inherit", "initial", "unset"):
        return None
    if s in NAMED:
        s = NAMED[s]
    if s.startswith("#"):
        h = s[1:]
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        if len(h) not in (6, 8) or not re.fullmatch(r"[0-9a-f]+", h):
            return None
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return (r, g, b, a)
    m = _FUNC_RE.match(s)
    if not m:
        return None
    fn, body = m.group(1), m.group(2)
    try:
        if fn == "color":
            parts, alpha = _split_args(body)
            space, nums = parts[0], parts[1:4]
            vals = [_num(n) for n in nums]
            if space in ("srgb", "srgb-linear"):
                rgb = vals if space == "srgb" else [linear_to_srgb(v) for v in vals]
            elif space == "display-p3":
                rgb = list(p3_to_rgb(*vals))
            else:
                return None
            return (*(_clamp(c) for c in rgb), _alpha(alpha))  # type: ignore[return-value]
        args, alpha = _split_args(body)
        if len(args) == 4 and alpha is None:  # legacy rgba(r, g, b, a)
            alpha = args.pop()
        if len(args) != 3:
            return None
        if fn in ("rgb", "rgba"):
            r, g, b = (_num(t, 1 / 255) for t in args)
            return (_clamp(r), _clamp(g), _clamp(b), _alpha(alpha))
        if fn in ("hsl", "hsla"):
            h = _hue(args[0])
            sat, lig = (_num(t if t.endswith("%") else t + "%") for t in args[1:])
            r, g, b = _hsl_to_rgb(h, _clamp(sat), _clamp(lig))
            return (r, g, b, _alpha(alpha))
        if fn == "oklch":
            L = _num(args[0])
            C = _num(args[1], 1.0, 0.4)
            H = _hue(args[2])
            a, b = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
            return (*oklab_to_rgb(L, a, b), _alpha(alpha))
        if fn == "oklab":
            L = _num(args[0])
            a, b = _num(args[1], 1.0, 0.4), _num(args[2], 1.0, 0.4)
            return (*oklab_to_rgb(L, a, b), _alpha(alpha))
        if fn == "lab":
            L = _num(args[0], 1.0, 100.0)
            a, b = _num(args[1], 1.0, 125.0), _num(args[2], 1.0, 125.0)
            return (*lab_to_rgb(L, a, b), _alpha(alpha))
        if fn == "lch":
            L = _num(args[0], 1.0, 100.0)
            C = _num(args[1], 1.0, 150.0)
            H = _hue(args[2])
            return (*lab_to_rgb(L, C * math.cos(math.radians(H)), C * math.sin(math.radians(H))), _alpha(alpha))
    except (ValueError, IndexError, ZeroDivisionError):
        return None
    return None


def to_hex(c: RGBA | tuple[float, float, float], alpha: bool = False) -> str:
    r, g, b = (round(_clamp(v) * 255) for v in c[:3])
    out = f"#{r:02x}{g:02x}{b:02x}"
    if alpha and len(c) == 4 and c[3] < 0.999:
        out += f"{round(c[3] * 255):02x}"
    return out


def blend(fg: RGBA, bg: RGBA | tuple[float, float, float]) -> RGBA:
    """Composite fg over an opaque bg."""
    a = fg[3]
    return (
        fg[0] * a + bg[0] * (1 - a),
        fg[1] * a + bg[1] * (1 - a),
        fg[2] * a + bg[2] * (1 - a),
        1.0,
    )


def luminance(c) -> float:
    r, g, b = (srgb_to_linear(_clamp(v)) for v in c[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(c1, c2) -> float:
    l1, l2 = luminance(c1), luminance(c2)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def wcag_level(ratio: float, large: bool = False) -> str:
    if large:
        return "AAA" if ratio >= 4.5 else "AA" if ratio >= 3 else "fail"
    return "AAA" if ratio >= 7 else "AA" if ratio >= 4.5 else "AA-large" if ratio >= 3 else "fail"


def chroma(c) -> float:
    return rgb_to_oklch(*c[:3])[1]


def distance(c1, c2) -> float:
    """Euclidean distance in OKLab (about 0.02 = just noticeable)."""
    a, b = rgb_to_oklab(*c1[:3]), rgb_to_oklab(*c2[:3])
    return math.dist(a, b)


def cluster(weighted: dict[str, float], threshold: float = 0.045, limit: int = 8) -> list[tuple[str, float]]:
    """Merge perceptually close colors. Input {css color: weight}; output [(hex, share)] by weight."""
    parsed = []
    for raw, w in weighted.items():
        c = parse(raw)
        if c is None or c[3] < 0.05 or w <= 0:
            continue
        parsed.append((c, w * (c[3] if c[3] < 1 else 1)))
    parsed.sort(key=lambda t: -t[1])
    groups: list[list] = []  # [color, weight]
    for c, w in parsed:
        for g in groups:
            if distance(g[0], c) < threshold:
                g[1] += w
                break
        else:
            groups.append([c, w])
    total = sum(g[1] for g in groups) or 1.0
    groups.sort(key=lambda g: -g[1])
    return [(to_hex(g[0]), round(g[1] / total, 4)) for g in groups[:limit]]


def describe(c) -> str:
    """Short human label like 'near-black', 'warm orange', 'cool gray'."""
    L, C, H = rgb_to_oklch(*c[:3])
    if C < 0.03:
        if L > 0.96:
            return "white"
        if L < 0.2:
            return "near-black"
        tone = "light gray" if L > 0.7 else "dark gray" if L < 0.4 else "gray"
        if C > 0.008:
            tone = ("warm " if 30 <= H <= 120 else "cool ") + tone
        return tone
    # OKLCH hue angles: red ~29, orange ~70, yellow ~110, green ~142, cyan ~195, blue ~264, magenta ~328
    names = [(10, "pink"), (40, "red"), (75, "orange"), (115, "yellow"), (135, "lime"), (165, "green"),
             (190, "teal"), (215, "cyan"), (245, "sky blue"), (275, "blue"), (310, "violet"),
             (345, "magenta"), (361, "pink")]
    name = next(n for limit, n in names if H < limit)
    shade = "pale " if L > 0.85 else "dark " if L < 0.4 else ""
    return shade + name
