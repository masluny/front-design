"""front-design command line."""
from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import __version__, catalog, color, project, scale, web


def _out(data, as_json: bool, text: str):
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str) if as_json else text)


def _root_or_none() -> Path | None:
    try:
        return project.find_root()
    except project.ProjectError:
        return None


def _root() -> Path:
    try:
        return project.find_root()
    except project.ProjectError as e:
        sys.exit(f"front-design: {e}")


def _wrap(s: str, indent: str = "    ", width: int = 100) -> str:
    import textwrap
    return textwrap.fill(" ".join(s.split()), width=width, initial_indent=indent, subsequent_indent=indent)


# ------------------------------------------------------------------ commands

def cmd_init(a):
    if a.type not in catalog.PAGE_TYPES:
        sys.exit(f"--type must be one of: {', '.join(catalog.PAGE_TYPES)}")
    try:
        root = project.init(a.brief, Path(a.dir) if a.dir else None, a.type, a.stack, a.lang)
    except project.ProjectError as e:
        sys.exit(f"front-design: {e}")
    print(f"created {root}/ (brief.toml, direction.md, research/, refs/, build/, audit/)")
    print(f"next: cd {root} && fill brief.toml, then `front-design sources` and `front-design refs`")


def cmd_status(a):
    root = _root()
    b = project.load_brief(root).get("brief", {})
    notes = project.load_notes(root)
    refs = project.load_refs(root)
    picks = project.load_picks(root)
    audit_p = root / "audit" / "latest.json"
    audit = json.loads(audit_p.read_text()) if audit_p.exists() else None
    missing = [k for k in ("audience", "primary_action", "brand_adjectives") if not b.get(k)]
    verified = sum(n["verified"] in ("exact", "close") for n in notes)
    observed = sum(1 for r in refs if "What to borrow:" in r.get("notes_md", "") and
                   any(l.split(":", 1)[1].strip() for l in r["notes_md"].splitlines() if l.startswith("- ") and ":" in l))
    direction = (root / "direction.md").read_text() if (root / "direction.md").exists() else ""
    data = {"root": str(root), "type": b.get("type"), "brief_missing": missing, "principles": len(notes),
            "principles_verified": verified, "references": len(refs), "references_with_notes": observed,
            "direction_written": "<name>" not in direction, "effects": [p["key"] for p in picks],
            "tokens_css": bool(list(root.glob("tokens.css")) + list(root.glob("build/**/tokens.css"))),
            "audit": {k: audit[k] for k in ("score", "pass", "errors", "warnings")} if audit else None}
    steps = []
    if missing:
        steps.append(f"fill brief.toml: {', '.join(missing)}")
    if len(notes) < 8:
        steps.append(f"research principles: {len(notes)}/8+ notes (front-design sources, note add)")
    if len(refs) < 5:
        steps.append(f"capture references: {len(refs)}/5+ (front-design refs, capture)")
    if refs and observed < len(refs):
        steps.append(f"write observations in refs/*/notes.md ({observed}/{len(refs)} done)")
    if not data["direction_written"]:
        steps.append("write direction.md (2-3 options, pick one)")
    if not picks:
        steps.append("pick effects (front-design effects ..., effects pick)")
    if not data["tokens_css"]:
        steps.append("create tokens.css (front-design scale --out tokens.css, contrast)")
    if not audit or not audit["pass"]:
        steps.append("build, then front-design audit build/index.html until it passes")
    steps.append("front-design dossier")
    data["next"] = steps
    _out(data, a.json, "\n".join([
        f"project {root} ({b.get('type')})",
        f"  brief: {'complete' if not missing else 'missing ' + ', '.join(missing)}",
        f"  principles: {len(notes)} ({verified} with verified quotes)",
        f"  references: {len(refs)} ({observed} with observations)",
        f"  direction: {'written' if data['direction_written'] else 'template only'}",
        f"  effects: {', '.join(data['effects']) or 'none'}",
        f"  tokens.css: {'yes' if data['tokens_css'] else 'no'}",
        f"  audit: {data['audit'] or 'not run'}",
        "next:", *[f"  - {s}" for s in steps]]))


