#!/usr/bin/env python3
"""Merge CJK glyphs into a Minecraft-styled CFF/OTF font used by Damage Meter.

The mod ships three CFF faces derived from the Minecraft fonts. They carry the
Minecraft letterforms but no CJK coverage at all, so Chinese text renders as
missing-glyph boxes. This script appends a subset of a CJK face (Noto Sans SC by
default) to the same CFF table, keeping:

  * every original glyph outline,
  * the original name table (family / subfamily / full name / PostScript name),
    so the widget's TypefaceFontName lookup keeps resolving,
  * the original unitsPerEm (1000 in both fonts, so no rescaling is needed).

Usage
-----
    python merge_cjk_font.py --target MinecraftSeven.otf \
                             --chars-file chars-zh-CN.txt \
                             --out MinecraftSeven-zh-CN.otf

    python merge_cjk_font.py --target F.otf --chars "伤害统计窗口" --out F-zh.otf

    # verify an already merged font
    python merge_cjk_font.py --verify F-zh.otf --chars-file chars-zh-CN.txt

Requirements: fontTools  (pip install fonttools)
CJK source:   Noto Sans SC, SIL Open Font License 1.1
"""
import argparse
import os
import sys

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib import TTFont

DEFAULT_CJK_SOURCES = [
    r"C:\Windows\Fonts\Noto Sans SC (TrueType).otf",
    r"C:\Windows\Fonts\Noto Sans SC Medium (TrueType).otf",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    r"/Library/Fonts/NotoSansSC-Regular.otf",
]


def load_cjk_source(explicit=None):
    candidates = [explicit] if explicit else []
    candidates += DEFAULT_CJK_SOURCES
    for path in candidates:
        if path and os.path.exists(path):
            try:
                font = TTFont(path, fontNumber=0)
                cmap = font.getBestCmap()
                print(f"  CJK source: {os.path.basename(path)} "
                      f"({len(cmap)} codepoints)")
                return font, cmap
            except Exception as exc:                    # noqa: BLE001
                print(f"  {path}: {exc}")
    raise SystemExit(
        "No CJK source font found. Install Noto Sans SC (OFL) or pass "
        "--cjk-source <path.otf|ttf|ttc>")


def read_chars(args):
    if args.chars_file:
        text = open(args.chars_file, encoding="utf-8").read()
    else:
        text = args.chars or ""
    chars = sorted({c for c in text if ord(c) > 0x7F and not c.isspace()})
    if not chars:
        raise SystemExit("no non-ASCII characters to merge")
    return chars


def draw_safely(gs, glyph_name, pen, fallback=".notdef"):
    """Draw a glyph, degrading to the fallback if it is a composite we cannot
    decompose (seac-style accents whose base is unavailable in this face)."""
    try:
        gs[glyph_name].draw(pen)
        return True
    except Exception:                                   # noqa: BLE001
        if fallback and fallback in gs:
            gs[fallback].draw(pen)
        return False


def charstring_for(src_gs, glyph_name, private, gsubrs):
    # T2CharStringPen needs a glyphSet so seac-style composites (base + accent)
    # can be resolved while drawing.
    pen = T2CharStringPen(0, None)
    pen.glyphSet = src_gs
    draw_safely(src_gs, glyph_name, pen)
    return pen.getCharString(private=private, globalSubrs=gsubrs)


def verify(path, chars):
    f = TTFont(path)
    cmap = f.getBestCmap()
    missing = [c for c in chars if ord(c) not in cmap]
    names = {}
    for rec in f["name"].names:
        try:
            if rec.nameID in (1, 2, 4, 6):
                names.setdefault(rec.nameID, rec.toUnicode())
        except Exception:                               # noqa: BLE001
            pass
    print(f"{os.path.basename(path)}")
    print(f"  glyphs      : {f['maxp'].numGlyphs}")
    print(f"  unitsPerEm  : {f['head'].unitsPerEm}")
    print(f"  family      : {names.get(1)!r}")
    print(f"  subfamily   : {names.get(2)!r}")
    print(f"  full name   : {names.get(4)!r}")
    print(f"  PostScript  : {names.get(6)!r}")
    print(f"  CJK present : {len(chars) - len(missing)}/{len(chars)}")
    if missing:
        print(f"  MISSING     : {''.join(missing)!r}")
        return 1
    return 0


