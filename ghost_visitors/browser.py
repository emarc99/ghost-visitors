"""A ghost's body: a Playwright browser set up like the persona's device, plus code that measures.

The model decides where to go. This module does the going, and measures what it finds with plain
code, so every complaint in the final report can point at a number rather than a feeling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from playwright.sync_api import Browser, Error as PlaywrightError, Page

from .personas import Ghost

SLOW_LOAD_MS = 3000
MIN_TARGET_PX = 24
MIN_TEXT_PX = 12
MIN_CONTRAST = 4.5
MIN_CONTRAST_LARGE = 3.0

SCAN_JS = r"""
() => {
  const NATIVE = 'a[href],button,input:not([type=hidden]),select,textarea,summary,[contenteditable="true"]';
  const visible = el => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const clean = t => (t || '').replace(/\s+/g, ' ').trim();
  const textOf = el => clean(el.innerText || el.textContent);
  const focusable = el => (el.matches(NATIVE) && !el.disabled) || (el.hasAttribute('tabindex') && el.tabIndex >= 0);
  const nameOf = el => {
    const aria = clean(el.getAttribute('aria-label'));
    if (aria) return aria;
    const ids = el.getAttribute('aria-labelledby');
    if (ids) {
      const t = clean(ids.split(/\s+/).map(i => document.getElementById(i)).filter(Boolean).map(textOf).join(' '));
      if (t) return t;
    }
    if (el.matches('input,select,textarea')) {
      if (['submit', 'button', 'reset'].includes(el.type)) return clean(el.value);
      if (el.id) {
        const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
        if (l && textOf(l)) return textOf(l);
      }
      const wrap = el.closest('label');
      return wrap ? textOf(wrap) : '';
    }
    if (el.tagName === 'IMG') return clean(el.alt);
    const t = textOf(el);
    if (t) return t;
    const img = el.querySelector('img[alt]');
    return img ? clean(img.alt) : clean(el.getAttribute('title'));
  };
  const roleOf = el => {
    if (el.getAttribute('role')) return el.getAttribute('role');
    const tag = {A: 'link', BUTTON: 'button', SELECT: 'combobox', TEXTAREA: 'textbox', SUMMARY: 'button'}[el.tagName];
    if (tag) return tag;
    if (el.tagName === 'INPUT') {
      return {checkbox: 'checkbox', radio: 'radio', submit: 'button', button: 'button',
              number: 'spinbutton', range: 'slider'}[el.type] || 'textbox';
    }
    return 'clickable';
  };
  const looksClickable = el => {
    if (el.closest(NATIVE) || focusable(el)) return false;
    if (el.hasAttribute('onclick')) return true;
    const parent = el.parentElement;
    return getComputedStyle(el).cursor === 'pointer' && !(parent && getComputedStyle(parent).cursor === 'pointer');
  };
  const inSentence = el => {
    if (el.tagName !== 'A') return false;
    const block = el.closest('p,li,td,dd');
    return !!block && textOf(block).length > textOf(el).length + 20;
  };

  document.querySelectorAll('[data-ghost-id]').forEach(el => el.removeAttribute('data-ghost-id'));
  const controls = [];
  for (const el of document.querySelectorAll('body *')) {
    if (!visible(el)) continue;
    const isFocusable = focusable(el);
    if (!isFocusable && !looksClickable(el)) continue;
    const id = controls.length + 1;
    el.setAttribute('data-ghost-id', String(id));
    const r = el.getBoundingClientRect();
    const c = {id, role: roleOf(el), name: nameOf(el), focusable: isFocusable,
               width: Math.round(r.width), height: Math.round(r.height), in_sentence: inSentence(el),
               placeholder: el.getAttribute('placeholder') || ''};
    if (el.tagName === 'SELECT') {
      c.value = el.selectedOptions[0] ? clean(el.selectedOptions[0].text) : '';
      c.options = Array.from(el.options).slice(0, 8).map(o => clean(o.text));
    } else if (el.matches('input,textarea')) {
      c.value = el.value;
    }
    controls.push(c);
  }

  const parse = c => {
    const m = c.match(/rgba?\(([^)]+)\)/);
    if (!m) return [255, 255, 255, 1];
    const p = m[1].split(',').map(s => parseFloat(s));
    return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
  };
  const lum = ([r, g, b]) => {
    const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const background = el => {
    for (let n = el; n; n = n.parentElement) {
      const c = parse(getComputedStyle(n).backgroundColor);
      if (c[3] > 0.5) return c;
    }
    return [255, 255, 255, 1];
  };
  const texts = [];
  for (const el of document.querySelectorAll('body *')) {
    const own = clean(Array.from(el.childNodes).filter(n => n.nodeType === 3).map(n => n.textContent).join(' '));
    if (own.length < 3 || !visible(el)) continue;
    const s = getComputedStyle(el);
    const size = parseFloat(s.fontSize);
    const bold = parseInt(s.fontWeight, 10) >= 700;
    const fg = lum(parse(s.color)), bg = lum(background(el));
    const ratio = (Math.max(fg, bg) + 0.05) / (Math.min(fg, bg) + 0.05);
    const large = size >= 24 || (bold && size >= 18.66);
    texts.push({text: own.slice(0, 60), size, ratio: Math.round(ratio * 100) / 100, large});
  }

  const active = document.activeElement;
  const nav = performance.getEntriesByType('navigation')[0];
  return {
    url: location.href,
    title: document.title,
    text: clean(document.body ? document.body.innerText : '').slice(0, 700),
    controls,
    texts,
    focused: active && active.getAttribute('data-ghost-id') ? parseInt(active.getAttribute('data-ghost-id'), 10) : null,
    scroll_width: document.documentElement.scrollWidth,
    inner_width: window.innerWidth,
    screen_width: window.screen.width,
    load_ms: nav && nav.loadEventEnd > 0 ? Math.round(nav.loadEventEnd) : null,
  };
}
"""


@dataclass
class Evidence:
    id: str
    kind: str
    page: str
    detail: str

    def as_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "page": self.page, "detail": self.detail}


@dataclass
class EvidenceLog:
    lens: tuple[str, ...]
    items: list[Evidence] = field(default_factory=list)

    def add(self, kind: str, page: str, detail: str) -> Evidence | None:
        if kind not in self.lens or any(e.kind == kind and e.page == page for e in self.items):
            return None
        item = Evidence(f"E{len(self.items) + 1}", kind, page, detail)
        self.items.append(item)
        return item

    def get(self, evidence_id: str) -> Evidence | None:
        return next((e for e in self.items if e.id == evidence_id), None)


def measure(scan: dict, log: EvidenceLog) -> list[Evidence]:
    """Turn one page scan into evidence. Pure function of the scan, so it's unit-testable."""
    page = urlparse(scan["url"]).path or "/"
    found = []

    def add(kind, detail):
        item = log.add(kind, page, detail)
        if item:
            found.append(item)

    if scan.get("load_ms") and scan["load_ms"] > SLOW_LOAD_MS:
        add("slow_load", f"took {scan['load_ms'] / 1000:.1f}s to load (limit {SLOW_LOAD_MS / 1000:.0f}s)")
    # Phones shrink an over-wide page to fit (innerWidth grows), desktops scroll it; both count.
    screen = min(scan["inner_width"], scan.get("screen_width") or scan["inner_width"])
    width = max(scan["scroll_width"], scan["inner_width"])
    if width > screen + 1:
        add("horizontal_scroll", f"page is {width}px wide on a {screen}px screen")
    small = [c for c in scan["controls"]
             if (c["width"] < MIN_TARGET_PX or c["height"] < MIN_TARGET_PX) and not c["in_sentence"]]
    if small:
        names = ", ".join(f"'{c['name'] or c['role']}' ({c['width']}x{c['height']}px)" for c in small[:4])
        add("small_tap_target", f"{len(small)} target(s) under {MIN_TARGET_PX}px: {names}")
    unnamed = [c for c in scan["controls"] if c["focusable"] and not c["name"]]
    if unnamed:
        names = ", ".join(f"{c['role']}" + (f" (placeholder '{c['placeholder']}')" if c["placeholder"] else "")
                          for c in unnamed[:4])
        add("unnamed_control", f"{len(unnamed)} control(s) with no accessible name: {names}")
    unreachable = [c for c in scan["controls"] if not c["focusable"]]
    if unreachable:
        names = ", ".join(f"'{c['name']}'" for c in unreachable[:4])
        add("not_keyboard_reachable", f"{len(unreachable)} clickable element(s) Tab can't reach: {names}")
    tiny = [t for t in scan["texts"] if t["size"] < MIN_TEXT_PX]
    if tiny:
        add("small_text", f"{len(tiny)} text block(s) under {MIN_TEXT_PX}px, e.g. '{tiny[0]['text']}' at {tiny[0]['size']:g}px")
    faint = [t for t in scan["texts"] if t["ratio"] < (MIN_CONTRAST_LARGE if t["large"] else MIN_CONTRAST)]
    if faint:
        worst = min(faint, key=lambda t: t["ratio"])
        add("low_contrast", f"{len(faint)} text block(s) below {MIN_CONTRAST}:1 contrast, worst '{worst['text']}' at {worst['ratio']}:1")
    return found


