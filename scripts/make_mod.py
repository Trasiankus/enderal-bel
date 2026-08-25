# -*- coding: utf-8 -*-
"""Build the installable mod from the JSON files in this repository.

Reads localization.json + books.json + interface.json, writes:

    mod/Strings/*_english.*   and  *_russian.*   (identical Belarusian content)
    mod/Interface/translate_russian.txt

Both language variants are emitted because the engine loads
`Strings\\<name>_<sLanguage>.*` and nothing else: an English base install reads
`_english`, a Russian one reads `_russian`. The tables are id-identical across language
variants of the same plugin generation, so one set of translations serves both.

The reference tables come from your game install (for ids, order and record format);
only the text is replaced.

Usage
  python scripts/make_mod.py --check      verify inputs, translate nothing
  python scripts/make_mod.py              build into mod/
  python scripts/make_mod.py --game "D:\\path\\to\\Enderal Special Edition"
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from strings import FILES, parse_file, build_file  # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NLRUN = re.compile(r"[\r\n]+")
DEFAULT_GAME = r"C:\Games\Steam\steamapps\common\Enderal Special Edition"


def arg(flag, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


GAME = arg("--game", os.environ.get("ENDERAL_DIR", DEFAULT_GAME))
CHECK = "--check" in sys.argv
SRC = os.path.join(GAME, "Data", "Strings")


def load(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return json.load(f)


def book_text(row):
    """Rejoin a book's paragraphs with its own recorded separators.

    If someone adds paragraphs in a PR there will be fewer separators than gaps; pad with
    the book's most common separator rather than silently running paragraphs together.
    """
    bel, sep = row.get("bel") or [], row.get("sep") or []
    if not bel:
        return ""
    fill = max(set(sep), key=sep.count) if sep else "\r\n\r\n"
    out = []
    for i, para in enumerate(bel):
        out.append(para)
        if i < len(bel) - 1:
            out.append(sep[i] if i < len(sep) else fill)
    return "".join(out)


def main():
    loc, books, ui = load("localization.json"), load("books.json"), load("interface.json")
    mp = load("map.json")

    text = {k: (v.get("bel") or "") for k, v in loc.items()}
    for k, row in books.items():
        text[k] = book_text(row)

    if not os.path.isdir(SRC):
        print("game Strings folder not found: %s\nPass --game <path>." % SRC)
        sys.exit(1)

    out_s = os.path.join(ROOT, "mod", "Strings")
    os.makedirs(out_s, exist_ok=True)
    total = done = 0
    for fname in FILES:
        path = os.path.join(SRC, fname)
        if not os.path.exists(path):
            path = os.path.join(SRC, fname.replace("_english", "_russian"))
        b, entries, mode = parse_file(path, os.path.splitext(fname)[1])
        m = mp[fname]
        new = []
        for sid, txt, raw in entries:
            tr = text.get(m[str(sid)])
            if tr:
                new.append((sid, tr, None))
                done += 1
            else:
                new.append((sid, txt, raw))
            total += 1
        if CHECK:
            continue
        blob = build_file(new, mode)
        if blob != b and build_file(new, mode, dedupe=True) == b:
            blob = build_file(new, mode, dedupe=True)
        for lang in ("english", "russian"):
            open(os.path.join(out_s, fname.replace("_english", "_" + lang)), "wb").write(blob)

    if not CHECK:
        out_i = os.path.join(ROOT, "mod", "Interface")
        os.makedirs(out_i, exist_ok=True)
        lines = ["%s\t%s" % (k, v.get("bel") or v.get("ru") or "") for k, v in ui.items()]
        blob = ("\r\n".join(lines) + "\r\n").encode("utf-16-le")
        for lang in ("english", "russian"):
            with open(os.path.join(out_i, "translate_%s.txt" % lang), "wb") as f:
                f.write(b"\xff\xfe")          # UTF-16LE BOM; the game rejects UTF-8 here
                f.write(blob)

    print("strings: %d/%d translated" % (done, total))
    print("interface: %d keys" % len(ui))
    print("checked inputs only." if CHECK else "written to mod/ — copy its contents into Data/")


if __name__ == "__main__":
    main()
