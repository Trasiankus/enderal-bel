# -*- coding: utf-8 -*-
"""Validate the translation files before you open a pull request.

Checks, in order of how often they actually catch something:

  1. Russian letters и/щ/ъ  — Belarusian has none; use і, шч, '
  2. тарашкевіца soft signs — this translation is Наркамаўка (ёсць, not ёсьць)
  3. paragraph counts       — noted when bel and en differ (allowed, but worth a look)
  4. placeholders           — <mag>, <dur>, %s, [pagebreak] etc. must survive verbatim
  5. empty translations     — a key with an empty `bel` falls back to English in game

Usage: python scripts/check.py
Exit code is non-zero if anything failed, so CI can use it.
"""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FORBIDDEN = set("ищъ")
TARASH = re.compile(r"сьць|ньн|цьц|льл|\bсьв|\bсьм|\bзьм|\bзьн", re.I)
# engine substitutions and markup: must appear unchanged in the translation
OPAQUE = re.compile(
    r"</?(?:font|p|b|i|u|br|img)\b[^<>]*>|<(?:mag|dur)>|<\d+>|"
    r"<(?:Alias|Global)[^<>]*>|%(?:%|[-+#0]*\d*(?:\.\d+)?[diouxXeEfFgGaAcsp])",
    re.I)


def load(n):
    with open(os.path.join(ROOT, n), encoding="utf-8") as f:
        return json.load(f)


def tokens(s):
    # '%%' and '%' both render as one literal percent sign. English writes '%%', the
    # Russian localization writes '%', and this translation follows Russian -- mixing the
    # two in one string is what crashed the talent descriptions, so normalise before
    # comparing rather than reporting 126 false positives.
    return sorted(OPAQUE.findall((s or "").replace("%%", "%")))


problems = []


def add(kind, key, detail):
    problems.append((kind, key, detail))


loc, books, ui = load("localization.json"), load("books.json"), load("interface.json")

for key, row in loc.items():
    bel, en = row.get("bel") or "", row.get("en") or ""
    if not bel:
        continue
    low = bel.lower()
    if any(c in FORBIDDEN for c in low):
        add("russian-letter", key, repr(bel[:70]))
    if TARASH.search(low):
        add("tarashkievica", key, repr(bel[:70]))
    if tokens(bel) != tokens(en):
        add("placeholder", key, "en=%s bel=%s" % (tokens(en), tokens(bel)))

for key, row in books.items():
    bel, en = row.get("bel") or [], row.get("en") or []
    if not bel:
        continue
    # bel may legitimately have a different paragraph count from en (the Russian
    # localization does too); only the token check needs a paired english paragraph.
    if len(bel) != len(en):
        add("paragraph-count-note", key, "%d bel vs %d en (ok if intentional)"
            % (len(bel), len(en)))
    for i, (b, e) in enumerate(zip(bel, en)):
        low = b.lower()
        if any(c in FORBIDDEN for c in low):
            add("russian-letter", "%s#%d" % (key, i), repr(b[:70]))
        if TARASH.search(low):
            add("tarashkievica", "%s#%d" % (key, i), repr(b[:70]))
        if tokens(b) != tokens(e):
            add("placeholder", "%s#%d" % (key, i), "en=%s bel=%s" % (tokens(e), tokens(b)))

for key, row in ui.items():
    bel = row.get("bel") or ""
    if not bel:
        add("empty-ui", key, "")
    elif any(c in FORBIDDEN for c in bel.lower()):
        add("russian-letter", key, repr(bel[:70]))

by_kind = {}
for kind, key, detail in problems:
    by_kind.setdefault(kind, []).append((key, detail))

print("localization=%d  books=%d  interface=%d" % (len(loc), len(books), len(ui)))
if not problems:
    print("OK — no problems found.")
    sys.exit(0)
for kind, rows in sorted(by_kind.items(), key=lambda x: -len(x[1])):
    print("\n%s: %d" % (kind, len(rows)))
    for key, detail in rows[:10]:
        print("   %-34s %s" % (key, detail))
    if len(rows) > 10:
        print("   ... and %d more" % (len(rows) - 10))
sys.exit(1)
