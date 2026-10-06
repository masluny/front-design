# PostHog - your product’s context layer

- URL: https://posthog.com/
- Mode: rendered
- Description: PostHog automatically diagnoses problems, fixes bugs, and generates pull requests - all without you having to prompt it.
- Theme: light

## Typography
- RoundHog (sans, body/ui, 99% of text) weights 500, 600, 700, 800
- Source Code Pro (mono, code, 1% of text) weights 500
- Body 18px / line-height 1.5; H1 36.0px; scale ratio 1.184 ~minor third (1.2); 8 distinct sizes in use

## Color
- Page background #eeefe9; surfaces: #eeefe9 warm light gray 71%, #ffffff white 18%, #b62ad9 magenta 9%, #eb9d2a orange 1%, #cd8407 orange 1%, #53ffcb pale teal 0%
- Text: #374151 dark blue 45%, #111111 near-black 22%, #65675e warm gray 15%, #111827 dark blue 12%, #ffffff white 3%, #000000 near-black 2%
- Body text contrast: 8.91:1
- Accent(s): #cd8407 orange 50%, #eb9d2a orange 25%, #b62ad9 magenta 20%, #f54e00 red 4%
- Gradient backgrounds: 5

## Space and shape
- Base unit: none (on-grid 57%); common: [8.0, 6.0, 2.0, 4.0, 12.0, 24.0, 4.4, 4.1, 16.0, 32.0]
- Radii: 4px (24%), 40% (21%), 6px (18%), 2px (12%), 5.64506px (9%)
- Distinct shadows: 5
- Content width: 1024.0px; sections: 1; sticky header: False; page height: 1.0 viewports

## Content
- h1: Your product's context layer (36px)
- h3: Set up for free (18px)
- h3: What can I help you with? (20.5275px)
- h2: Ask PostHog anything (24px)
- h2: Social proof (30px)
- h2: All your data, working together (30px)
- h2: Usage-based pricing (30px)
- h2: Why PostHog? (30px)
- CTAs: "Get started - free" (filled, r=6px, h=32px); "Get started" (filled, r=8px, h=47px); "Install with AI" (filled, r=8px, h=47px); "Ask PostHog anything" (filled, r=6px, h=40px); "Get started - free" (filled, r=6px, h=35px); "Open Customers" (filled, r=6px, h=35px)
- Nav: Home | Self-driving product | Context warehouse | Pricing | Docs | Demo | Talk to a human | About us | Changelog | Company handbook

## Stack and effects
- effects: Swiper
- framework: Gatsby
- styling: Tailwind CSS, Radix UI
- Media: images 22, svgs 205, sections 1, buttons 22, links 138
- Motion: 24 running animations, 60 @keyframes, reduced-motion CSS: True
- Modern CSS: container_queries (110), has_selector (2), color_mix (4), clamp (11), backdrop_filter (12), text_wrap_balance (5), cascade_layers (2), css_grid (48), keyframes (60), reduced_motion_media (9), variable_fonts (18)
- 7 CSS custom properties on :root (see tokens.json)
- Perf (this run, unthrottled): LCP 1292 ms (img), CLS 0.116, 111 requests, 6784 kB
