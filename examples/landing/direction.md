# Design direction

## Options considered

### A. Field notebook (chosen)
- Idea: the page reads like a designer's research notebook: warm paper, serif display, mono figure captions, hairline rules, highlighter marks and verified-quote stamps. The evidence the tool produces is the visual material.
- Draws from: refs/paper-design (warm paper, hairline rules with corner ticks, two-tone headline), refs/linear-app (mono "FIG" captions, dividers instead of cards), refs/press-stripe-com (book-like serif italics, one rich material), refs/posthog-com (highlighter marks, tactile buttons), refs/resend-com (serif display for a developer audience).
- Honors: P1, P2 (descriptive tagline), P4 (front-loaded headings), P5/P6 (one accent, value contrast), P11 (measure), P14 (space, not boxes).
- Risk: could feel slow or academic; countered by a short hero and the install command in the first screen (P3).

### B. Lab instrument
- Idea: dark UI, dithering shader, numeric readouts (contrast ratios, type ratios) styled as instrument panels.
- Draws from: refs/linear-app, refs/resend-com (dark developer marketing).
- Honors: P5, P13.
- Risk: dark developer-tool look is the category default (3 of 6 references are dark per `compare`) and fights the brand adjective "warm".

### C. Specimen wall
- Idea: hero is a large collage of captured reference screenshots with measurements overlaid.
- Draws from: refs/impeccable-style (show the tool working), refs/press-stripe-com (objects as hero).
- Honors: P1 (shows real content).
- Risk: other companies' screenshots as our hero (brand and copyright issues), visual noise, LCP becomes heavy images (P13).

## Chosen direction and why

A. It expresses all three brand adjectives: rigorous (citations, figures, measured tables), crafted (book-like type, rules, details), warm (paper and vermilion ink). It differs from the direct competitor (refs/impeccable-style: condensed sans, yellow labels, white) while keeping category conventions every leader shares in `compare`: left-aligned hero, one filled primary CTA plus a text link, mono for commands.

## Tokens
- Type: display Newsreader (editorial serif with optical sizes, italic for second voices), text IBM Plex Sans, mono IBM Plex Mono (Plex pair = engineering rigor). Fluid scale 17px @360 ratio 1.2 to 19px @1440 ratio 1.333 (`design-scout scale`; reference sites range 1.25-1.44 for developer tools). h1 = step-5, h2 = step-3, h3 = step-1, body = step-0, captions = step--1.
- Color (oklch, contrast checked): paper, paper-2, ink, muted, rule, vermilion accent reserved for the primary action and verification stamps (P6), marker yellow for highlights only, green only for "verified" status.
- Space: Utopia space scale (space-3xs .. space-3xl), sections separated by hairline rules and space-2xl.
- Shape: radius 6px for controls, 2px for stamps; no drop shadows except the tactile primary button (P7, refs/posthog-com).

## Layout and sections
1. Hero: eyebrow, two-tone H1 "Research-first UI design / for your AI coding agent", subhead, install block with a filled Copy button (primary action), text link to the workflow. Right: FIG. 1 specimen plate with the live grain gradient and a caption.
2. The loop: seven numbered steps (01-07) with the real command for each, as a ruled list, not cards (P14).
3. Evidence: three principles this page was designed with, quoted from research/notes.json with verified stamps.
4. Measured references: FIG. 2 table of what `capture` measured on the six references for this page (fonts, body size, type ratio, accent).
5. Effects with manners: the libraries in the catalog plus the four rules (one signature, reduced motion, contrast on real pixels, pinned versions).
6. Audit: the real scores from the test fixtures and from this page.
7. Install again + agents supported + repo placeholder, footer.

## Signature effect and motion
- Signature: paper-grain-gradient inside the FIG. 1 plate only (organic, editorial, warm vibes). It is decorative (aria-hidden), loads after the text (LCP stays the H1, P13), speed 0 under reduced motion (P9).
- Supporting: scroll-driven (native CSS) highlighter that draws under key phrases as they enter view; purpose: points at the words that matter (P5, P10). Gated by @supports and reduced motion.
- Supporting: modern-css (text-wrap balance/pretty, oklch, color-mix).
- Motion rules: 200-300 ms ease-out for UI state, no animation on keyboard-driven actions (P10, refs: emil-no-animations), no smooth-scroll hijacking.

## Principle checklist (fill during critique)
| Principle | Where it is honored | Status |
|---|---|---|
| P1 tagline says what it does | eyebrow + H1 "Research-first UI design for your AI coding agent" | done |
| P2 descriptive header | H1 names the product category and audience; no slogan | done |
| P3 first two screenfuls | install block fully visible in the first desktop viewport (audit desktop-01) | done |
| P4 front-loaded headings | "Seven steps...", "Principles with sources...", "Measured, not remembered" | done |
| P5 value/saturation hierarchy | ink vs muted (6.3:1) carry hierarchy; color only in accent and stamps | done |
| P6 one accent | vermilion only on Install/Copy buttons; green only on verified stamps | done |
| P7 strong signifiers | filled tactile buttons, underlined links, no ghost CTAs | done |
| P8 contrast | all pairs checked with `contrast`; audit sampled 201 desktop + 51 mobile text boxes, 0 failures | done |
| P9 reduced motion | audit: rAF 20/s and 3 animations normally, 0 and 0 with reduce | done |
| P10 purposeful motion | one shader in a frame + highlighter on key phrases below the fold | done |
| P11 measure | lede and section copy capped at 62ch; audit found no line over 90 chars | done |
| P12 fluid scale | `design-scout scale` 17/1.2 to 19/1.333; H1 one step down in the two-column layout | done |
| P13 LCP | LCP element is a text paragraph at 232 ms locally; shader mounts after load | done |
| P14 space not boxes | hairline rules and columns; no card grid anywhere | done |