def cmd_sources(a):
    page_type = a.type
    root = _root_or_none()
    topics = a.topic
    if not page_type and not topics and root and not a.all:
        brief = project.load_brief(root)
        page_type = brief.get("brief", {}).get("type")
        topics = brief.get("research", {}).get("topics") or None
    items = catalog.sources() if a.all else catalog.find_sources(page_type, topics)
    if a.check:
        def probe(s):
            try:
                final, status, html = web.fetch(s["url"], timeout=20, max_bytes=300_000)
                return s, status, web.looks_blocked(status, html)
            except web.FetchError as e:
                return s, str(e)[:80], True
        with ThreadPoolExecutor(8) as ex:
            res = list(ex.map(probe, items))
        bad = [(s["key"], st) for s, st, blocked in res if st != 200]
        for s, st, blocked in res:
            print(f"{'ok ' if st == 200 else 'ERR'} {st!s:>4} {s['key']:<28} {s['url']}" + (" (bot wall?)" if blocked and st == 200 else ""))
        print(f"{len(res) - len(bad)}/{len(res)} reachable")
        return 1 if bad else 0
    if a.json:
        _out(items, True, "")
        return
    print(f"{len(items)} sources" + (f" for type={page_type}" if page_type else "") + (f" topics={topics}" if topics else ""))
    print("evidence weight: research > standard > guideline > craft > tool\n")
    for s in items:
        print(f"[{s['kind']}] {s['key']}  {s['title']}  ({s['author']})")
        print(f"    {s['url']}  topics: {', '.join(s['topics'])}")
        print(_wrap(s["why"]))


def cmd_note(a):
    root = _root()
    if a.action == "add":
        if not a.source or not a.principle:
            sys.exit("note add needs --source and --principle")
        try:
            n = project.add_note(root, a.source, a.principle, a.quote, a.topic, verify=not a.no_verify,
                                 title=a.title, kind=a.kind)
        except project.ProjectError as e:
            sys.exit(f"front-design: {e}")
        _out(n, a.json, f"{n['id']} added [{n['verified']}] {n['principle']}  <- {n['title']}")
        if n["verified"] == "not-found":
            print("  quote NOT found on the page: copy the exact words from the source (or drop --quote)")
    elif a.action == "list":
        notes = project.load_notes(root)
        if a.json:
            _out(notes, True, "")
            return
        for n in notes:
            print(f"{n['id']:<4} [{n['verified']}] ({n.get('topic') or '-'}) {n['principle']}")
            if n.get("quote"):
                print(f"     \"{n['quote'][:140]}\"")
            print(f"     {n['url']}")
    elif a.action == "rm":
        if not a.id:
            sys.exit("note rm needs an id (e.g. P3)")
        print("removed" if project.remove_note(root, a.id) else "no such note")
    elif a.action == "verify":
        notes = project.load_notes(root)
        for n in notes:
            if n.get("quote"):
                try:
                    text, status = project.page_text(n["url"])
                    n["verified"], n["match"] = web.verify_quote(n["quote"], text) if text else (f"unverifiable (HTTP {status})", None)
                except web.FetchError as e:
                    n["verified"] = f"unverifiable ({e})"
            print(f"{n['id']:<4} {n['verified']}")
        project.save_notes(root, notes)


def cmd_refs(a):
    root = _root_or_none()
    page_type = a.type
    competitors = []
    if root:
        b = project.load_brief(root).get("brief", {})
        page_type = page_type or b.get("type")
        competitors = b.get("competitors", [])
    gal, ex = catalog.find_galleries(page_type), catalog.find_exemplars(page_type)
    if a.json:
        _out({"galleries": gal, "exemplars": ex, "competitors": competitors}, True, "")
        return
    print(f"References for type={page_type or 'any'}\n\nGalleries (browse, then capture what you pick):")
    for g in gal:
        print(f"  {g['name']:<22} {g['url']:<40}" + (" [login]" if g.get("login") else ""))
        print(_wrap(g["note"], "      "))
    print("\nExemplars (well-known for design quality):")
    for x in ex:
        print(f"  {x['name']:<22} {x['url']:<40}")
        print(_wrap(x["known_for"], "      "))
    if competitors:
        print("\nCompetitors from brief.toml:")
        for c in competitors:
            print(f"  {c}")
    print("\nMix: 3-4 category leaders/competitors + 2-3 taste references + 1 wildcard from another field.")


