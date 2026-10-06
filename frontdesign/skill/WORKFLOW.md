# front-design workflow reference

Everything here is called from inside a project folder (the one holding `brief.toml`) unless
noted. Add `--json` to most commands for machine-readable output.

## Project layout

```
design/<slug>/
  brief.toml              brief, page type, stack, research topics
  research/notes.json     principles with sources and verified quotes (P1, P2, ...)
  refs/<site>/            desktop-*.jpg, mobile-*.jpg, tokens.json, summary.md, notes.md, raw.json
  direction.md            options, chosen direction, tokens, sections, effects, principle checklist
  tokens.css              design tokens (scale block managed by `front-design scale --out`)
  effects.json            picked effects with role and reason
  build/                  prototype (when the user has no codebase)
  audit/latest.json       last audit, audit/shots/*.jpg, audit/history/
  dossier.html            compiled report
```

## Commands

| Command | What it does |
|---|---|
| `init "<brief>" --type T --stack S [--dir D] [--lang en]` | create the project; types: landing, saas, ecommerce, dashboard, portfolio, editorial, docs, app, mobile-app |
| `status` | progress and the next steps (use it to resume work) |
| `sources [--type T] [--topic a b] [--all] [--check]` | curated expert sources for the brief's type/topics, strongest evidence first |
| `note add --source KEY\|URL --principle "..." --quote "..." --topic t` | record a principle; the quote is checked against the live page (exact / close / not-found) |
| `note list`, `note rm P3`, `note verify` | manage notes; `verify` re-checks every quote |
| `refs [--type T]` | galleries + exemplar sites + competitors from the brief |
| `capture URL... [--slices 6] [--no-mobile] [--static]` | screenshots and computed tokens into `refs/<slug>/` |
| `compare` | references side by side + shared patterns |
| `effects [--vibe V] [--category C] [--stack S] [--max-cost light]` | effect catalog |
| `effects show KEY` | snippet (React and/or vanilla), license, a11y and perf notes |
| `effects pick KEY --role signature\|support --why "..."` | record the choice in `effects.json` |
| `scale [--min-base 16 --max-base 19 --min-ratio 1.2 --max-ratio 1.25 --space --out tokens.css]` | fluid type/space scale as `clamp()` custom properties (Utopia method) |
| `contrast C1 C2 [C3...]` | WCAG ratio for every pair; accepts hex, rgb(), hsl(), oklch(), oklab(), lab(), lch(), color() |
| `audit FILE\|URL [--min-score 85] [--static]` | audit the build; exit code 0 pass, 2 fail |
| `dossier [--open]` | write `dossier.html` |
| `doctor [--online]` | dependencies; `--online` checks every source URL |
| `install-skill [--target all\|claude\|codex\|cursor] [--project DIR] [--link]` | install this skill |

## Reading sources well

- Prefer the page itself over summaries of it. Quote 1-2 sentences that state the rule; the
  principle text is your paraphrase applied to this project.
- `kind` tells you how much weight a source carries: `research` (studies, measured data) and
  `standard` (WCAG) beat `guideline` (design systems) and `craft` (practitioner opinion).
- When sources disagree, note both and say which one you follow and why (usually: the one
  with evidence, or the one closer to this audience and context).
- Sites behind bot walls (Medium, some galleries) return `unverifiable`: read them with your
  own browser tools if available and keep the note, or choose another source.
- Topics vocabulary: usability, critique, hierarchy, layout, spacing, typography, color,
  dark-mode, motion, effects, accessibility, forms, navigation, landing, conversion, trust,
  content, ecommerce, checkout, dashboard, data-viz, empty-states, onboarding, mobile,
  performance, design-systems, craft.

## Choosing references

- **Leaders/competitors (3-4):** show the conventions users of this category already know.
- **Taste (2-3):** from galleries; pick for one specific quality (type, color, motion, layout),
  and write down which.
- **Wildcard (1):** a different industry with a matching brand adjective (a coffee shop can learn
  from a fashion editorial; a dev tool from a hardware brand).
- Login-only galleries (Mobbin, Refero, Page Flows): never sign in; tell the user they can share
  screenshots, or use public galleries.
- `capture` hides cookie banners (it never accepts them) and reports `BLOCKED` when it only got a
  bot-check page: drop that reference.

### refs/<slug>/notes.md template (filled after looking at the screenshots)

