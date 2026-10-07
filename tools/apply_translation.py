#!/usr/bin/env python3
"""Apply a translation table to a cooked Damage Meter asset.

This is the reference implementation of the byte-level edit the localisation
needs. It works on a cooked asset (the `.uasset` you get from `retoc unpack`, or
your own cooked output) and rewrites every matching FString body.

Framing (verified against the shipped container):

    [ .. ][ int32 length+1 ][ body ][ 0x00 ]

`length+1` is the byte count the engine consumes, including the NUL, so a
replacement of a different byte length is fine as long as the dword is rewritten
too. That is exactly what this script does.

Safety
------
  * A replacement is only written when the dword before the body really equals
    `len(body) + 1` and the byte after the body is `0x00`.
  * Replacements are applied back-to-front so earlier offsets stay valid.
  * Nothing is written unless `--apply` is passed; the default is a dry run that
    reports exactly what would change.

Do NOT translate the internal setting identifiers (`position_x`, `show_dps`,
`dps_mode`, ...). They are the keys the widget uses to read and write settings;
translating them silently breaks the settings page. The shipped translation
tables list only display text for this reason.

Usage
-----
    python apply_translation.py ModInfo.uasset --table translations/modinfo.zh-CN.tsv
    python apply_translation.py ModInfo.uasset --table ... --apply
"""
import argparse
import os
import re
import struct
import sys

FRAMED = re.compile(rb"[\x20-\x7e\xc2-\xf4][\x20-\x7e\x80-\xbf]{1,4096}")


def load_table(path):
    """TSV with `English<TAB>Chinese` and an optional third notes column."""
    pairs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n").rstrip("\r")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            en, zh = parts[0].strip(), parts[1].strip()
            if not en or not zh or en == "English (current)":
                continue
            if en == zh:
                continue
            pairs.append((en, zh))
    return pairs


def patch(data, pairs, apply_):
    report = []
    for en, zh in pairs:
        raw = en.encode("utf-8")
        repl = zh.encode("utf-8") + b"\x00"
        hits = []
        for m in re.finditer(re.escape(raw), data):
            off = m.start()
            if off < 4:
                continue
            if struct.unpack_from("<i", data, off - 4)[0] != len(raw) + 1:
                continue
            if data[off + len(raw)] != 0x00:
                continue
            hits.append(off)
        if not hits:
            report.append((en, "not found", 0, 0))
            continue
        for off in sorted(hits, reverse=True):
            old_len = len(raw) + 1
            struct.pack_into("<i", data, off - 4, len(repl))
            data[off:off + old_len] = repl
            report.append((en, "ok", old_len, len(repl)))
    return report


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("asset", help="cooked .uasset to patch")
    ap.add_argument("--table", required=True,
                    help="TSV with English<TAB>Chinese")
    ap.add_argument("--out", help="write here instead of editing in place")
    ap.add_argument("--apply", action="store_true",
                    help="actually write (default is a dry run)")
    args = ap.parse_args()

    pairs = load_table(args.table)
    if not pairs:
        raise SystemExit(f"no usable rows in {args.table}")

    data = bytearray(open(args.asset, "rb").read())
    print(f"{os.path.basename(args.asset)}  {len(data)} bytes  "
          f"{len(pairs)} table rows")
    report = patch(data, pairs, args.apply)

    problems = 0
    for en, status, old, new in report:
        if status != "ok":
            problems += 1
            print(f"  [{'MISS' if status == 'not found' else status:>8}] {en[:60]!r}")
        elif old != new:
            print(f"  [     ok] {old:>4} -> {new:>4} bytes  {en[:50]!r}")
        else:
            print(f"  [     ok] same size       {en[:50]!r}")

    print(f"\n{len(report) - problems}/{len(report)} substitutions matched")
    if not args.apply:
        print("dry run — re-run with --apply to write")
        return 0 if problems == 0 else 1

    out = args.out or args.asset
    open(out, "wb").write(bytes(data))
    print(f"wrote {out}")
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