def cmd_capture(a):
    from . import capture as cap
    root = _root_or_none()
    refs_dir = Path(a.out) if a.out else (root / "refs" if root else Path("refs"))
    results = []
    for url in a.urls:
        print(f"capturing {url} ...", file=sys.stderr)
        try:
            t = cap.capture(url, refs_dir, static=a.static, slices=a.slices, mobile=not a.no_mobile,
                            name=a.name if len(a.urls) == 1 else None)
        except (web.FetchError, Exception) as e:  # keep going with the other URLs
            print(f"  failed: {e}", file=sys.stderr)
            results.append({"url": url, "error": str(e)})
            continue
        results.append(t)
        if not a.json:
            fonts = ", ".join(f"{f['family']}" for f in t.get("fonts", [])[:3])
            libs = ", ".join(x for g in t.get("libraries", {}).values() for x in g)
            shots = sum(len(v) for v in t.get("screenshots", {}).values())
            print(f"  -> {t['dir']}  [{t['mode']}{', BLOCKED' if t.get('blocked') else ''}] {shots} screenshots")
            print(f"     fonts: {fonts or '?'} | theme: {t.get('theme')} | libs: {libs or '-'}")
            print(f"     read {t['dir']}/summary.md, look at the screenshots, write {t['dir']}/notes.md")
    if a.json:
        _out(results, True, "")
    return 0 if all("error" not in r for r in results) else 1


def cmd_compare(a):
    root = _root()
    refs = project.load_refs(root)
    if not refs:
        sys.exit("no captured references (front-design capture URL)")
    rows = []
    for r in refs:
        pal = r.get("palette", {})
        rows.append({
            "site": r.get("slug"), "theme": r.get("theme"),
            "fonts": [f"{f['family']} ({f['class']})" for f in r.get("fonts", [])[:3]],
            "body_px": r.get("type", {}).get("body_px"), "h1_px": r.get("type", {}).get("h1_px"),
            "ratio": r.get("type", {}).get("ratio"), "base_unit": r.get("spacing", {}).get("base_unit"),
            "radius": [x for x, _ in r.get("shape", {}).get("radii", [])[:2]],
            "content_width": r.get("layout", {}).get("content_width_px"),
            "accent": (pal.get("accents") or [[None]])[0][0],
            "effects": r.get("libraries", {}).get("effects", []),
            "framework": r.get("libraries", {}).get("framework", []),
            "sections": r.get("layout", {}).get("sections"),
            "css": sorted(r.get("css_features", {}))[:8],
        })
    if a.json:
        _out(rows, True, "")
        return
    for row in rows:
        print(f"{row['site']}  [{row['theme']}]")
        print(f"   type: {', '.join(row['fonts'])} | body {row['body_px']}px h1 {row['h1_px']}px ratio {row['ratio']}")
        print(f"   space: base {row['base_unit']} | radius {row['radius']} | width {row['content_width']} | sections {row['sections']}")
        print(f"   accent: {row['accent']} | effects: {', '.join(row['effects']) or '-'} | built with: {', '.join(row['framework']) or '?'}")
    themes = [r["theme"] for r in rows]
    ratios = [r["ratio"] for r in rows if r["ratio"]]
    bodies = [r["body_px"] for r in rows if r["body_px"]]
    print("\npatterns:")
    print(f"   themes: {', '.join(f'{t} x{themes.count(t)}' for t in sorted(set(themes)))}")
    if ratios:
        print(f"   type ratio range {min(ratios)}-{max(ratios)}, body {min(bodies)}-{max(bodies)}px")
    eff = [e for r in rows for e in r["effects"]]
    if eff:
        print(f"   effects in use: {', '.join(sorted(set(eff), key=lambda e: -eff.count(e)))}")


