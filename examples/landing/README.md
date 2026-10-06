# Example: front-design's own landing page

A complete run of the front-design skill, from brief to audited page.

| Step | File |
|---|---|
| Brief | [brief.toml](brief.toml) |
| 14 principles, every quote verified against the source page | [research/notes.json](research/notes.json) |
| 6 references: measured tokens and written observations | [refs/](refs) |
| 3 directions, the chosen one, principle checklist | [direction.md](direction.md) |
| Tokens (fluid type and space scale, OKLCH palette) | [tokens.css](tokens.css) |
| Effects: Paper Shaders Grain Gradient + scroll-driven highlighter | [effects.json](effects.json) |
| The page | [build/index.html](build/index.html) |
| Audit: 100/100, motion stops under reduced motion, LCP is text | [audit/latest.json](audit/latest.json) |

Open `build/index.html` in a browser, or serve the folder:

```bash
python -m http.server -d examples/landing 8000
```

Screenshots of the reference sites are not committed (they are third-party pages);
`front-design capture <url>` recreates them locally. To rebuild the dossier:

```bash
cd examples/landing && front-design capture https://impeccable.style/ https://resend.com https://paper.design/ https://linear.app https://press.stripe.com https://posthog.com && front-design dossier
```

Note: re-capturing overwrites `refs/*/summary.md` and `tokens.json` with fresh measurements, but keeps
the written `notes.md`.