```
- Layout and grid: 12-col, 1200px container, generous 160px section padding
- Hero pattern: left-aligned headline + product screenshot bleeding off the right edge
- Section sequence: hero > logos > 3 features > testimonial > pricing teaser > CTA
- Type pairing and voice: serif display (tight tracking) + grotesk text; short, confident copy
- Color strategy: warm off-white, one saturated accent used only for primary actions
- Signature detail / effect: slow grain gradient behind the hero; numbers animate on scroll
- What to borrow: accent discipline, the hero layout
- What to avoid: low-contrast gray body text (3.3:1 in summary.md)
```

## Brand adjectives to effect vibes

| Brand words | Try vibes | Typical signature |
|---|---|---|
| calm, trustworthy, premium | calm, luxe | paper-mesh-gradient, view-transitions, modern-css |
| technical, precise, fast | techy | paper-dithering, cobe, scroll-driven, number-flow |
| warm, crafted, natural | organic, warm, editorial | paper-grain-gradient, paper-fluted-glass |
| playful, friendly | playful, warm | rive, dotlottie, react-bits text effects |
| bold, loud, launch | bold, dramatic | paper-god-rays, unicorn-studio, gsap split text |
| nostalgic, raw | retro, brutalist | paper-dithering, modern-css grain |

## direction.md

The template has: options considered (2-3), chosen direction and why, tokens, layout and
sections, signature effect and motion, principle checklist. Write options that differ in
substance (layout model, type voice, color strategy, motion level), not three shades of one
idea. Each option names what it borrows (`refs/<slug>`) and which principles it serves (`P#`).

## Tokens

- `front-design scale` writes a `/* front-design scale ... */ :root { --step-0 ... }` block; re-running
  with `--out` replaces only that block. Map h1..small to steps (for example h1 = step-5,
  h2 = step-3, body = step-0, small = step--1).
- Colors: name by role (`--bg`, `--surface`, `--text`, `--muted`, `--accent`, `--accent-contrast`,
  `--border`), define in `oklch()`, and give dark mode its own values instead of inverting.
- Check every pair you will actually use, including text on accent buttons and muted text on surfaces:
  `front-design contrast "oklch(0.25 0.02 60)" "#f6f1e9" "oklch(0.55 0.15 40)"`.

## Audit

Rendered mode (Playwright) checks:

- text contrast measured on real pixels (text hidden, background sampled under each text box),
  so text over gradients, images and shaders is covered; desktop and mobile;
- horizontal overflow at 390px; touch targets under 24x24 px that crowd neighbours (WCAG 2.5.8);
- links/buttons without accessible names, inputs without labels;
- keyboard focus visible (Tab through the page) and not hidden under sticky headers;
- motion under `prefers-reduced-motion: reduce` compared with normal (animations and rAF loops);
- console errors, CLS, page weight, WebGL canvas count;
- line length, line height, centered paragraphs, mobile body size;
- design-system drift: font families, distinct font sizes, spacing grid, stock accent, emoji.

Static checks (always): lang, title, viewport zoom, h1 and heading order, img alt, `<main>`,
autoplay video, positive tabindex, lorem ipsum, removed focus outlines, motion without a
reduced-motion path.

Score = 100 - 10 per error type - 3 per warning type. Pass = no errors and score >= 85.
Audit a local dev server URL (`http://localhost:3000`) or a built HTML file.

## Critique rubric (after the audit passes)

Score each 1-5 and fix anything under 4:

1. **Clarity in 5 seconds:** from the first desktop and mobile screenshot alone, can you tell what
   it is, who it is for and what to do next?
2. **Hierarchy:** one dominant element per view; the primary action is the most prominent control.
3. **Typography:** scale steps only; comfortable measure; display and text faces each doing one job.
4. **Color:** accent reserved for actions and key highlights; neutrals carry the layout.
5. **Rhythm and space:** consistent section padding; grouping by proximity, not by boxes.
6. **Craft:** states, focus, alignment, optical details (icon sizes, baseline alignment).
7. **Effect fit:** the signature effect expresses the brand adjectives, does not fight the content,
   and stops for reduced motion.
8. **Distinctiveness:** next to the best reference it holds up, and does not look like a template.
9. **Truthfulness:** no invented customers, metrics, testimonials or logos.

## Troubleshooting

- `playwright not installed`: `pip install "front-design[capture]"` and `python -m playwright install chromium`
  (falls back to the system Chrome if Chromium is missing). Without it, `capture --static` still
  reads HTML/CSS and `audit --static` runs the source checks.
- Fonts in a local `file://` build may not load from some CDNs; serve the folder
  (`python -m http.server -d build 8000`) and audit `http://localhost:8000`.
- Geo-redirects (a site serving another language) are normal; note it in notes.md.