def merge(args, chars):
    target = TTFont(args.target)
    order = list(target.getGlyphOrder())
    gs = target.getGlyphSet()
    cff = target["CFF "].cff
    cff_name = cff.fontNames[0]
    td = cff[cff_name]
    private, gsubrs = td.Private, cff.GlobalSubrs
    if private is None:
        raise SystemExit("target CFF has no Private dict")

    scale = target["head"].unitsPerEm / args.cjk_upem_override \
        if args.cjk_upem_override else 1.0
    src, src_cmap = load_cjk_source(args.cjk_source)
    scale = target["head"].unitsPerEm / src["head"].unitsPerEm
    src_gs = src.getGlyphSet()
    src_hmtx = src["hmtx"]

    charstrings, hmtx = {}, {}
    degraded = 0
    for g in order:
        pen = T2CharStringPen(0, None)
        pen.glyphSet = gs
        if not draw_safely(gs, g, pen):
            degraded += 1
        charstrings[g] = pen.getCharString()
        hmtx[g] = target["hmtx"][g]
    if degraded:
        print(f"  note: {degraded} composite glyph(s) fell back to .notdef")

    cmap = target.getBestCmap()
    added, missing = 0, []
    for ch in chars:
        cp = ord(ch)
        if cp in cmap:
            continue
        src_glyph = src_cmap.get(cp)
        if not src_glyph:
            missing.append(ch)
            continue
        name = "uni%04X" % cp
        while name in charstrings:
            name += "_"
        charstrings[name] = charstring_for(src_gs, src_glyph, private, gsubrs)
        width, _ = src_hmtx[src_glyph]
        hmtx[name] = (int(round(width * scale)), 0)
        order.append(name)
        cmap[cp] = name
        added += 1

    if missing:
        print(f"  !! CJK source lacks {len(missing)} characters: {''.join(missing)!r}")

    # keep the original name table verbatim so font identity is unchanged
    name_records = []
    for rec in target["name"].names:
        try:
            name_records.append((rec.nameID, rec.platformID, rec.platEncID,
                                 rec.langID, rec.toUnicode()))
        except Exception:                               # noqa: BLE001
            continue
    family = next((t for i, _, _, _, t in name_records if i == 1), cff_name)
    style = next((t for i, _, _, _, t in name_records if i == 2), "Regular")
    full = next((t for i, _, _, _, t in name_records if i == 4), family)
    ps_name = next((t for i, _, _, _, t in name_records if i == 6), cff_name)

    fb = FontBuilder(target["head"].unitsPerEm, isTTF=False)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupCFF(ps_name, {"FullName": full}, charstrings, {})
    fb.setupHorizontalMetrics(hmtx)
    fb.setupHorizontalHeader(ascent=target["hhea"].ascent,
                             descent=target["hhea"].descent,
                             lineGap=target["hhea"].lineGap)
    fb.setupNameTable({"familyName": family, "styleName": style,
                       "psName": ps_name, "fullName": full})
    fb.setupOS2(sTypoAscender=target["OS/2"].sTypoAscender,
                sTypoDescender=target["OS/2"].sTypoDescender,
                usWinAscent=target["OS/2"].usWinAscent,
                usWinDescent=target["OS/2"].usWinDescent)
    fb.setupPost()
    fb.font["head"].unitsPerEm = target["head"].unitsPerEm
    fb.save(args.out)
    print(f"  {os.path.basename(args.target)} -> {os.path.basename(args.out)}")
    print(f"  +{added} glyphs, {os.path.getsize(args.out)} bytes "
          f"(was {os.path.getsize(args.target)})")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", help="the original CFF/OTF font to extend")
    ap.add_argument("--out", help="where to write the merged font")
    ap.add_argument("--chars", help="characters to add, inline")
    ap.add_argument("--chars-file", help="file containing the characters to add")
    ap.add_argument("--cjk-source", help="CJK font file (Noto Sans SC by default)")
    ap.add_argument("--cjk-upem-override", type=float, default=None,
                    help="force the CJK source unitsPerEm (rarely needed)")
    ap.add_argument("--verify", help="verify an already merged font instead")
    args = ap.parse_args()

    if args.verify:
        chars = read_chars(args)
        return verify(args.verify, chars)
    if not (args.target and args.out):
        ap.error("--target and --out are required unless --verify is used")
    chars = read_chars(args)
    print(f"  merging {len(chars)} characters")
    return merge(args, chars)


if __name__ == "__main__":
    sys.exit(main())
