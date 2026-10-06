## UI/UX design with front-design

When asked to design, redesign or restyle a page, screen or component, or to research UI/UX,
use the `front-design` CLI (`front-design --help`). Research first, then design, then audit.

1. `front-design init "<brief>" --type <type> --stack <stack> --dir design/<slug>`; fill `brief.toml`
   (audience, primary action, 3 brand adjectives, constraints, competitors).
2. Principles: `front-design sources`; read the most relevant; record each rule with an exact quote:
   `front-design note add --source <key|url> --principle "..." --quote "..." --topic <t>` (fix not-found quotes).
3. References: `front-design refs`; `front-design capture <urls>`; read `refs/*/summary.md`, look at the
   screenshots, fill `refs/*/notes.md`; `front-design compare`.
4. Direction: 2-3 options in `direction.md` citing `P#` and `refs/<slug>`; pick one. Tokens:
   `front-design scale --space --out tokens.css`, `front-design contrast <pairs>`.
5. Effects: `front-design effects --vibe <v> --stack <s>`, `effects show <key>`, `effects pick <key> --why "..."`.
   One signature effect, reduced-motion path, aria-hidden canvases, pinned versions.
6. Build with real copy (no lorem, no invented social proof), then `front-design audit <file|url> --json`
   until it passes; look at `audit/shots/*.jpg` and critique against the principles.
7. `front-design dossier`; report direction, effects, audit score and anything unverified.

Never state a principle without a recorded source, never describe a reference from memory
(read tokens.json), never sign in, solve CAPTCHAs or bypass bot walls.