def cmd_effects(a):
    root = _root_or_none()
    if a.action == "show":
        e = catalog.effect_by_key(a.key or "")
        if not e:
            sys.exit(f"unknown effect '{a.key}' (front-design effects)")
        if a.json:
            _out(e, True, "")
            return
        print(f"{e['library']}: {e['name']}  [{e['category']}, cost {e['cost']}]")
        print(f"  package {e['package']} @ {e['version']}  |  license: {e['license']}")
        print(f"  docs: {e['url']}")
        print(f"  vibes: {', '.join(e['vibes'])}  stacks: {', '.join(e['stacks'])}")
        for k in ("use_when", "avoid_when", "a11y", "perf"):
            print(f"  {k.replace('_', ' ')}:")
            print(_wrap(e[k], "    "))
        meta = catalog.effects_meta()
        for k in ("react", "vanilla"):
            if e.get(k):
                print(f"\n--- {k} ---\n{e[k].strip()}")
        if any("useReducedMotion" in (e.get(k) or "") or "reduce" in (e.get(k) or "") for k in ("react",)):
            print(f"\n--- helper: useReducedMotion ---\n{meta['helpers']['use_reduced_motion'].strip()}")
        print(f"\n(checked {meta['checked']}; pin the version and re-check props on the docs page)")
        return
    if a.action == "pick":
        if not root:
            sys.exit("effects pick needs a project (run inside a front-design project)")
        if not a.key or not a.why:
            sys.exit("effects pick KEY --why \"...\" [--role signature|support]")
        try:
            p = project.pick_effect(root, a.key, a.role, a.why)
        except project.ProjectError as e:
            sys.exit(f"front-design: {e}")
        print(f"picked {p['name']} as {p['role']}")
        return
    items = catalog.find_effects(a.vibe, a.category, a.stack, a.max_cost)
    if a.json:
        _out(items, True, "")
        return
    print(f"{len(items)} effects" + "".join(f" {k}={v}" for k, v in (("vibe", a.vibe), ("category", a.category), ("stack", a.stack), ("max-cost", a.max_cost)) if v))
    print(f"vibes: {', '.join(catalog.all_vibes())}\ncategories: {', '.join(catalog.all_categories())}\n")
    for e in items:
        print(f"{e['key']:<22} {e['library']}: {e['name']}  [{e['category']}, {e['cost']}]")
        print(_wrap(e["use_when"], "    ", 104))
    print("\nfront-design effects show KEY   for snippets, a11y and perf notes")


def cmd_scale(a):
    ts = scale.type_scale(a.min_base, a.max_base, a.min_ratio, a.max_ratio, a.min_vw, a.max_vw, tuple(a.steps))
    items = ts + (scale.space_scale(a.min_base, a.max_base, a.min_vw, a.max_vw) if a.space else [])
    css = (f"/* front-design scale: {a.min_base}px @{a.min_vw:g}px ratio {a.min_ratio} -> {a.max_base}px @{a.max_vw:g}px "
           f"ratio {a.max_ratio} ({scale.nearest_named_ratio(a.min_ratio)[1]} -> {scale.nearest_named_ratio(a.max_ratio)[1]}) */\n"
           + scale.to_css(items))
    if a.json:
        _out([{"name": f.name, "min_px": round(f.min_px, 2), "max_px": round(f.max_px, 2), "css": f.clamp()} for f in items], True, "")
        return
    if a.out:
        p = Path(a.out)
        existing = p.read_text() if p.exists() else ""
        marker = "/* front-design scale"
        if marker in existing:
            start = existing.index(marker)
            end = existing.index("}", start) + 1
            existing = existing[:start] + css + existing[end:]
        else:
            existing = (existing + "\n\n" if existing else "") + css
        p.write_text(existing.strip() + "\n")
        print(f"wrote {p}")
    print(css)


