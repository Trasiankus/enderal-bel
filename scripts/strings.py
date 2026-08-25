# -*- coding: utf-8 -*-
"""Reader/writer for Skyrim SE string tables, as Enderal ships them.

Layout of all three types:

    u32 count
    u32 dataSize
    count x { u32 id, u32 offset }        offset is relative to the data section
    data section                          starts at 8 + count*8

Record payload differs by extension:

    .strings                 null-terminated bytes
    .dlstrings / .ilstrings  u32 length (INCLUDING the trailing \\x00) then the bytes

That second line is a quirk of this build: vanilla SSE null-terminates .dlstrings, this
one length-prefixes them, so the mode is auto-detected per file rather than assumed.
Payloads are UTF-8.
"""
import struct

FILES = [
    "enderal - forgotten stories_english.strings",
    "enderal - forgotten stories_english.dlstrings",
    "enderal - forgotten stories_english.ilstrings",
    "skyrim_english.strings",
    "skyrim_english.dlstrings",
    "skyrim_english.ilstrings",
]


def _walk(b, n, mode):
    data_off = 8 + n * 8
    entries = []
    covered = bytearray(len(b))
    for i in range(n):
        sid, off = struct.unpack_from("<II", b, 8 + i * 8)
        pos = data_off + off
        if pos > len(b):
            return None, 0.0
        if mode == "null":
            end = b.find(b"\x00", pos)
            if end < 0 or end >= len(b):
                return None, 0.0
            raw, endpos = b[pos:end], end + 1
        else:
            if pos + 4 > len(b):
                return None, 0.0
            ln = struct.unpack_from("<I", b, pos)[0]
            if pos + 4 + ln > len(b):
                return None, 0.0
            raw, endpos = b[pos + 4:pos + 4 + ln], pos + 4 + ln
        entries.append((sid, raw.rstrip(b"\x00").decode("utf-8", "replace"), raw))
        for j in range(pos, endpos):
            covered[j] = 1
    return entries, sum(covered[data_off:]) / max(1, len(b) - data_off)


def parse_file(path, ext):
    """-> (raw bytes, [(id, text, raw)], mode)"""
    b = open(path, "rb").read()
    n = struct.unpack_from("<I", b, 0)[0]
    if ext == ".strings":
        entries, _ = _walk(b, n, "null")
        if entries is None:
            raise ValueError("%s: null-terminated walk failed" % path)
        return b, entries, "null"
    cand = []
    for mode in ("len", "null"):
        e, c = _walk(b, n, mode)
        if e is not None:
            cand.append((mode, e, c))
    if not cand:
        raise ValueError("%s: no valid interpretation" % path)
    best = max(c[2] for c in cand)
    win = [c for c in cand if abs(c[2] - best) < 1e-9]
    win = [c for c in win if c[0] == "len"] or win
    mode, entries, _ = win[0]
    return b, entries, mode


def build_file(entries, mode, dedupe=False):
    """entries = [(id, text, raw_or_None)] -> bytes"""
    table, payloads, cache, pos = [], [], {}, 0
    for sid, text, raw in entries:
        if raw is not None:
            enc = raw + b"\x00" if mode == "null" else raw
        else:
            enc = text.encode("utf-8") + b"\x00"
        off = cache.get(enc) if dedupe else None
        if off is None:
            off = pos
            if dedupe:
                cache[enc] = off
            rec = struct.pack("<I", len(enc)) + enc if mode == "len" else enc
            payloads.append(rec)
            pos += len(rec)
        table.append(struct.pack("<II", sid, off))
    return struct.pack("<II", len(entries), pos) + b"".join(table) + b"".join(payloads)
