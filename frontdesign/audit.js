// Audit helpers injected into the page under test. Exposes window.__ds with small functions
// that the Python side calls per viewport / per check.
(() => {
  const transparent = (c) => !c || c === 'transparent' || /rgba?\([^)]*,\s*0\)$/.test(c) || /\/\s*0\)$/.test(c);
  const visible = (el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) < 0.1) return false;
    const r = el.getBoundingClientRect();
    return r.width >= 1 && r.height >= 1;
  };
  const effectiveOpacity = (el) => {
    let o = 1;
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) o *= parseFloat(getComputedStyle(e).opacity);
    return o;
  };
  const sel = (el) => {
    if (el.id) return '#' + el.id;
    let s = el.tagName.toLowerCase();
    if (el.classList.length) s += '.' + [...el.classList].slice(0, 2).join('.');
    const p = el.parentElement;
    return p && p !== document.body ? (p.id ? '#' + p.id : p.tagName.toLowerCase()) + ' > ' + s : s;
  };
  const bgGuess = (el) => {
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') return { color: null, over_media: true };
      if (!transparent(cs.backgroundColor)) return { color: cs.backgroundColor, over_media: false };
    }
    return { color: 'rgb(255, 255, 255)', over_media: false };
  };
  const accName = (el) => {
    const label = el.getAttribute('aria-label');
    if (label && label.trim()) return label.trim();
    const lb = el.getAttribute('aria-labelledby');
    if (lb) { const t = lb.split(/\s+/).map(id => document.getElementById(id)?.innerText || '').join(' ').trim(); if (t) return t; }
    const t = (el.innerText || el.value || '').trim();
    if (t) return t;
    const img = el.querySelector('img[alt]');
    if (img && img.alt.trim()) return img.alt.trim();
    const svgTitle = el.querySelector('svg title');
    if (svgTitle && svgTitle.textContent.trim()) return svgTitle.textContent.trim();
    return (el.getAttribute('title') || '').trim();
  };

  window.__ds = {
    textInViewport() {
      const out = [];
      const vh = innerHeight, vw = innerWidth;
      for (const el of document.body.querySelectorAll('*')) {
        if (out.length >= 400) break;
        let direct = '';
        for (const c of el.childNodes) if (c.nodeType === 3) direct += c.textContent;
        direct = direct.replace(/\s+/g, ' ').trim();
        if (direct.length < 2 || !visible(el)) continue;
        if (el.closest('[disabled], [aria-disabled="true"], noscript')) continue;
        const r = el.getBoundingClientRect();
        if (r.top < 0 || r.bottom > vh || r.left < 0 || r.right > vw + 1) continue;
        // skip text covered by another element (e.g. scrolled under a sticky header)
        const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
        const hit = document.elementFromPoint(cx, cy);
        if (hit && hit !== el && !el.contains(hit) && !hit.contains(el)) continue;
        const cs = getComputedStyle(el);
        const op = effectiveOpacity(el);
        if (op < 0.1) continue;
        const bg = bgGuess(el);
        // sample the content box only: borders and padding are not the text's background
        const inset = (a, b) => (parseFloat(cs[a]) || 0) + (parseFloat(cs[b]) || 0);
        const x0 = r.left + inset('borderLeftWidth', 'paddingLeft'), x1 = r.right - inset('borderRightWidth', 'paddingRight');
        const y0 = r.top + inset('borderTopWidth', 'paddingTop'), y1 = r.bottom - inset('borderBottomWidth', 'paddingBottom');
        out.push({
          sel: sel(el), text: direct.slice(0, 60), color: cs.color, opacity: op,
          size: parseFloat(cs.fontSize), weight: parseInt(cs.fontWeight) || 400,
          rect: [Math.max(0, Math.min(x0, x1 - 1)), Math.max(0, Math.min(y0, y1 - 1)), Math.min(vw, Math.max(x1, x0 + 1)), Math.min(vh, Math.max(y1, y0 + 1))],
          bg: bg.color, over_media: bg.over_media,
          decorative: !!el.closest('[aria-hidden="true"]'),
        });
      }
      return out;
    },
    targets() {
      const q = 'a[href], button, input:not([type="hidden"]), select, textarea, summary, [role="button"], [role="link"], [role="tab"], [role="checkbox"], [role="switch"], [tabindex]:not([tabindex="-1"])';
      const items = [];
      for (const el of document.querySelectorAll(q)) {
        if (!visible(el)) continue;
        const r = el.getBoundingClientRect();
        // inline links inside running text are exempt (WCAG 2.5.8 "inline" exception)
        let inline = false;
        if (el.tagName === 'A' && getComputedStyle(el).display === 'inline') {
          const p = el.parentElement;
          const txt = p ? [...p.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim() : '';
          inline = txt.length > 20;
        }
        items.push({ sel: sel(el), w: r.width, h: r.height, cx: r.left + r.width / 2, cy: r.top + scrollY + r.height / 2,
                     inline, name: accName(el).slice(0, 40), tag: el.tagName.toLowerCase() });
      }
      return items;
    },
    unnamedControls() {
      const out = [];
      for (const el of document.querySelectorAll('a[href], button, [role="button"], [role="link"]')) {
        if (!visible(el) || el.closest('[aria-hidden="true"]')) continue;
        if (!accName(el)) out.push(sel(el));
      }
      return out;
    },
    unlabeledInputs() {
      const out = [];
      for (const el of document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"]):not([type="image"]), select, textarea')) {
        if (!visible(el)) continue;
        const labelled = el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || el.closest('label') ||
          (el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`)) || el.getAttribute('title');
        if (!labelled) out.push({ sel: sel(el), placeholder_only: !!el.getAttribute('placeholder') });
      }
      return out;
    },
    paragraphs() {
      const out = [];
      const canvas = document.createElement('canvas').getContext('2d');
      for (const p of document.querySelectorAll('p, li')) {
        if (p.tagName === 'LI' && p.querySelector('p, div, h1, h2, h3, h4, ul, ol, table, pre')) continue;  // only running text
        const t = (p.innerText || '').replace(/\s+/g, ' ').trim();
        if (t.length < 120 || !visible(p)) continue;
        const cs = getComputedStyle(p);
        canvas.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
        const sample = t.slice(0, 200);
        const avg = canvas.measureText(sample).width / sample.length;
        const fs = parseFloat(cs.fontSize);
        const lh = cs.lineHeight === 'normal' ? fs * 1.2 : parseFloat(cs.lineHeight);
        out.push({ sel: sel(p), size: fs, line_height: lh / fs, chars_per_line: Math.round(p.clientWidth / avg),
                   centered: cs.textAlign === 'center' && p.getBoundingClientRect().height > lh * 3.2 });
        if (out.length >= 80) break;
      }
      return out;
    },
    overflowers() {
      const out = [];
      const vw = document.documentElement.clientWidth;
      const clipped = (el) => {  // inside a scroll/clip container: does not widen the page
        for (let e = el.parentElement; e && e !== document.body; e = e.parentElement) {
          const ox = getComputedStyle(e).overflowX;
          if (ox !== 'visible') return true;
        }
        return false;
      };
      for (const el of document.body.querySelectorAll('*')) {
        const r = el.getBoundingClientRect();
        if (r.right > vw + 1 && r.width > 0 && visible(el) && !clipped(el)) {
          const pr = el.parentElement ? el.parentElement.getBoundingClientRect() : null;
          if (!pr || pr.right <= vw + 1) out.push({ sel: sel(el), right: Math.round(r.right), width: Math.round(r.width) });
        }
        if (out.length >= 6) break;
      }
      return { scroll_width: document.documentElement.scrollWidth, viewport: vw, offenders: out };
    },
    focusState() {
      const el = document.activeElement;
      if (!el || el === document.body) return null;
      const keys = ['outlineStyle', 'outlineWidth', 'outlineColor', 'boxShadow', 'backgroundColor', 'borderTopColor', 'textDecorationLine', 'color', 'transform'];
      const snap = () => { const cs = getComputedStyle(el); return keys.map(k => cs[k]).join('|'); };
      const focused = snap();
      const r = el.getBoundingClientRect();
      // is it hidden under a sticky/fixed element?
      let obscured = false;
      const cx = r.left + r.width / 2, cy = r.top + Math.min(r.height / 2, 8);
      if (cy >= 0 && cy <= innerHeight) {
        const top = document.elementFromPoint(cx, cy);
        if (top && top !== el && !el.contains(top) && !top.contains(el)) {
          const pos = getComputedStyle(top).position;
          obscured = pos === 'fixed' || pos === 'sticky';
        }
      }
      el.blur();
      const blurred = snap();
      return { sel: sel(el), changed: focused !== blurred, obscured };
    },
    motionProbe() {
      const anims = document.getAnimations ? document.getAnimations().filter(a => a.playState === 'running').length : 0;
      return { animations: anims, raf: window.__dsRaf || 0 };
    },
  };
})();
