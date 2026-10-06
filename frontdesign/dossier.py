"""Compile a design project into one self-contained HTML dossier (images referenced relatively)."""
from __future__ import annotations

import html
import json
import re
import time
from pathlib import Path

from . import color, project

# ------------------------------------------------------------------ tiny markdown

def _inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*\s][^*]*)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+|[^)\s]+)\)", r'<a href="\2">\1</a>', s)
    return s


def markdown(md: str) -> str:
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            buf = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            out.append(f"<pre><code>{html.escape(chr(10).join(buf))}</code></pre>")
            i += 1
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            lvl = min(len(m.group(1)) + 1, 5)
            out.append(f"<h{lvl}>{_inline(m.group(2))}</h{lvl}>")
            i += 1
            continue
        if line.strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            head = [c.strip() for c in line.strip().strip("|").split("|")]
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            t = "<table><thead><tr>" + "".join(f"<th>{_inline(h)}</th>" for h in head) + "</tr></thead><tbody>"
            t += "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in rows)
            out.append(t + "</tbody></table>")
            continue
        if re.match(r"^\s*([-*]|\d+\.)\s+", line):
            tag = "ol" if re.match(r"^\s*\d+\.", line) else "ul"
            items = []
            while i < len(lines) and re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
                items.append(re.sub(r"^\s*([-*]|\d+\.)\s+", "", lines[i]))
                i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{_inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        if not line.strip():
            i += 1
            continue
        buf = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,4}\s|```|\s*([-*]|\d+\.)\s|\s*\|)", lines[i]):
            buf.append(lines[i])
            i += 1
        out.append(f"<p>{_inline(' '.join(buf))}</p>")
    return "\n".join(out)


# ------------------------------------------------------------------ helpers

def _swatches(items) -> str:
    out = []
    for h, share in items:
        p = color.parse(h)
        label = f"{h} {round(share * 100)}%" if isinstance(share, float) else h
        title = color.describe(p) if p else ""
        out.append(f'<span class="sw" title="{html.escape(title)}"><i style="background:{h}"></i>{html.escape(label)}</span>')
    return "".join(out)


def _rel(root: Path, p: Path) -> str:
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)


def _parse_tokens_css(text: str) -> dict[str, str]:
    return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", text))


def _find_tokens_css(root: Path) -> Path | None:
    for cand in [root / "tokens.css", root / "build" / "tokens.css", *root.glob("build/**/tokens.css")]:
        if cand.exists():
            return cand
    return None


# ------------------------------------------------------------------ build

CSS = """
:root{--bg:#f7f6f3;--surface:#fff;--text:#16161a;--muted:#5d5d66;--line:#e4e2dc;--accent:#d2552f;--ok:#1f7a4d;--warn:#a86500;--bad:#b42318;
--mono:ui-monospace,SFMono-Regular,Menlo,monospace;--sans:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;--serif:"Iowan Old Style","Palatino Linotype",Georgia,serif}
@media (prefers-color-scheme:dark){:root{--bg:#121214;--surface:#1b1b1f;--text:#ecebe8;--muted:#a3a2ab;--line:#2c2c33;--accent:#ff7a4f;--ok:#4cc38a;--warn:#f5a524;--bad:#ff6b5e}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.55 var(--sans)}
main{max-width:1180px;margin:0 auto;padding:clamp(16px,4vw,48px)}
header.top{padding:40px 0 24px;border-bottom:1px solid var(--line);margin-bottom:32px}
header.top h1{font:600 clamp(2rem,1.4rem + 2.6vw,3.4rem)/1.05 var(--serif);margin:0 0 12px;letter-spacing:-.02em;text-wrap:balance}
.meta{color:var(--muted);font-size:.9rem;display:flex;flex-wrap:wrap;gap:8px 18px}
nav.toc{display:flex;flex-wrap:wrap;gap:6px;margin:18px 0 0}nav.toc a{font-size:.85rem;padding:4px 10px;border:1px solid var(--line);border-radius:99px;color:var(--text);text-decoration:none}
section{margin:0 0 56px}section>h2{font:600 1.5rem/1.2 var(--serif);margin:0 0 6px}section>p.lede{color:var(--muted);margin:0 0 20px;max-width:70ch}
.grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(min(100%,340px),1fr))}
.card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px;min-width:0}
.card h3{margin:0 0 6px;font-size:1.05rem}.card .sub{color:var(--muted);font-size:.85rem;word-break:break-all}
.shot{display:block;width:100%;aspect-ratio:16/10;object-fit:cover;object-position:top;border-radius:10px;border:1px solid var(--line);margin:0 0 12px;background:var(--line)}
.thumbs{display:flex;gap:6px;overflow-x:auto;margin:-4px 0 10px}.thumbs img{height:64px;border-radius:6px;border:1px solid var(--line)}
.sw{display:inline-flex;align-items:center;gap:6px;font:12px/1 var(--mono);margin:0 10px 6px 0}.sw i{width:18px;height:18px;border-radius:5px;border:1px solid var(--line);display:inline-block}
.chips{display:flex;flex-wrap:wrap;gap:6px}.chip{font-size:.75rem;padding:3px 8px;border-radius:99px;background:color-mix(in oklab,var(--accent) 12%,transparent);color:var(--text)}
dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 12px;margin:8px 0;font-size:.9rem}dt{color:var(--muted)}dd{margin:0;min-width:0}
blockquote{margin:8px 0;padding:8px 12px;border-left:3px solid var(--accent);background:color-mix(in oklab,var(--accent) 6%,transparent);border-radius:0 8px 8px 0;font-family:var(--serif)}
.badge{font:600 11px/1 var(--sans);padding:4px 7px;border-radius:6px;text-transform:uppercase;letter-spacing:.04em;white-space:nowrap}
.b-exact{background:color-mix(in oklab,var(--ok) 18%,transparent);color:var(--ok)}.b-close{background:color-mix(in oklab,var(--warn) 18%,transparent);color:var(--warn)}
.b-bad{background:color-mix(in oklab,var(--bad) 16%,transparent);color:var(--bad)}.b-kind{border:1px solid var(--line);color:var(--muted)}
.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:.85rem}th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{color:var(--muted);font-weight:600}
.prose{max-width:76ch}.prose h3,.prose h4{font-family:var(--serif);margin:1.4em 0 .4em}
code{font-family:var(--mono);font-size:.88em}pre{overflow-x:auto;background:var(--surface);border:1px solid var(--line);padding:12px;border-radius:10px}
.score{font:700 3rem/1 var(--serif)}.pass{color:var(--ok)}.fail{color:var(--bad)}
.finding{border-top:1px solid var(--line);padding:10px 0}.finding:first-child{border-top:0}.finding small{color:var(--muted)}
.steps div{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-family:var(--serif);line-height:1.15;margin:4px 0}
a{color:var(--accent)}
"""


def build(root: Path, out: Path | None = None) -> Path:
    brief = project.load_brief(root).get("brief", {})
    notes = project.load_notes(root)
    refs = project.load_refs(root)
    picks = project.load_picks(root)
    direction = (root / "direction.md").read_text() if (root / "direction.md").exists() else ""
    audit = json.loads((root / "audit" / "latest.json").read_text()) if (root / "audit" / "latest.json").exists() else None
    tokens_css = _find_tokens_css(root)
    e = html.escape
    parts = [f"<!doctype html><html lang=\"{e(brief.get('language', 'en'))}\"><head><meta charset=\"utf-8\">"
             f"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>{e(brief.get('title', 'Design dossier'))} - dossier</title>"
             f"<style>{CSS}</style></head><body><main>"]
    toc = [("brief", "Brief"), ("principles", f"Principles ({len(notes)})"), ("references", f"References ({len(refs)})"),
           ("compare", "Comparison"), ("direction", "Direction"), ("tokens", "Tokens"), ("effects", "Effects"), ("audit", "Audit")]
    parts.append(f"<header class=\"top\"><h1>{e(brief.get('title', 'Design dossier'))}</h1><div class=\"meta\">"
                 f"<span>type: {e(str(brief.get('type')))}</span><span>stack: {e(str(brief.get('stack')))}</span>"
                 f"<span>generated {time.strftime('%Y-%m-%d %H:%M')}</span>"
                 + (f"<span>audit: {audit['score']}/100 {'pass' if audit['pass'] else 'fail'}</span>" if audit else "")
                 + "</div><nav class=\"toc\">" + "".join(f"<a href=\"#{a}\">{e(t)}</a>" for a, t in toc) + "</nav></header>")

    # brief
    rows = "".join(f"<dt>{e(k.replace('_', ' '))}</dt><dd>{e(', '.join(v) if isinstance(v, list) else str(v))}</dd>"
                   for k, v in brief.items() if k not in ("title", "summary") and v)
    parts.append(f"<section id=\"brief\"><h2>Brief</h2><div class=\"card prose\"><p>{e(brief.get('summary', '').strip())}</p><dl>{rows}</dl></div></section>")

    # principles
    by_topic: dict[str, list] = {}
    for n in notes:
        by_topic.setdefault(n.get("topic") or "general", []).append(n)
    cards = []
    for topic, items in by_topic.items():
        for n in items:
            v = n.get("verified", "")
            badge = ("b-exact", "verified quote") if v == "exact" else ("b-close", "close match") if v == "close" else \
                    ("b-kind", "no quote") if v == "unchecked" else ("b-bad", v)
            quote = f"<blockquote>{e(n['quote'])}</blockquote>" if n.get("quote") else ""
            cards.append(f"<div class=\"card\"><div class=\"chips\"><span class=\"badge b-kind\">{e(n['id'])}</span>"
                         f"<span class=\"badge b-kind\">{e(topic)}</span><span class=\"badge b-kind\">{e(n.get('kind') or '')}</span>"
                         f"<span class=\"badge {badge[0]}\">{e(badge[1])}</span></div>"
                         f"<h3 style=\"margin-top:10px\">{e(n['principle'])}</h3>{quote}"
                         f"<div class=\"sub\"><a href=\"{e(n['url'])}\">{e(n.get('title') or n['url'])}</a>"
                         + (f" ({e(n['author'])})" if n.get("author") else "") + "</div></div>")
    parts.append("<section id=\"principles\"><h2>Principles from expert sources</h2><p class=\"lede\">Each principle is tied to a source; quotes are checked against the live page text.</p>"
                 f"<div class=\"grid\">{''.join(cards) or '<p>No notes yet (front-design note add).</p>'}</div></section>")

    # references
    rcards = []
    for r in refs:
        d = Path(r["dir"])
        shots = r.get("screenshots", {})
        desk = shots.get("desktop", [])
        mob = shots.get("mobile", [])
        img = f"<img class=\"shot\" loading=\"lazy\" src=\"{e(_rel(root, d / desk[0]))}\" alt=\"{e(r.get('title') or '')} screenshot\">" if desk else ""
        thumbs = "".join(f"<a href=\"{e(_rel(root, d / f))}\"><img loading=\"lazy\" src=\"{e(_rel(root, d / f))}\" alt=\"\"></a>" for f in desk[1:] + mob)
        fonts = ", ".join(f"{f['family']} ({f['class']})" for f in r.get("fonts", [])[:3])
        pal = r.get("palette", {})
        sw = _swatches((pal.get("backgrounds") or pal.get("declared") or [])[:4] + (pal.get("accents") or [])[:2])
        libs = [x for g in ("effects", "framework") for x in r.get("libraries", {}).get(g, [])]
        ty = r.get("type", {})
        obs = re.sub(r"^#.*\n+|URL:.*\n+", "", r.get("notes_md", ""), flags=re.M)
        obs = "\n".join(l for l in obs.splitlines() if not re.match(r"^\s*-\s*[^:]+:\s*$", l))  # drop unfilled prompts
        obs_html = markdown(obs) if re.sub(r"#+.*", "", obs).strip() else ""
        rcards.append(f"<div class=\"card\">{img}<div class=\"thumbs\">{thumbs}</div><h3>{e(r.get('title') or r.get('url') or '')}</h3>"
                      f"<div class=\"sub\"><a href=\"{e(r.get('final_url') or r.get('url') or '')}\">{e(r.get('final_url') or r.get('url') or '')}</a></div>"
                      f"<dl><dt>fonts</dt><dd>{e(fonts)}</dd><dt>type</dt><dd>body {e(str(ty.get('body_px')))}px, ratio {e(str(ty.get('ratio')))}</dd>"
                      f"<dt>theme</dt><dd>{e(str(r.get('theme')))}</dd></dl><div>{sw}</div>"
                      f"<div class=\"chips\">{''.join(f'<span class=chip>{e(x)}</span>' for x in libs)}</div>{obs_html}</div>")
    parts.append("<section id=\"references\"><h2>Reference sites</h2><p class=\"lede\">Captured with computed styles; open the thumbnails for full-page slices.</p>"
                 f"<div class=\"grid\">{''.join(rcards) or '<p>No references yet (front-design capture URL).</p>'}</div></section>")

    # comparison
    if refs:
        head = ["Site", "Fonts", "Body", "Ratio", "Grid", "Radius", "Width", "Accent", "Effects"]
        body = []
        for r in refs:
            pal = r.get("palette", {})
            acc = (pal.get("accents") or [[None]])[0][0]
            body.append([r.get("slug", ""), ", ".join(f["family"] for f in r.get("fonts", [])[:2]),
                         f"{r.get('type', {}).get('body_px')}px", str(r.get("type", {}).get("ratio")),
                         str(r.get("spacing", {}).get("base_unit")), ", ".join(x for x, _ in r.get("shape", {}).get("radii", [])[:2]),
                         str(r.get("layout", {}).get("content_width_px")),
                         _swatches([(acc, "")]) if acc else "", ", ".join(r.get("libraries", {}).get("effects", []))])
        table = "<table><thead><tr>" + "".join(f"<th>{h}</th>" for h in head) + "</tr></thead><tbody>"
        table += "".join("<tr>" + "".join(f"<td>{c if c.startswith('<span') else e(c)}</td>" for c in row) + "</tr>" for row in body)
        parts.append(f"<section id=\"compare\"><h2>Comparison</h2><div class=\"table-wrap\">{table}</tbody></table></div></section>")

    parts.append(f"<section id=\"direction\"><h2>Direction</h2><div class=\"card prose\">{markdown(direction)}</div></section>")

    # tokens
    if tokens_css:
        tv = _parse_tokens_css(tokens_css.read_text())
        cols = [(k, v.strip()) for k, v in tv.items() if color.parse(v.strip())]
        steps = [(k, v) for k, v in tv.items() if k.startswith("--step")]
        sw = "".join(f"<span class=\"sw\"><i style=\"background:{e(v)}\"></i>{e(k)}: {e(v)}</span>" for k, v in cols)
        st = "".join(f"<div style=\"font-size:{e(v)}\">{e(k)} The quick brown fox</div>" for k, v in sorted(steps, key=lambda kv: kv[0], reverse=True))
        parts.append(f"<section id=\"tokens\"><h2>Tokens</h2><p class=\"lede\">From {e(_rel(root, tokens_css))}.</p>"
                     f"<div class=\"card\">{sw or 'no color tokens'}<div class=\"steps\" style=\"margin-top:16px\">{st}</div></div></section>")
    else:
        parts.append("<section id=\"tokens\"><h2>Tokens</h2><p class=\"lede\">No tokens.css yet.</p></section>")

    # effects
    ecards = "".join(f"<div class=\"card\"><span class=\"badge b-kind\">{e(p['role'])}</span><h3 style=\"margin-top:8px\">{e(p['name'])}</h3>"
                     f"<p>{e(p['why'])}</p><div class=\"sub\"><code>{e(p['package'])}@{e(p['version'])}</code> <a href=\"{e(p['url'])}\">docs</a></div></div>"
                     for p in picks)
    parts.append(f"<section id=\"effects\"><h2>Effects</h2><div class=\"grid\">{ecards or '<p>None picked (front-design effects pick).</p>'}</div></section>")

    # audit
    if audit:
        fl = "".join(f"<div class=\"finding\"><span class=\"badge {'b-bad' if f['severity'] == 'error' else 'b-close' if f['severity'] == 'warning' else 'b-kind'}\">{e(f['severity'])}</span> "
                     f"<strong>{e(f['title'])}</strong> <small>x{f['count']}</small><br><small>{e(f['fix'])}</small></div>" for f in audit["findings"])
        shots = audit.get("screenshots", {})
        imgs = "".join(f"<img class=\"shot\" style=\"aspect-ratio:auto\" loading=\"lazy\" src=\"audit/shots/{e(v[0])}\" alt=\"{e(k)} view\">"
                       for k, v in shots.items() if v)
        parts.append(f"<section id=\"audit\"><h2>Audit</h2><div class=\"grid\"><div class=\"card\"><div class=\"score {'pass' if audit['pass'] else 'fail'}\">{audit['score']}</div>"
                     f"<p>{audit['errors']} errors, {audit['warnings']} warnings ({e(audit['mode'])}, {e(audit['time'])})</p>{fl}</div>"
                     f"<div class=\"card\">{imgs}</div></div></section>")
    else:
        parts.append("<section id=\"audit\"><h2>Audit</h2><p class=\"lede\">Not run yet (front-design audit build/index.html).</p></section>")
    parts.append("</main></body></html>")
    out = out or root / "dossier.html"
    out.write_text("\n".join(parts))
    return out
