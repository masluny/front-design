# design-scout

Research-first UI/UX design for AI coding agents (Claude Code, Codex, Cursor).

Ask an agent to "make it look professional" and it designs from memory: stock indigo gradients,
three identical feature cards, Inter everywhere. design-scout makes the agent work the way a good
designer does:

1. **Read the experts.** Curated sources (NN/g, Baymard, WCAG, web.dev, Butterick, Utopia, Apple HIG,
   Material, GOV.UK, Vercel's interface guidelines...) ranked by evidence. Every principle the agent
   uses is recorded with a quote that is checked against the live page.
2. **Study professional sites.** `capture` opens real sites in Chromium, takes desktop and mobile
   screenshots, and measures what they actually use: fonts, type scale ratio, palette by screen
   area, spacing grid, radii, content width, CTAs, modern CSS features and effect libraries
   (GSAP, Lenis, three.js, Paper Shaders, Unicorn Studio...).
3. **Decide with reasons.** A `direction.md` where every decision points to a principle or a reference,
   fluid type/space tokens (`clamp()`), and a contrast matrix for every color pair.
4. **Add one considered modern effect.** A catalog of 28 effects with verified snippets, licenses,
   accessibility and performance notes: Paper Shaders, Unicorn Studio, ShaderGradient, GSAP, Motion,
   Lenis, React Bits, Magic UI, Aceternity UI, Rive, View Transitions and more.
5. **Audit until it passes.** Contrast measured on the real pixels behind each text box (works over
   gradients and shaders), touch targets, focus visibility, reduced motion, mobile overflow, line
   length, type-scale drift, and more.
6. **Hand over a dossier.** One HTML page with the brief, principles, reference moodboard, comparison,
   direction, tokens, effects and audit.

The agent makes the design judgments; the CLI does everything that should be objective.

## Install

```bash
git clone https://github.com/masluny/design-scout && cd design-scout
pip install -e ".[capture]"
python -m playwright install chromium
design-scout install-skill
design-scout doctor
```

`install-skill` copies the skill to `~/.claude/skills/design-scout` (Claude Code) and
`~/.agents/skills/design-scout` (Codex). Cursor reads both locations. Use `--project .` to install
into a repository instead (`.claude/skills` and `.agents/skills`), or `--link` while developing.
For agents without skill support, paste `designscout/skill/AGENTS.md` into your `AGENTS.md`.

Playwright is optional: without it `capture --static` still reads HTML and CSS, and `audit --static`
runs the source checks. Everything else is standard library only (Python 3.11+).

## Use

In Claude Code, Codex or Cursor just ask for a design:

> Design a landing page for my small-batch coffee roastery. Shipping weekly, people should subscribe.

The skill triggers on design, redesign, restyle, "make it look professional" and UI/UX research
requests, and scales the process to the task (a full site gets 8+ principles and 5-8 references;
a single component gets a couple).

Or drive it by hand:

```bash
design-scout init "Landing page for a coffee roastery" --type landing --stack vanilla --dir design/coffee
cd design/coffee
design-scout sources                       # what to read, strongest evidence first
design-scout note add --source nng-heuristics --topic usability \
  --principle "Show the order status at every step" \
  --quote "The design should always keep users informed about what is going on"
design-scout refs                          # galleries + exemplar sites for this page type
design-scout capture https://stripe.com https://linear.app
design-scout compare
design-scout scale --min-base 17 --max-base 20 --max-ratio 1.25 --space --out tokens.css
design-scout contrast "oklch(0.25 0.02 60)" "#f6f1e9" "#b4441c"
design-scout effects --vibe warm --stack vanilla
design-scout effects show paper-grain-gradient
design-scout effects pick paper-grain-gradient --why "tactile, print-like warmth for a craft brand"
design-scout audit build/index.html
design-scout dossier --open
design-scout status                        # progress and next steps at any time
```

## Example: this tool's own landing page

[`examples/landing/`](examples/landing) is a full run of the skill: the brief, 14 principles with
verified quotes ([`research/notes.json`](examples/landing/research/notes.json)), six measured
references with written observations ([`refs/`](examples/landing/refs)), the direction with a
principle checklist ([`direction.md`](examples/landing/direction.md)), tokens, picked effects and the
final page ([`build/index.html`](examples/landing/build/index.html), audit 100/100). Screenshots of
third-party sites are not committed; `design-scout capture` recreates them.

## Commands

| Command | Purpose |
|---|---|
| `init`, `status` | create a project (`brief.toml`, `direction.md`, folders); show progress and next steps |
| `sources [--type] [--topic] [--check]` | 71 curated expert sources, filtered by page type and topic |
| `note add/list/rm/verify` | principles with quotes verified against the source page |
| `refs` | 18 galleries (Recent (ex-Godly), Awwwards, Land-book, Mobbin...) and 30 exemplar sites by page type |
| `capture URL...` | screenshots (desktop + mobile, scroll-revealed) and computed design tokens |
| `compare` | references side by side and their shared patterns |
| `effects [list/show/pick]` | the modern effects catalog |
| `scale` | fluid type and space scale (`clamp()` tokens, Utopia method) |
| `contrast` | WCAG matrix; parses hex, rgb, hsl, oklch, oklab, lab, lch, color() |
| `audit FILE/URL` | rendered + static audit, score, screenshots; exit code 2 when failing |
| `dossier` | compile everything into `dossier.html` |
| `doctor [--online]` | dependency check; `--online` checks every source URL |
| `install-skill` | install for Claude Code / Codex / Cursor |

## Effects catalog

| Category | Entries |
|---|---|
| Paper Shaders | Mesh Gradient, Grain Gradient, Dithering, God Rays, Liquid Metal (logo), Fluted Glass (image), plus pointers to the rest of the set |
| WebGL scenes | Unicorn Studio, ShaderGradient, Spline, three.js / React Three Fiber, OGL, COBE globe |
| Component collections | React Bits, Magic UI, Aceternity UI, Motion Primitives |
| Motion engines | Motion, GSAP (ScrollTrigger, SplitText), Lenis, Rive, dotLottie, NumberFlow, AutoAnimate, Vaul + Sonner |
| Web platform | View Transitions API, CSS scroll-driven animations, modern CSS kit (OKLCH, color-mix, @property borders, glass, grain, @starting-style) |

Every entry has a pinned version (checked 2026-10-06), license, vibes, cost, when to use and when
not, accessibility and performance notes, and a React and/or vanilla snippet with a
reduced-motion path. The vanilla Paper Shaders snippet is exercised by the browser test suite.

## Audit

Rendered checks (Playwright): text contrast on real pixels (desktop and mobile), horizontal overflow
at 390px, WCAG 2.5.8 target size, accessible names, form labels, visible and unobscured keyboard
focus, motion under `prefers-reduced-motion: reduce` (animations and requestAnimationFrame loops),
console errors, CLS, page weight, WebGL canvas count, line length, line height, centered
paragraphs, mobile body size, font-family count, type-scale drift, spacing grid, stock accent colors.

Static checks: `lang`, title, zoom-blocking viewport, h1 and heading order, image alt, `<main>`,
autoplaying video with sound, positive tabindex, lorem ipsum, removed focus outlines, animation
without a reduced-motion path.

Each finding links to the source behind it (for example `wcag-target-size`, `butterick-line-length`).

## Development

```bash
python -m unittest discover tests                       # fast suite
DS_BROWSER_TESTS=1 python -m unittest tests.test_core   # + Playwright audit tests
design-scout doctor --online                            # every source URL
```

Knowledge lives in `designscout/data/*.toml` (sources, galleries, effects); add entries there.

## Notes

- `capture` hides cookie banners (never accepts them), identifies itself honestly when fetching
  sources, and reports bot-check pages as `BLOCKED` instead of trying to get around them.
- Some sources (Medium) and galleries refuse scripted requests; their notes are marked
  `unverifiable` and the agent reads them with its own browser tools.
- Library licenses are their own: Paper Shaders is Apache-2.0, React Bits is MIT + Commons Clause,
  Unicorn Studio and Spline are hosted services. The catalog lists each.

## License

MIT
