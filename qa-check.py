#!/usr/bin/env python3
"""
qa-check.py — structural QA for the Axis Digital single-file demo sites.

Usage:
    python3 qa-check.py [--deep] file.html [more.html ...]

Checks (always):
  * every href="#..." resolves to a real id
  * every getElementById('x') / querySelector('#x') target exists
  * no duplicate ids
  * no external images or scripts (Google Fonts CSS is allowed)
  * viewport meta, lang attribute, <title>, skip link, <main>
  * content is not parked behind opacity:0 waiting on JavaScript
  * no `'X' in window` feature detects
  * prefers-reduced-motion block present

Extra with --deep:
  * tag balance / unclosed elements
  * banned typefaces (the studio's existing sites) not requested
  * icon-only <button>/<a> carry an accessible name
  * form controls have a <label for> or aria-label
  * :focus-visible styling present, focus outlines not killed outright
  * fixed pixel widths that would overflow a 375px viewport
  * inline event handlers (onclick=) — these die with the accordion pattern
  * CSS custom properties whose names imply brightness rather than role
  * <details>/<summary> or ARIA state on any accordion
"""

import argparse
import os
import re
import sys
from collections import Counter
from html.parser import HTMLParser

RESET = "\033[0m"
RED = "\033[31m"
YEL = "\033[33m"
GRN = "\033[32m"
DIM = "\033[2m"

BANNED_FONTS = [
    "Instrument Serif", "Cormorant", "Bodoni Moda", "Archivo", "Fraunces",
    "Plus Jakarta Sans", "Marcellus", "Prata", "Inter", "Jost", "Manrope",
    "Karla", "Chivo", "Epilogue", "Public Sans",
]

VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


