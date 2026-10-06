import json
import os
import tempfile
import unittest
from pathlib import Path

from designscout import analyze, catalog, cli, color, dossier, fingerprints, project, scale, web

FIX = Path(__file__).parent / "fixtures"


class ColorTests(unittest.TestCase):
    def test_parse_formats(self):
        self.assertEqual(color.to_hex(color.parse("#fff")), "#ffffff")
        self.assertEqual(color.to_hex(color.parse("rgb(255 0 0 / 50%)")), "#ff0000")
        self.assertAlmostEqual(color.parse("rgba(0, 0, 0, 0.25)")[3], 0.25)
        self.assertEqual(color.to_hex(color.parse("hsl(120 100% 25%)")), "#008000")
        self.assertIsNone(color.parse("transparent"))
        self.assertIsNone(color.parse("not-a-color"))

    def test_oklch_roundtrip(self):
        for hexv in ("#b4441c", "#2e4a3f", "#6366f1", "#f6f1e9"):
            L, C, H = color.rgb_to_oklch(*color.parse(hexv)[:3])
            back = color.parse(f"oklch({L} {C} {H})")
            self.assertEqual(color.to_hex(back), hexv)

    def test_lab_and_p3(self):
        self.assertEqual(color.to_hex(color.parse("lab(100 0 0)")), "#ffffff")
        self.assertEqual(color.to_hex(color.parse("color(display-p3 1 1 1)")), "#ffffff")

    def test_contrast_known_values(self):
        self.assertAlmostEqual(color.contrast(color.parse("#000"), color.parse("#fff")), 21.0, places=2)
        self.assertAlmostEqual(color.contrast(color.parse("#767676"), color.parse("#fff")), 4.54, places=2)
        self.assertEqual(color.wcag_level(4.5), "AA")
        self.assertEqual(color.wcag_level(3.2, large=True), "AA")

    def test_cluster_merges_near_colors(self):
        out = color.cluster({"#ffffff": 10, "#fefefe": 5, "#000000": 3})
        self.assertEqual(out[0][0], "#ffffff")
        self.assertEqual(len(out), 2)


class ScaleTests(unittest.TestCase):
    def test_clamp_values(self):
        steps = scale.type_scale(16, 20, 1.2, 1.25, 320, 1240, (0, 1))
        self.assertEqual(steps[0].name, "step-0")
        self.assertIn("clamp(1rem,", steps[0].clamp())
        self.assertTrue(steps[0].clamp().endswith("1.25rem)"))

    def test_infer_ratio_and_grid(self):
        self.assertAlmostEqual(scale.infer_ratio([16, 20, 25, 31.25, 39.06], 16), 1.25, places=2)
        self.assertEqual(scale.infer_base_unit({8: 10, 16: 8, 24: 5, 32: 2})[0], 8)
        self.assertEqual(scale.infer_base_unit({4: 10, 12: 8, 20: 5, 8: 1})[0], 4)


class CatalogTests(unittest.TestCase):
    def test_sources_integrity(self):
        keys = [s["key"] for s in catalog.sources()]
        self.assertEqual(len(keys), len(set(keys)))
        for s in catalog.sources():
            self.assertTrue(s["url"].startswith("http"), s["key"])
            self.assertIn(s["kind"], catalog.KIND_RANK, s["key"])

    def test_every_type_has_sources_and_refs(self):
        for t in catalog.PAGE_TYPES:
            self.assertGreaterEqual(len(catalog.find_sources(t)), 5, t)
            self.assertTrue(catalog.find_galleries(t), t)

    def test_effects_integrity(self):
        keys = [e["key"] for e in catalog.effects()]
        self.assertEqual(len(keys), len(set(keys)))
        for e in catalog.effects():
            self.assertTrue(e.get("react") or e.get("vanilla"), e["key"])
            for f in ("use_when", "avoid_when", "a11y", "perf", "license", "version"):
                self.assertTrue(e.get(f), (e["key"], f))
            self.assertIn(e["cost"], ("light", "medium", "heavy"))
        self.assertTrue(any(e["library"] == "Paper Shaders" for e in catalog.effects()))

    def test_effect_filters(self):
        retro = catalog.find_effects(vibe="retro")
        self.assertIn("paper-dithering", [e["key"] for e in retro])
        light_vanilla = catalog.find_effects(stack="vanilla", max_cost="light")
        self.assertTrue(all(e["cost"] == "light" for e in light_vanilla))


class WebTests(unittest.TestCase):
    def test_verify_quote(self):
        page = "Intro.\nThe design should always keep users informed about what is going on.\nMore."
        self.assertEqual(web.verify_quote("keep users informed about what is going on", page)[0], "exact")
        self.assertEqual(web.verify_quote("“keep users  informed” about what is going on", page)[0], "close")
        self.assertEqual(web.verify_quote("users love purple gradients", page)[0], "not-found")
        self.assertEqual(web.verify_quote("word count display", "the word-count dis\u00adplay appears")[0], "close")
        self.assertEqual(web.verify_quote("the display appears", "the dis\u00adplay ap\u00adpears")[0], "exact")

    def test_css_helpers(self):
        css = ":root, :host { --bg: #fff; --accent: oklch(0.6 0.2 30); } .a { color: red } @media (prefers-reduced-motion: reduce) {}"
        self.assertEqual(web.root_variables(css)["--bg"], "#fff")
        self.assertEqual(web.css_features(css)["reduced_motion_media"], 1)

    def test_html_to_text_skips_scripts(self):
        self.assertEqual(web.html_to_text("<p>Hi</p><script>var x=1</script><p>there</p>"), "Hi\n\nthere")


