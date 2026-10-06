## UI/UX design with design-scout

When asked to design, redesign or restyle a page, screen or component, or to research UI/UX,
use the `design-scout` CLI (`design-scout --help`). Research first, then design, then audit.

1. `design-scout init "<brief>" --type <type> --stack <stack> --dir design/<slug>`; fill `brief.toml`
   (audience, primary action, 3 brand adjectives, constraints, competitors).
2. Principles: `design-scout sources`; read the most relevant; record each rule with an exact quote:
   `design-scout note add --source <key|url> --principle "..." --quote "..." --topic <t>` (fix not-found quotes).
3. References: `design-scout refs`; `design-scout capture <urls>`; read `refs/*/summary.md`, look at the
   screenshots, fill `refs/*/notes.md`; `design-scout compare`.
4. Direction: 2-3 options in `direction.md` citing `P#` and `refs/<slug>`; pick one. Tokens:
   `design-scout scale --space --out tokens.css`, `design-scout contrast <pairs>`.
5. Effects: `design-scout effects --vibe <v> --stack <s>`, `effects show <key>`, `effects pick <key> --why "..."`.
   One signature effect, reduced-motion path, aria-hidden canvases, pinned versions.
6. Build with real copy (no lorem, no invented social proof), then `design-scout audit <file|url> --json`
   until it passes; look at `audit/shots/*.jpg` and critique against the principles.
7. `design-scout dossier`; report direction, effects, audit score and anything unverified.

Never state a principle without a recorded source, never describe a reference from memory
(read tokens.json), never sign in, solve CAPTCHAs or bypass bot walls.
