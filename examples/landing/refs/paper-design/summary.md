# Paper - design, share, ship

- URL: https://paper.design/
- Mode: rendered
- Description: Paper is a modern and powerful design tool that helps you create, share, and ship your best work.
- Theme: light

## Typography
- Matter (display/other, body/ui, 65% of text) weights 360, 400, 480, 500, 550, 570, 670
- -apple-system (sans, body/ui, 17% of text) weights 400, 500
- Inter (sans, body/ui, 16% of text) weights 400
- Paper Mono (mono, body/ui, 2% of text) weights 400
- Body 18px / line-height 1.56; H1 64.0px; scale ratio 1.886 ~golden ratio (1.618); 5 distinct sizes in use

## Color
- Page background #efefe4; surfaces: #efefe4 warm light gray 97%, #ffffff white 1%, #dcdee1 light gray 1%, #bdbfc3 light gray 0%, #181818 dark gray 0%, #86b9ff blue 0%
- Text: #181818 dark gray 43%, #666666 gray 34%, #000000 near-black 14%, #909090 gray 5%, #fcfcf9 white 2%, #797979 gray 1%
- Body text contrast: 4.96:1
- Gradient backgrounds: 7

## Space and shape
- Base unit: 4 (on-grid 75%); common: [8.0, 4.0, 12.0, 2.0, 40.0, 24.0, 6.0, 10.0, 16.0, 1.0]
- Radii: 5px (39%), 4px (27%), 8px (7%), 2px (7%), 12px (5%)
- Distinct shadows: 13
- Content width: 600.0px; sections: 10; sticky header: True; page height: 10.3 viewports

## Content
- h1: design incredible (48px)
- h2: the connected canvas for teams shipping with agents (48px)
- h2: Introducing Paper Desktop a fully connected canvas, a whole new workflow (48px)
- h2: finally a continuous loop, from Paper to code and back (48px)
- h3: connect any agent to your canvas (18px)
- h3: design and code, one language (18px)
- h2: connected to real content, real data, from anywhere (48px)
- h3: prompt to get data from anywhere (18px)
- CTAs: "download Paper" (filled, r=4px, h=40px); "download for macOS" (filled, r=4px, h=42px)
- Nav: pricing | roadmap | blog | changelog | docs | sign up | open Paper →

## Stack and effects
- effects: Paper Shaders, CSS scroll-driven animations
- framework: Next.js
- styling: Tailwind CSS
- Media: images 124, svgs 246, canvases 12, sections 10, buttons 9, links 45, webgl_canvases 7
- Motion: 3 running animations, 13 @keyframes, reduced-motion CSS: False
- Modern CSS: has_selector (42), oklch (2), color_mix (363), clamp (2), scroll_driven (1), backdrop_filter (11), at_property (142), text_wrap_balance (6), cascade_layers (11), css_grid (7), keyframes (13), dark_mode_media (40), variable_fonts (10)
- 87 CSS custom properties on :root (see tokens.json)
- Perf (this run, unthrottled): LCP 292 ms (span), CLS 0, 142 requests, 4330 kB