def cmd_contrast(a):
    cols = []
    for c in a.colors:
        p = color.parse(c)
        if not p:
            sys.exit(f"cannot parse color '{c}'")
        cols.append((c, p))
    rows = []
    for i, (n1, c1) in enumerate(cols):
        for n2, c2 in cols[i + 1:]:
            bg = c2 if c2[3] >= 1 else color.blend(c2, (1, 1, 1, 1))
            fg = color.blend(c1, bg) if c1[3] < 1 else c1
            r = round(color.contrast(fg, bg), 2)
            rows.append({"a": n1, "b": n2, "ratio": r, "text": color.wcag_level(r), "large_text": color.wcag_level(r, True),
                         "ui_3to1": r >= 3})
    if a.json:
        _out(rows, True, "")
        return
    for n, p in cols:
        print(f"{n:<28} {color.to_hex(p)}  {color.describe(p)}  L={round(color.rgb_to_oklch(*p[:3])[0], 3)}")
    print()
    for r in rows:
        print(f"{r['a']:<24} vs {r['b']:<24} {r['ratio']:>5}:1  text {r['text']:<8} large {r['large_text']:<5} UI {'ok' if r['ui_3to1'] else 'fail'}")


def cmd_audit(a):
    from . import audit
    root = _root_or_none()
    out_dir = Path(a.out) if a.out else (root / "audit" if root else Path("audit"))
    result = audit.run(a.target, out_dir, static=a.static, min_score=a.min_score, slices=a.slices)
    _out(result, a.json, audit.format_text(result) + f"\nsaved {out_dir}/latest.json, screenshots in {out_dir}/shots/")
    return 0 if result["pass"] else 2


def cmd_dossier(a):
    from . import dossier
    root = _root()
    out = dossier.build(root, Path(a.out) if a.out else None)
    print(f"wrote {out}")
    if a.open:
        webbrowser.open(out.resolve().as_uri())


def cmd_doctor(a):
    from . import browser
    print(f"front-design {__version__}, python {sys.version.split()[0]}")
    ok, msg = browser.available()
    print(f"playwright: {msg}")
    if ok:
        try:
            with browser.browser() as b:
                print(f"chromium: ok ({b.version})")
        except browser.BrowserUnavailable as e:
            print(f"chromium: {e}")
    try:
        import PIL
        print(f"pillow: ok ({PIL.__version__}) -> pixel-accurate contrast in audit")
    except ImportError:
        print("pillow: missing -> audit falls back to computed-style contrast (pip install pillow)")
    print(f"catalog: {len(catalog.sources())} sources, {len(catalog.galleries())} galleries, "
          f"{len(catalog.exemplars())} exemplars, {len(catalog.effects())} effects (checked {catalog.effects_meta()['checked']})")
    if a.online:
        ns = argparse.Namespace(type=None, topic=None, all=True, check=True, json=False)
        return cmd_sources(ns)


def cmd_install(a):
    from . import install
    done = install.install(a.target, link=a.link, project=Path(a.project) if a.project else None)
    for d in done:
        print(f"installed skill -> {d}")
    print("Claude Code: ~/.claude/skills | Codex: ~/.agents/skills | Cursor reads both")


