#!/usr/bin/env python3
"""Locate every FText/FString value inside a cooked Damage Meter asset.

Why this exists
---------------
Blueprint data assets store their editable text (ModName, Description, setting
Labels and Descriptions) as UE FString bodies inside the cooked package. They are
not kept in any external localisation file, so editing the package bytes is the
only way to translate them. This script finds every such string and prints its
byte offset plus the framing any patcher needs.

Framing it relies on (verified against the shipped Damage Meter container):

    [ .. ][ int32 length+1 ][ body bytes ][ 0x00 ]

The `length+1` dword sits exactly four bytes before the body and counts the body
bytes plus its NUL terminator. A string is reported only when that dword really
equals `len(body) + 1`, which filters out the property names, import paths and
other plain ASCII that also live in a cooked package.

Usage
-----
    python get_settings_ftexts.py ModInfo.uasset
    python get_settings_ftexts.py ModInfo.uasset --tsv out.tsv
    python get_settings_ftexts.py WBP_DamageProbe.uasset --min-length 4

The input is a cooked asset as packed in the mod: either the `.uasset` you get
from `retoc unpack` on the shipped container, or the asset inside your own
cooked output.
"""
import argparse
import struct
import sys

ASCII_PRINTABLE = set(range(0x20, 0x7F))
UTF8_LEAD = set(range(0xC2, 0xF5))


def utf8_sequence_length(lead):
    if lead < 0xE0:
        return 2
    if lead < 0xF0:
        return 3
    return 4


def framed_strings(data, min_length):
    """Yield (offset, declared_length, text) for every framed FString body."""
    n = len(data)
    i = 0
    while i < n:
        b = data[i]
        if b not in ASCII_PRINTABLE and b not in UTF8_LEAD:
            i += 1
            continue

        start = i
        while i < n:
            b = data[i]
            if b in ASCII_PRINTABLE:
                i += 1
                continue
            if b in UTF8_LEAD:
                size = utf8_sequence_length(b)
                if i + size <= n and all(
                        0x80 <= data[i + k] <= 0xBF for k in range(1, size)):
                    i += size
                    continue
                # malformed: drop the lead byte so we always make progress
                i += 1
                break
            break

        body = data[start:i]
        if len(body) >= min_length and start >= 4 and i < n and data[i] == 0x00:
            declared = struct.unpack_from("<i", data, start - 4)[0]
            if declared == len(body) + 1:
                try:
                    text = body.decode("utf-8")
                except UnicodeDecodeError:
                    continue
                if text.strip():
                    yield start, declared, text


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("asset", help="cooked .uasset to inspect")
    ap.add_argument("--min-length", type=int, default=3,
                    help="shortest body to report (default 3)")
    ap.add_argument("--tsv", help="also write offset/length/text to this TSV")
    args = ap.parse_args()

    data = open(args.asset, "rb").read()
    rows = list(framed_strings(data, args.min_length))
    print(f"{args.asset}  ({len(data)} bytes)  {len(rows)} framed strings")
    print()
    print(f"{'offset':>8}  {'len+1':>6}  text")
    print("-" * 78)
    for off, declared, text in rows:
        shown = text if len(text) <= 60 else text[:57] + "..."
        print(f"{off:>8}  {declared:>6}  {shown}")

    if args.tsv:
        with open(args.tsv, "w", encoding="utf-8", newline="\n") as f:
            f.write("offset\tlength_with_nul\ttext\n")
            for off, declared, text in rows:
                f.write(f"{off}\t{declared}\t{text}\n")
        print(f"\nwrote {args.tsv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