class FingerprintTests(unittest.TestCase):
    def test_detect(self):
        found = fingerprints.detect(
            scripts=["https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"],
            html='<html class="lenis lenis-smooth"><div data-paper-shader></div><div data-us-project="x"></div><script src="/_next/static/a.js"></script>',
            css=":root{--tw-ring:0}", globals_=["__THREE__"])
        effects = set(found["effects"])
        self.assertTrue({"GSAP", "Lenis", "Paper Shaders", "Unicorn Studio", "three.js"} <= effects)
        self.assertIn("Next.js", found["framework"])
        self.assertIn("Tailwind CSS", found["styling"])


class AnalyzeTests(unittest.TestCase):
    def test_rendered_summary(self):
        raw = {
            "mode": "rendered", "url": "https://x.test",
            "text": {"Inter|16px|400|24px|normal|rgb(20, 20, 20)|none|text|Inter, sans-serif": 900,
                     "Fraunces|48px|600|52px|-1px|rgb(20, 20, 20)|none|h1|Fraunces, serif": 40},
            "bg": {"rgba(0, 0, 0, 0)": 1, "rgb(250, 248, 244)": 1000000, "rgb(180, 68, 28)": 5000},
            "page_bg": "rgba(0, 0, 0, 0)", "root_bg": "rgba(0, 0, 0, 0)",
            "headings": [{"tag": "h1", "text": "Hi", "size": "48px", "family": "Fraunces"},
                         {"tag": "h2", "text": "Sub", "size": "30px", "family": "Fraunces"},
                         {"tag": "h3", "text": "Sub2", "size": "24px", "family": "Fraunces"}],
            "ctas": [{"text": "Buy", "bg": "rgb(180, 68, 28)", "color": "rgb(255, 255, 255)", "above_fold": True}],
            "spacing": {"8px": 10, "16px": 10, "24px": 5}, "radii": {"8px": 4},
        }
        t = analyze.summarize(raw)
        self.assertEqual(t["theme"], "light")
        self.assertEqual(t["fonts"][0]["family"], "Inter")
        self.assertEqual(t["fonts"][1]["class"], "serif")
        self.assertEqual(t["type"]["body_px"], 16.0)
        self.assertEqual(t["palette"]["accents"][0][0], "#b4441c")
        self.assertEqual(t["spacing"]["base_unit"], 8)
        self.assertGreater(t["palette"]["body_text_contrast"], 15)
        self.assertIn("Typography", analyze.to_markdown(t))


class ProjectAndAuditTests(unittest.TestCase):
    def test_init_note_dossier(self):
        with tempfile.TemporaryDirectory() as d:
            root = project.init("Landing page for a test brand", Path(d) / "p", "landing", "vanilla")
            self.assertEqual(project.load_brief(root)["brief"]["type"], "landing")
            n = project.add_note(root, "nng-heuristics", "Show system status", None, "usability")
            self.assertEqual(n["id"], "P1")
            self.assertEqual(n["verified"], "unchecked")
            project.pick_effect(root, "paper-mesh-gradient", "signature", "calm brand backdrop")
            project.pick_effect(root, "number-flow", "signature", "pricing toggle")
            roles = {p["key"]: p["role"] for p in project.load_picks(root)}
            self.assertEqual(roles, {"paper-mesh-gradient": "support", "number-flow": "signature"})
            (root / "tokens.css").write_text(":root { --bg: #fff; --step-0: 1rem; }")
            out = dossier.build(root)
            html = out.read_text()
            self.assertIn("Show system status", html)
            self.assertIn("--step-0", html)

    def test_static_audit_flags_bad_page(self):
        from designscout import audit
        with tempfile.TemporaryDirectory() as d:
            bad = audit.run(str(FIX / "bad.html"), Path(d) / "a", static=True)
            ids = {f["id"] for f in bad["findings"]}
            for expected in ("html-lang", "zoom-blocked", "img-alt", "lorem", "reduced-motion-missing",
                             "heading-skip", "focus-removed", "landmark-main"):
                self.assertIn(expected, ids)
            self.assertFalse(bad["pass"])
            good = audit.run(str(FIX / "good.html"), Path(d) / "b", static=True)
            self.assertEqual(good["errors"], 0, good["findings"])

    def test_markdown_renderer(self):
        h = dossier.markdown("# T\n\n- a **b**\n- c\n\n| x | y |\n|---|---|\n| 1 | 2 |\n\ntext `code`")
        self.assertIn("<h2>T</h2>", h)
        self.assertIn("<strong>b</strong>", h)
        self.assertIn("<td>1</td>", h)
        self.assertIn("<code>code</code>", h)

    def test_cli_contrast_and_scale(self):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(cli.main(["contrast", "#000", "#fff", "--json"]), 0)
            self.assertEqual(cli.main(["scale", "--json"]), 0)
            self.assertEqual(cli.main(["effects", "show", "paper-mesh-gradient", "--json"]), 0)
        self.assertIn('"ratio": 21.0', buf.getvalue())


@unittest.skipUnless(os.environ.get("DS_BROWSER_TESTS"), "set DS_BROWSER_TESTS=1 to run Playwright tests")
class BrowserTests(unittest.TestCase):
    def test_rendered_audit(self):
        from designscout import audit
        with tempfile.TemporaryDirectory() as d:
            bad = audit.run(str(FIX / "bad.html"), Path(d) / "a", slices=2)
            ids = {f["id"] for f in bad["findings"]}
            for expected in ("contrast-desktop", "target-size", "control-name", "input-label", "mobile-overflow", "focus-visible"):
                self.assertIn(expected, ids)
            good = audit.run(str(FIX / "good.html"), Path(d) / "b", slices=2)
            self.assertTrue(good["pass"], json.dumps(good["findings"], indent=1))
            self.assertEqual(good["metrics"]["motion_reduced"]["raf"], 0)


if __name__ == "__main__":
    unittest.main()