# ------------------------------------------------------------------ parser

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="front-design", description="Research-first UI/UX design toolkit for AI agents.")
    p.add_argument("--version", action="version", version=f"front-design {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="create a design project folder with brief.toml")
    s.add_argument("brief")
    s.add_argument("--dir")
    s.add_argument("--type", default="landing", help=" | ".join(catalog.PAGE_TYPES))
    s.add_argument("--stack", default="unknown")
    s.add_argument("--lang", default="en")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("status", help="project progress and next steps")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("sources", help="expert articles to read for this page type/topics")
    s.add_argument("--type")
    s.add_argument("--topic", nargs="*")
    s.add_argument("--all", action="store_true")
    s.add_argument("--check", action="store_true", help="check every URL is reachable")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_sources)

    s = sub.add_parser("note", help="record a principle from a source (quote is verified against the page)")
    s.add_argument("action", choices=["add", "list", "rm", "verify"])
    s.add_argument("id", nargs="?")
    s.add_argument("--source", help="source key from `sources` or a URL")
    s.add_argument("--principle")
    s.add_argument("--quote", help="exact words from the source")
    s.add_argument("--topic")
    s.add_argument("--title")
    s.add_argument("--kind", choices=list(catalog.KIND_RANK))
    s.add_argument("--no-verify", action="store_true")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_note)

    s = sub.add_parser("refs", help="galleries and exemplar sites for this page type")
    s.add_argument("--type")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_refs)

    s = sub.add_parser("capture", help="screenshot a site and extract its design tokens")
    s.add_argument("urls", nargs="+")
    s.add_argument("--static", action="store_true", help="no browser: HTML/CSS only")
    s.add_argument("--slices", type=int, default=6, help="desktop viewport screenshots (default 6)")
    s.add_argument("--no-mobile", action="store_true")
    s.add_argument("--name")
    s.add_argument("--out")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_capture)

    s = sub.add_parser("compare", help="compare captured references side by side")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_compare)

    s = sub.add_parser("effects", help="catalog of modern effects (Paper Shaders, GSAP, Unicorn Studio...)")
    s.add_argument("action", nargs="?", choices=["list", "show", "pick"], default="list")
    s.add_argument("key", nargs="?")
    s.add_argument("--vibe")
    s.add_argument("--category")
    s.add_argument("--stack")
    s.add_argument("--max-cost", choices=["light", "medium", "heavy"])
    s.add_argument("--role", choices=["signature", "support"], default="signature")
    s.add_argument("--why")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_effects)

    s = sub.add_parser("scale", help="fluid type (and space) scale as CSS clamp() tokens")
    s.add_argument("--min-base", type=float, default=16)
    s.add_argument("--max-base", type=float, default=19)
    s.add_argument("--min-ratio", type=float, default=1.2)
    s.add_argument("--max-ratio", type=float, default=1.25)
    s.add_argument("--min-vw", type=float, default=360)
    s.add_argument("--max-vw", type=float, default=1440)
    s.add_argument("--steps", type=int, nargs=2, default=[-2, 5])
    s.add_argument("--space", action="store_true", help="also emit a space scale")
    s.add_argument("--out", help="write/replace the block in a CSS file")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_scale)

    s = sub.add_parser("contrast", help="WCAG contrast matrix for colors (hex, rgb, hsl, oklch, lab...)")
    s.add_argument("colors", nargs="+")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_contrast)

    s = sub.add_parser("audit", help="audit a built page (file or URL): a11y, contrast on real pixels, motion, mobile")
    s.add_argument("target")
    s.add_argument("--static", action="store_true")
    s.add_argument("--min-score", type=int, default=85)
    s.add_argument("--slices", type=int, default=6)
    s.add_argument("--out")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_audit)

    s = sub.add_parser("dossier", help="compile research, references, direction and audit into dossier.html")
    s.add_argument("--out")
    s.add_argument("--open", action="store_true")
    s.set_defaults(fn=cmd_dossier)

    s = sub.add_parser("doctor", help="check dependencies (and --online: every source URL)")
    s.add_argument("--online", action="store_true")
    s.set_defaults(fn=cmd_doctor)

    s = sub.add_parser("install-skill", help="install the agent skill for Claude Code / Codex / Cursor")
    s.add_argument("--target", nargs="+", default=["all"], choices=["all", "claude", "codex", "cursor"])
    s.add_argument("--link", action="store_true", help="symlink instead of copy (for development)")
    s.add_argument("--project", help="install into a repo (.claude/skills and .agents/skills) instead of home")
    s.set_defaults(fn=cmd_install)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rc = args.fn(args)
    return rc or 0