def describe(scan: dict, ghost: Ghost, new_evidence: list[Evidence]) -> str:
    """What the ghost perceives, as compact text for the model."""
    lines = [f"Page: {scan['title']} ({urlparse(scan['url']).path or '/'})", f"Text on the page: {scan['text']}", "Controls:"]
    for c in scan["controls"]:
        if ghost.keyboard_only and not c["focusable"]:
            continue
        label = f'"{c["name"]}"' if c["name"] else "(no name announced)"
        line = f"[{c['id']}] {c['role']} {label}"
        if "value" in c and c["role"] != "combobox":
            line += f" value=\"{c['value']}\""
        if c.get("options"):
            line += f" selected=\"{c['value']}\" options={c['options']}"
        if not ghost.keyboard_only and c["placeholder"] and not c["name"]:
            line += f" (grey hint text: '{c['placeholder']}')"
        lines.append(line)
    if ghost.keyboard_only:
        focus = f"[{scan['focused']}]" if scan["focused"] else "the page itself (nothing focused)"
        lines.append(f"Focus is on: {focus}")
    if new_evidence:
        lines.append("You noticed: " + "; ".join(f"{e.id} {e.kind}: {e.detail}" for e in new_evidence))
    return "\n".join(lines)


class Body:
    def __init__(self, browser: Browser, ghost: Ghost):
        self.ghost = ghost
        self.log = EvidenceLog(ghost.lens)
        self.context = browser.new_context(
            viewport=ghost.viewport,
            device_scale_factor=ghost.device_scale_factor,
            is_mobile=ghost.is_mobile,
            has_touch=ghost.has_touch,
            locale="en-US",
        )
        self.context.set_default_timeout(30000)
        self.page: Page = self.context.new_page()
        if ghost.network:
            cdp = self.context.new_cdp_session(self.page)
            cdp.send("Network.enable")
            cdp.send("Network.emulateNetworkConditions", {
                "offline": False,
                "latency": ghost.network["latency_ms"],
                "downloadThroughput": ghost.network["download_kbps"] * 1024 / 8,
                "uploadThroughput": ghost.network["upload_kbps"] * 1024 / 8,
            })

    def goto(self, url: str) -> None:
        self.page.goto(url, wait_until="load")

    def observe(self) -> tuple[dict, list[Evidence], str]:
        scan = self.page.evaluate(SCAN_JS)
        new = measure(scan, self.log)
        return scan, new, describe(scan, self.ghost, new)

    def act(self, action: dict, scan: dict) -> str:
        kind = str(action.get("action", "")).lower()
        before = self.page.url
        try:
            result = self._do(kind, action, scan)
        except PlaywrightError as err:
            return f"that didn't work: {str(err).splitlines()[0][:160]}"
        try:
            self.page.wait_for_load_state("load", timeout=20000)
        except PlaywrightError:
            pass
        if self.page.url != before:
            result += f"; now on {urlparse(self.page.url).path or '/'}"
        return result

    def _do(self, kind: str, action: dict, scan: dict) -> str:
        keys = {"tab": "Tab", "shift_tab": "Shift+Tab", "enter": "Enter", "space": " "}
        if self.ghost.keyboard_only:
            if kind in keys:
                self.page.keyboard.press(keys[kind] if kind != "space" else "Space")
                self.page.wait_for_timeout(500 if kind in ("enter", "space") else 150)
                return f"pressed {keys[kind].strip() or 'Space'}"
            if kind == "type":
                self.page.keyboard.type(str(action.get("text", "")))
                return f"typed '{action.get('text', '')}'"
            return f"'{kind}' isn't something you can do with a keyboard; use tab, shift_tab, enter, space or type"
        if kind == "scroll":
            self.page.evaluate("window.scrollBy(0, Math.round(window.innerHeight * 0.8))")
            return "scrolled down"
        if kind == "back":
            self.page.go_back()
            return "went back"
        target = action.get("target")
        control = next((c for c in scan["controls"] if c["id"] == target), None)
        if control is None:
            return f"there is no control [{target}] on this page"
        el = self.page.locator(f'[data-ghost-id="{target}"]')
        label = control["name"] or control["role"]
        if kind == "click":
            el.click(timeout=5000)
            self.page.wait_for_timeout(300)
            return f"tapped [{target}] '{label}'"
        if kind == "fill":
            el.fill(str(action.get("text", "")), timeout=5000)
            return f"typed '{action.get('text', '')}' into [{target}] '{label}'"
        if kind == "select":
            choice = str(action.get("text", ""))
            try:
                el.select_option(label=choice, timeout=5000)
            except PlaywrightError:
                el.select_option(choice, timeout=5000)
            return f"chose '{choice}' in [{target}] '{label}'"
        return f"'{kind}' isn't an action; use click, fill, select, scroll or back"

    def screenshot(self, path: str) -> None:
        self.page.screenshot(path=path)

    def close(self) -> None:
        self.context.close()