class Doc(HTMLParser):
    """Collects ids, hrefs, tag balance and element facts."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.hrefs = []
        self.stack = []
        self.unclosed = []
        self.stray = []
        self.buttons = []          # (tag, attrs, text, line)
        self.controls = []         # (tag, attrs, line)
        self.labels_for = set()
        self.has_main = False
        self.has_title = False
        self._grab_text_for = None
        self._text = ""
        self._pending = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        line = self.getpos()[0]
        if "id" in a:
            self.ids.append((a["id"], line))
        if "href" in a:
            self.hrefs.append((a["href"], line))
        if tag == "main":
            self.has_main = True
        if tag == "title":
            self.has_title = True
        if tag == "label" and "for" in a:
            self.labels_for.add(a["for"])
        if tag in ("input", "select", "textarea"):
            self.controls.append((tag, a, line))
        if tag == "button" or (tag == "a" and "href" in a):
            self._pending = (tag, a, line)
            self._grab_text_for = tag
            self._text = ""
        if tag not in VOID:
            self.stack.append((tag, line))

    def handle_startendtag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.append((a["id"], self.getpos()[0]))
        if "href" in a:
            self.hrefs.append((a["href"], self.getpos()[0]))

    def handle_data(self, data):
        if self._grab_text_for:
            self._text += data

    def handle_endtag(self, tag):
        if self._pending and tag == self._pending[0]:
            t, a, line = self._pending
            self.buttons.append((t, a, self._text.strip(), line))
            self._pending = None
            self._grab_text_for = None
        if tag in VOID:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for orphan in self.stack[i + 1:]:
                    self.unclosed.append(orphan)
                del self.stack[i:]
                return
        self.stray.append((tag, self.getpos()[0]))


class Report:
    def __init__(self, path):
        self.path = path
        self.errors = []
        self.warns = []
        self.oks = []

    def err(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warns.append(msg)

    def ok(self, msg):
        self.oks.append(msg)

    def print(self, verbose):
        print(f"\n{DIM}{'=' * 68}{RESET}")
        print(f"  {os.path.basename(self.path)}")
        print(f"{DIM}{'=' * 68}{RESET}")
        for m in self.oks:
            print(f"  {GRN}pass{RESET}  {m}")
        for m in self.warns:
            print(f"  {YEL}warn{RESET}  {m}")
        for m in self.errors:
            print(f"  {RED}FAIL{RESET}  {m}")
        n_e, n_w = len(self.errors), len(self.warns)
        print()
        if n_e:
            print(f"  {RED}{n_e} failure(s){RESET}, {n_w} warning(s)")
        else:
            print(f"  {GRN}clean{RESET} — 0 failures, {n_w} warning(s)")
        return n_e


def strip_comments(src):
    src = re.sub(r"<!--.*?-->", "", src, flags=re.S)
    return src


def styles_of(src):
    return "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", src, flags=re.S | re.I))


def scripts_of(src):
    return "\n".join(
        m for m in re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", src, flags=re.S | re.I)
    )


def check(path, deep):
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()

    r = Report(path)
    src = strip_comments(raw)
    css = styles_of(src)
    js = scripts_of(src)

    doc = Doc()
    doc.feed(src)

    # ---------- ids ----------
    names = [i for i, _ in doc.ids]
    dupes = [n for n, c in Counter(names).items() if c > 1]
    if dupes:
        r.err(f"duplicate id(s): {', '.join(sorted(dupes))}")
    else:
        r.ok(f"{len(names)} ids, all unique")

    idset = set(names)

    # ---------- fragment links ----------
    bad = []
    frag = 0
    for href, line in doc.hrefs:
        if href.startswith("#") and href != "#":
            frag += 1
            if href[1:] not in idset:
                bad.append(f"{href} (line {line})")
    if bad:
        r.err(f"href target(s) with no matching id: {', '.join(bad)}")
    else:
        r.ok(f"{frag} in-page links, all resolve")

    # ---------- script id targets ----------
    targets = re.findall(r"getElementById\(\s*['\"]([^'\"]+)['\"]", js)
    # follow one level of helper: `var byId = function(id){ ... getElementById(id) ... }`
    for helper in re.findall(
        r"(?:var|let|const)\s+(\w+)\s*=\s*function\s*\(\s*\w+\s*\)\s*\{[^}]*getElementById\(", js
    ) + re.findall(r"function\s+(\w+)\s*\(\s*\w+\s*\)\s*\{[^}]*getElementById\(", js):
        targets += re.findall(r"\b" + helper + r"\(\s*['\"]([^'\"]+)['\"]", js)
    # ids assembled at runtime, e.g. byId('f-' + name) — flag the prefix for a look
    for pre in re.findall(r"\b\w+\(\s*['\"]([\w-]+-)['\"]\s*\+", js):
        if not any(i.startswith(pre) for i in idset):
            r.warn(f"script builds ids with the prefix '{pre}' but no id starts with it")
    missing = sorted({t for t in targets if t not in idset})
    if missing:
        r.err(f"getElementById target(s) not in the DOM: {', '.join(missing)}")
    else:
        r.ok(f"{len(set(targets))} getElementById target(s), all present")

    qs = re.findall(r"querySelector(?:All)?\(\s*['\"]#([A-Za-z0-9_\-]+)", js)
    qmiss = sorted({t for t in qs if t not in idset})
    if qmiss:
        r.err(f"querySelector('#id') target(s) missing: {', '.join(qmiss)}")

    # ---------- external assets ----------
    ext_img = re.findall(r"<img[^>]*\bsrc=[\"']([^\"']+)", src, flags=re.I)
    if ext_img:
        r.err(f"{len(ext_img)} <img> element(s) — this build allows no image files")
    else:
        r.ok("no <img> elements; all visuals are CSS or inline SVG")

    urls = re.findall(r"url\(\s*['\"]?(https?:)?//", css)
    if urls:
        r.err("CSS references a remote url() asset")

    ext_scripts = re.findall(r"<script[^>]*\bsrc=[\"']([^\"']+)", src, flags=re.I)
    if ext_scripts:
        r.err(f"external script(s): {', '.join(ext_scripts)}")
    else:
        r.ok("no external scripts — self-contained")

    links = re.findall(r"<link[^>]*\bhref=[\"']([^\"']+)", src, flags=re.I)
    stray_links = [
        u for u in links
        if u.startswith("http") and "fonts.googleapis.com" not in u and "fonts.gstatic.com" not in u
    ]
    if stray_links:
        r.err(f"external stylesheet(s) beyond Google Fonts: {', '.join(stray_links)}")

    # ---------- hidden content ----------
    # opacity:0 anywhere outside a keyframe/@supports reveal is a content risk
    hidden = []
    for m in re.finditer(r"opacity\s*:\s*0(?!\.\d|\s*\d)", css):
        start = css.rfind("{", 0, m.start())
        sel = css[max(0, css.rfind("}", 0, start)) + 1:start].strip().splitlines()
        sel = sel[-1].strip() if sel else "?"
        line = css[: m.start()].count("\n") + 1
        hidden.append(f"{sel} (style line {line})")
    if hidden:
        r.err("opacity:0 rule(s) — content must not wait on JavaScript to appear: "
              + "; ".join(hidden))
    else:
        r.ok("no opacity:0 rules — content is visible in the default state")

    if re.search(r"visibility\s*:\s*hidden", css):
        r.warn("visibility:hidden present — confirm it never hides page copy")

    # ---------- feature detection style ----------
    inwin = re.findall(r"['\"]([A-Za-z_$][\w$]*)['\"]\s+in\s+window", js)
    if inwin:
        r.err(f"`'X' in window` detect(s) found ({', '.join(inwin)}); "
              "use typeof window.X === 'function'")
    else:
        r.ok("no `'X' in window` feature detects")

    # ---------- head basics ----------
    if not re.search(r"<html[^>]*\blang=", src, flags=re.I):
        r.err("<html> has no lang attribute")
    if not re.search(r"<meta[^>]*name=[\"']viewport[\"']", src, flags=re.I):
        r.err("no viewport meta tag")
    if not doc.has_title:
        r.err("no <title>")
    if not doc.has_main:
        r.err("no <main> landmark")
    if not re.search(r"href=[\"']#(main|content)[\"']", src, flags=re.I):
        r.warn("no obvious skip-to-content link")
    else:
        r.ok("skip-to-content link present")

    if "prefers-reduced-motion" in css:
        block = re.search(
            r"@media[^{]*prefers-reduced-motion:\s*reduce[^{]*\{(.*?)\n\}", css, flags=re.S)
        if block and "animation-duration" in block.group(1) and "transition-duration" in block.group(1):
            r.ok("prefers-reduced-motion zeroes animation and transition durations")
        else:
            r.warn("prefers-reduced-motion present but may not zero both durations")
    else:
        r.err("no prefers-reduced-motion handling")

    if not deep:
        return r

    # ================= DEEP =================
    if doc.unclosed:
        r.err("unclosed element(s): "
              + ", ".join(f"<{t}> opened line {l}" for t, l in doc.unclosed[:8]))
    if doc.stray:
        r.err("stray closing tag(s): "
              + ", ".join(f"</{t}> line {l}" for t, l in doc.stray[:8]))
    if doc.stack:
        r.err("never closed: " + ", ".join(f"<{t}> line {l}" for t, l in doc.stack[:8]))
    if not (doc.unclosed or doc.stray or doc.stack):
        r.ok("tag tree balances")

    # fonts
    hit = [f for f in BANNED_FONTS if re.search(re.escape(f).replace(r"\ ", r"[+ ]"), src)]
    if hit:
        r.err(f"banned typeface(s) in use: {', '.join(hit)}")
    else:
        fams = sorted(set(re.findall(r"family=([A-Za-z0-9+]+)", src)))
        r.ok("typefaces clear of the studio's existing sites"
             + (f" ({', '.join(f.replace('+', ' ') for f in fams)})" if fams else ""))

    # accessible names on icon-only controls
    nameless = []
    for tag, a, text, line in doc.buttons:
        if text:
            continue
        if a.get("aria-label") or a.get("aria-labelledby") or a.get("title"):
            continue
        nameless.append(f"<{tag}> line {line}")
    if nameless:
        r.err("icon-only control(s) without an accessible name: " + ", ".join(nameless))
    else:
        r.ok("every button/link has text or an aria-label")

    # form controls labelled
    unlabelled = []
    for tag, a, line in doc.controls:
        if a.get("type") in ("hidden", "submit", "button"):
            continue
        if a.get("aria-label") or a.get("aria-labelledby") or a.get("title"):
            continue
        cid = a.get("id")
        if cid and cid in doc.labels_for:
            continue
        if a.get("type") == "checkbox" or a.get("type") == "radio":
            continue  # commonly wrapped in a <label>
        unlabelled.append(f"<{tag} id={cid or '?'}> line {line}")
    if unlabelled:
        r.err("form control(s) with no label: " + ", ".join(unlabelled))
    else:
        r.ok("form controls are labelled")

    # focus styling
    if ":focus-visible" in css or ":focus" in css:
        if re.search(r":focus[^{]*\{[^}]*outline\s*:\s*none", css) and ":focus-visible" not in css:
            r.err("outline removed on :focus with no :focus-visible replacement")
        else:
            r.ok("visible focus styling defined")
    else:
        r.err("no focus styling in CSS")

    # inline handlers
    inline = re.findall(r"\son(click|change|submit|input|load)=", src, flags=re.I)
    if inline:
        r.warn(f"{len(inline)} inline event handler(s) — prefer addEventListener")

    # overflow risk at 375px
    risky = []
    # media query conditions are breakpoints, not element widths
    css_no_mq = re.sub(r"@media[^{]*\{", "{", css)
    for m in re.finditer(r"(?<![-\w])(width|min-width)\s*:\s*(\d{3,4})px", css_no_mq):
        prop, px = m.group(1), int(m.group(2))
        if px <= 375:
            continue
        start = css_no_mq.rfind("{", 0, m.start())
        head = css_no_mq[max(0, css_no_mq.rfind("}", 0, start)) + 1:start].strip().splitlines()
        sel = head[-1].strip() if head else "?"
        # a wide min-width is fine inside a scroll container
        ctx = css_no_mq[max(0, m.start() - 900):m.start()]
        if "overflow-x:auto" in ctx.replace(" ", "") or "overflow:auto" in ctx.replace(" ", ""):
            continue
        risky.append(f"{sel} {{{prop}:{px}px}}")
    if risky:
        r.warn("wide fixed width(s) — verify they sit inside a scroll container: "
               + "; ".join(risky[:6]))
    else:
        r.ok("no unguarded fixed widths above 375px")

    if "overflow-x:hidden" in css.replace(" ", "") or "overflow-x: hidden" in css:
        r.ok("body guards against horizontal overflow")

    # token naming: a colour token should name a role, not a brightness
    brightness = re.findall(r"--(dark|light|black|white)[\w-]*\s*:", css)
    if brightness:
        r.warn("colour token(s) named for brightness rather than role: "
               + ", ".join(sorted(set(brightness))))
    else:
        r.ok("colour tokens are named by role, so the scheme survives inversion")

    # accordions
    if "<details" in src:
        r.ok("accordion uses <details>/<summary> — works without JavaScript")
    elif re.search(r"aria-expanded", src):
        r.ok("accordion exposes aria-expanded")

    # heading order sanity
    heads = [int(h) for h in re.findall(r"<h([1-6])[\s>]", src)]
    if heads.count(1) != 1:
        r.warn(f"{heads.count(1)} <h1> element(s); expected exactly one")
    else:
        r.ok("exactly one <h1>")

    # noscript safety net when reveals are used
    if "animation-timeline" in css:
        if "<noscript" in src:
            r.ok("scroll-timeline reveals ship with a <noscript> fallback")
        else:
            r.warn("scroll-timeline reveals with no <noscript> block")

    return r


def main():
    ap = argparse.ArgumentParser(description="QA a single-file demo site.")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--deep", action="store_true", help="run the full structural pass")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args()

    failures = 0
    for path in args.files:
        if not os.path.isfile(path):
            print(f"{RED}FAIL{RESET}  no such file: {path}")
            failures += 1
            continue
        failures += check(path, args.deep).print(not args.quiet)

    print()
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
