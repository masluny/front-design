---
name: design-scout
description: Research-first UI/UX design. Use whenever the user asks to design, redesign or restyle a website, landing page, app screen, dashboard or UI component, wants a UI to look professional, modern or less generic, or asks for UI/UX research, inspiration or a design critique. Before designing it reads respected expert sources (NN/g, Baymard, WCAG, web.dev, Butterick, Utopia...) and records verified principles, captures and measures professional reference sites (screenshots plus computed fonts, palette, type scale, spacing and effect libraries), then designs with a curated catalog of modern effects (Paper Shaders, Unicorn Studio, GSAP, Motion, Lenis, React Bits, Magic UI, View Transitions...) and audits the result (contrast on real pixels, touch targets, focus, reduced motion, mobile overflow) until it passes.
---

# design-scout: research first, then design

You (the agent) make the design judgments and write the code. The `design-scout` CLI does
what must be objective: listing trusted sources, verifying quotes against the source page,
measuring reference sites, computing type scales and contrast, and auditing the result.

- Never state a design principle you did not read in a source recorded with `note add`.
- Never describe a reference site's fonts, colors or libraries from memory: read its `tokens.json` / `summary.md`.
- Look at screenshots (desktop and mobile) before writing observations or judging your own build.

Check the CLI first: `design-scout --version` (missing: `pip install -e <path-to-design-scout>[capture]`
then `python -m playwright install chromium`; `design-scout doctor` shows what works).
Full command reference, templates and the critique rubric: `WORKFLOW.md` next to this file.
Read it before the first run in a session.

## Scale the process to the task

| Task | Principles | References | Deliverables |
|---|---|---|---|
| New page, site or redesign | 8+ (at least 4 research/standard) | 5-8 | all phases + dossier |
| One section or screen | 4+ | 3 | phases 1-6, dossier if asked |
| Component or small tweak | 2 | 1-2 (or none) | effects/tokens as needed, audit |

## The loop

0. **Brief.** `design-scout init "<brief>" --type <type> --stack <stack> --dir design/<slug>`, then `cd` there.
   Fill `brief.toml`: audience, the ONE primary action, 3 brand adjectives, constraints (existing
   brand, WCAG level, budget), competitor URLs. Ask the user at most 3 questions, and only for
   facts that change the design (audience, brand adjectives, must-keep assets); otherwise write
   your assumptions into the brief and say so.

1. **Principles from experts.** `design-scout sources` lists the curated sources for this page type,
   strongest evidence first (research > standard > guideline > craft). Read the 6-10 most relevant
   with your web tools. Also search the web for research on this exact problem (for example
   "NN/g pricing page", "Baymard product page", "WCAG focus appearance") and prefer studies over
   opinion. Record each actionable rule with the exact words from the page:
   `design-scout note add --source <key|url> --topic <topic> --principle "<rule in your words>" --quote "<exact words>"`.
   A `not-found` quote must be fixed (copy the exact words) or dropped. Include at least one
   source that argues against your instinct (for example `emil-no-animations` before adding effects).

2. **Professional references.** `design-scout refs` lists galleries and exemplar sites. Pick a mix:
   3-4 category leaders or competitors, 2-3 taste references found by browsing galleries (Recent,
   Awwwards, Land-book, Mobbin...), 1 wildcard from another field. Then
   `design-scout capture <url> <url> ...` and for every reference: read `refs/<slug>/summary.md`,
   look at `desktop-*.jpg` and `mobile-*.jpg`, and fill `refs/<slug>/notes.md` (layout, hero
   pattern, section sequence, type pairing, color strategy, signature detail, what to borrow,
   what to avoid). `design-scout compare` shows shared conventions (keep them: users expect them)
   and differentiators (where you can stand out).

3. **Direction and tokens.** In `direction.md` write 2-3 genuinely different directions, each citing
   references (`refs/<slug>`) and principles (`P#`). Choose one: if the user is present, show a short
   comparison and let them pick; otherwise pick and justify. Lock tokens in `tokens.css`:
   - type: `design-scout scale --min-base 16 --max-base 19 --min-ratio 1.2 --max-ratio 1.25 --space --out tokens.css`
     (ratios informed by `compare`); at most two families plus mono, with a pairing rationale;
   - color: define the palette in `oklch()`; run `design-scout contrast <text> <bg> ...` for every
     text/background pair (AA: 4.5:1 body, 3:1 large text and UI);
   - space, radius, shadow, motion durations/easing as tokens. No magic numbers in components.

4. **Modern effects.** `design-scout effects --vibe <brand adjective> --stack <stack>`, then
   `design-scout effects show <key>` for the snippet, a11y and perf notes, then
   `design-scout effects pick <key> --role signature --why "<how it expresses the brand>"`.
   - One signature effect per page; at most two supporting ones. Effects serve the brand
     adjectives and the content, never decoration for its own sake.
   - Every effect has a reduced-motion path (speed 0, static frame, no smooth scroll).
   - Decorative canvases are `aria-hidden`; text over an effect must pass contrast on its
     brightest and darkest frame (add a scrim or surface if not).
   - Pin the version from the catalog and re-check props on the docs page before use.
   - The LCP element stays text or an image, not a canvas; lazy-load below-the-fold effects.

5. **Build.** In the user's stack; with no stack, a single `build/index.html` (ESM imports from
   jsDelivr are fine). Real copy, never lorem ipsum, and never invented customers, logos,
   testimonials or statistics: use clearly marked placeholders instead. Semantic HTML, mobile
   first, every state designed (hover, focus-visible, active, disabled, loading, empty, error).

6. **Audit and critique loop.** `design-scout audit <file-or-url> --json`. Fix errors first, then
   warnings; re-run until `pass` is true (max 5 rounds). Then look at `audit/shots/*.jpg` and
   critique like a senior designer: fill the principle checklist in `direction.md` (each `P#`:
   where is it honored?), apply the rubric in WORKFLOW.md, and put your best screenshot next to
   the best reference's. If yours would not hold up, fix and re-audit. Never "fix" an audit
   finding by hiding content or removing a true state.

7. **Deliver.** `design-scout dossier` writes `dossier.html` (brief, principles with verified
   quotes, reference moodboard, comparison, direction, tokens, effects, audit). Tell the user: the
   chosen direction and why (cite references and principles), effects used, the audit score,
   what could not be verified (blocked sources, login-only galleries), and open questions.

## Avoid the generic AI look (unless the brief asks for it)

- Stock Tailwind indigo/violet as the brand accent; purple-blue gradients by default.
- One sans for everything with no reason; ten or more font sizes; spacing off any scale.
- Everything centered; three identical icon-title-text cards as the whole features story.
- Emoji as icons; vague hero copy ("Unlock the power of..."); fake social proof.
- Glass or blur over busy backgrounds; several WebGL canvases competing in one viewport.
- Copying a reference: borrow patterns, never logos, illustrations, copy or a brand's exact
  palette-plus-font combination.

## Hard rules

- Every decision in `direction.md` points to a principle (`P#`) or a reference (`refs/<slug>`).
- Stay polite on the web: no logins, no CAPTCHAs, no bypassing bot walls; if a site blocks the
  capture, choose another reference and mention it.
- Report the audit score honestly, including warnings you chose to keep and why.
