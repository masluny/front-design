// Runs inside the page (Playwright page.evaluate). Collects computed design data.
// Returns plain JSON; aggregation keeps the payload small.
async (globalsToProbe) => {
  const vw = innerWidth, vh = innerHeight;
  const docH = Math.max(document.documentElement.scrollHeight, document.body ? document.body.scrollHeight : 0);
  const out = {
    text: {}, bg: {}, radii: {}, shadows: {}, spacing: {}, gaps: {}, maxw: {},
    gradients: 0, gradient_samples: [], headings: [], ctas: [], nav: [], counts: {},
    sticky_header: false, fonts_loaded: [], center_paragraphs: 0, borders: {},
  };
  const inc = (obj, k, by = 1) => { obj[k] = (obj[k] || 0) + by; };
  const transparent = (c) => !c || c === 'transparent' || /rgba?\([^)]*,\s*0\)$/.test(c) || /\/\s*0\)$/.test(c);

  const roleOf = (el, tag) => {
    if (/^h[1-6]$/.test(tag)) return tag;
    if (el.closest('pre, code, kbd, samp')) return 'code';
    if (el.closest('button, [role="button"], input[type="submit"]')) return 'button';
    if (el.closest('nav, header')) return 'nav';
    if (el.closest('a')) return 'link';
    if (el.closest('footer')) return 'footer';
    if (tag === 'small' || el.closest('small, figcaption, label')) return 'small';
    return 'text';
  };

  const all = [document.documentElement, document.body, ...document.body.querySelectorAll('*')];
  let n = 0;
  for (const el of all) {
    if (n > 8000) break;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    n++;
    const tag = el.tagName.toLowerCase();
    let direct = '';
    for (const c of el.childNodes) if (c.nodeType === 3) direct += c.textContent;
    direct = direct.replace(/\s+/g, ' ').trim();
    if (direct.length && parseFloat(cs.opacity) > 0.05) {
      const fam = cs.fontFamily.split(',')[0].replace(/["']/g, '').trim();
      const key = [fam, cs.fontSize, cs.fontWeight, cs.lineHeight, cs.letterSpacing, cs.color,
                   cs.textTransform, roleOf(el, tag), cs.fontFamily.slice(0, 160)].join('|');
      inc(out.text, key, direct.length);
      if (tag === 'p' && cs.textAlign === 'center' && r.height > parseFloat(cs.lineHeight || cs.fontSize) * 3.2) out.center_paragraphs++;
    }
    const bgc = cs.backgroundColor;
    if (!transparent(bgc)) inc(out.bg, bgc, Math.min(r.width, vw) * Math.min(r.height, docH));
    if (cs.backgroundImage && cs.backgroundImage.includes('gradient')) {
      out.gradients++;
      if (out.gradient_samples.length < 6) out.gradient_samples.push(cs.backgroundImage.slice(0, 240));
    }
    const rad = cs.borderTopLeftRadius;
    if (rad && rad !== '0px' && r.width > 16) inc(out.radii, rad);
    if (cs.boxShadow && cs.boxShadow !== 'none') inc(out.shadows, cs.boxShadow.slice(0, 200));
    if (cs.borderTopStyle !== 'none' && parseFloat(cs.borderTopWidth) > 0 && !transparent(cs.borderTopColor)) inc(out.borders, cs.borderTopColor);
    for (const p of ['paddingTop', 'paddingBottom', 'paddingLeft', 'paddingRight', 'marginTop', 'marginBottom']) {
      const v = cs[p];
      if (v && v !== '0px' && !v.startsWith('-')) inc(out.spacing, v);
    }
    for (const p of ['rowGap', 'columnGap']) {
      const v = cs[p];
      if (v && v !== 'normal' && v !== '0px') inc(out.gaps, v);
    }
    if (cs.maxWidth && cs.maxWidth.endsWith('px')) {
      const mw = parseFloat(cs.maxWidth);
      if (mw >= 480 && mw <= 2400) inc(out.maxw, cs.maxWidth);
    }
    if ((cs.position === 'sticky' || cs.position === 'fixed') && r.top <= 8 && r.width > vw * 0.8 && r.height < 180) out.sticky_header = true;
  }
  out.elements_scanned = n;

  for (const h of [...document.querySelectorAll('h1, h2, h3')].slice(0, 24)) {
    const cs = getComputedStyle(h);
    let t = h.innerText.replace(/\s+/g, ' ').trim();
    const half = t.length / 2;  // "Title Title" from visually hidden duplicates
    if (t.length > 8 && t.length % 2 === 1 && t.slice(0, half - 0.5) === t.slice(half + 0.5)) t = t.slice(0, half - 0.5);
    if (!t || out.headings.some(x => x.text === t.slice(0, 140))) continue;
    out.headings.push({ tag: h.tagName.toLowerCase(), text: t.slice(0, 140), size: cs.fontSize,
                        weight: cs.fontWeight, family: cs.fontFamily.split(',')[0].replace(/["']/g, '').trim(),
                        tracking: cs.letterSpacing, line_height: cs.lineHeight });
  }

  const ctaSeen = new Set();
  const CONSENT = /cookie|consent|accept all|reject all|allow all|decline|aceptar|rechazar|akceptuj|odrzu|zustimmen|ablehnen|accepter|refuser|tout accepter/i;
  for (const el of document.querySelectorAll('a, button')) {
    if (out.ctas.length >= 14) break;
    const r = el.getBoundingClientRect();
    const top = r.top + scrollY;
    if (r.width < 40 || r.height < 24 || top > vh * 2.2) continue;
    const cs = getComputedStyle(el);
    const filled = !transparent(cs.backgroundColor) || cs.backgroundImage.includes('gradient');
    const outlined = cs.borderTopStyle !== 'none' && parseFloat(cs.borderTopWidth) > 0 && !transparent(cs.borderTopColor);
    if (!filled && !outlined) continue;
    const t = (el.innerText || el.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim();
    if (!t || t.length > 40 || ctaSeen.has(t) || CONSENT.test(t)) continue;
    ctaSeen.add(t);
    out.ctas.push({ text: t, bg: cs.backgroundColor, color: cs.color, radius: cs.borderTopLeftRadius,
                    height: Math.round(r.height), padding_x: cs.paddingLeft, weight: cs.fontWeight,
                    above_fold: top < vh, style: filled ? 'filled' : 'outline' });
  }

  for (const a of [...document.querySelectorAll('header a, nav a')].slice(0, 40)) {
    const t = (a.innerText || '').replace(/\s+/g, ' ').trim();
    if (t && t.length < 32 && !out.nav.includes(t)) out.nav.push(t);
    if (out.nav.length >= 14) break;
  }

  const q = (s) => document.querySelectorAll(s).length;
  let container = document.querySelector('main') || document.body;
  for (let depth = 0; depth < 5; depth++) {  // descend through single-child wrappers
    const tall = [...container.children].filter(c => c.getBoundingClientRect().height > 240);
    if (tall.length !== 1) break;
    container = tall[0];
  }
  const sections = [...container.children].filter(c => c.getBoundingClientRect().height > 240).length;
  out.counts = { images: q('img'), videos: q('video'), svgs: q('svg'), canvases: q('canvas'),
                 iframes: q('iframe'), sections, forms: q('form'), buttons: q('button'), links: q('a'),
                 webgl_canvases: [...document.querySelectorAll('canvas')].filter(c => {
                   try { return !!(c.getContext('webgl2') || c.getContext('webgl')); } catch (e) { return false; }
                 }).length };

  try {
    out.fonts_loaded = [...document.fonts].filter(f => f.status === 'loaded')
      .map(f => ({ family: f.family.replace(/["']/g, ''), weight: f.weight, style: f.style }));
  } catch (e) {}

  // stylesheet text that is readable from JS (covers CSS-in-JS insertRule)
  let cssText = '';
  for (const sheet of document.styleSheets) {
    try { for (const rule of sheet.cssRules) { cssText += rule.cssText + '\n'; if (cssText.length > 3e6) break; } }
    catch (e) {}
  }
  out.css_text = cssText;
  out.animations_running = (document.getAnimations ? document.getAnimations().length : 0);
  out.globals = (globalsToProbe || []).filter(k => { try { return k in window; } catch (e) { return false; } });
  out.scripts = [...document.scripts].map(s => s.src).filter(Boolean);
  out.title = document.title;
  out.lang = document.documentElement.lang || '';
  out.meta = {};
  for (const m of document.querySelectorAll('meta[name], meta[property]')) {
    const k = (m.getAttribute('name') || m.getAttribute('property')).toLowerCase();
    if (['description', 'generator', 'theme-color', 'og:image', 'viewport', 'og:title'].includes(k)) out.meta[k] = m.content;
  }
  const html = document.documentElement, body = document.body;
  out.page_bg = getComputedStyle(body).backgroundColor;
  out.root_bg = getComputedStyle(html).backgroundColor;
  out.doc = { width: html.scrollWidth, height: docH, viewport_w: vw, viewport_h: vh };

  // performance
  const perf = {};
  try {
    const nav = performance.getEntriesByType('navigation')[0];
    if (nav) { perf.dom_content_loaded_ms = Math.round(nav.domContentLoadedEventEnd); perf.load_ms = Math.round(nav.loadEventEnd); }
    const res = performance.getEntriesByType('resource');
    perf.requests = res.length + 1;
    perf.transfer_kb = Math.round((res.reduce((s, r) => s + (r.transferSize || 0), 0) + (nav ? nav.transferSize || 0 : 0)) / 1024);
    const byType = {};
    for (const r of res) byType[r.initiatorType] = (byType[r.initiatorType] || 0) + (r.transferSize || 0);
    perf.kb_by_type = Object.fromEntries(Object.entries(byType).map(([k, v]) => [k, Math.round(v / 1024)]));
    const observe = (type) => new Promise((resolve) => {
      const list = [];
      try {
        const po = new PerformanceObserver((l) => list.push(...l.getEntries()));
        po.observe({ type, buffered: true });
        setTimeout(() => { po.disconnect(); resolve(list); }, 150);
      } catch (e) { resolve(list); }
    });
    const lcp = await observe('largest-contentful-paint');
    if (lcp.length) {
      const last = lcp[lcp.length - 1];
      perf.lcp_ms = Math.round(last.startTime);
      perf.lcp_element = last.element ? (last.element.tagName.toLowerCase() + (last.element.id ? '#' + last.element.id : '')) : null;
    }
    const shifts = await observe('layout-shift');
    perf.cls = Math.round(shifts.filter(s => !s.hadRecentInput).reduce((s, e) => s + e.value, 0) * 1000) / 1000;
  } catch (e) {}
  out.perf = perf;
  return out;
}
