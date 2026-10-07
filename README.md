# DamageMeter — Simplified Chinese (zh-CN) localisation kit

Everything in this repository was produced while attempting to translate the
Nexus mod **Damage Meter** (Minecraft Dungeons II, mod id 93) into Simplified
Chinese. The translation itself is finished and verified; the only thing that
could not be done from the outside is repacking the shipped IoStore container,
because that requires the **cooked (unversioned) assets**, which only the
author's Unreal project can produce.

So this repo hands the author everything needed to add Chinese support natively.

---

## What is in here

| Path | What it is |
|---|---|
| `translations/modinfo.zh-CN.tsv` | Every ModInfo string: English → Chinese |
| `translations/hud.zh-CN.tsv` | Every in-game HUD string: English → Chinese |
| `translations/*.en.tsv` | The same tables with the original English only |
| `fonts/MinecraftSeven.otf` | The mod's font, with the 149 needed CJK glyphs merged in |
| `fonts/MinecraftFiveBold.otf` | same |
| `fonts/MinecraftFiveBoldSpaced.otf` | same |
| `tools/merge_cjk_font.py` | The script that produces the three fonts above |
| `tools/get_settings_ftexts.py` | Locates every FText in `ModInfo.uasset` with exact byte offsets |
| `tools/apply_translation.py` | Reference patcher (works on cooked container chunks) |
| `TECHNICAL.md` | Package-format notes gathered while reverse-engineering |
| `LICENSES/` | OFL notice for the CJK source font, retoc licence |

---

## The three things the mod needs for Chinese

### 1. The strings

`translations/modinfo.zh-CN.tsv` and `hud.zh-CN.tsv` are tab-separated
`English<TAB>Chinese` pairs. The English side is the exact current text, so you
can find each field by searching for it.

The strings come from two assets:

* **`ModInfo`** — the Data Asset. Its `ModName`, `Description`, and every
  `Settings` entry's `Label` / `Description` / `Button Text` / `Placeholder`.
* **`WBP_DamageProbe`** — the widget. Eight literal strings that are baked into
  the widget graph (`No data`, `DAMAGE DETAILS`, `Total`, the key-hint texts,
  the `0 DPS` / `MAX 0 DPS` / `RUN 0:00` readouts).

`Damage` / `Dps` / `Total` etc. are bound to runtime values — only the static
labels need translating.

### 2. The font

**This is the part that will silently break Chinese if it is skipped.**

The mod ships three custom CFF/OTF faces derived from the Minecraft fonts:

| Asset | Original glyphs | CJK |
|---|---|---|
| `MinecraftSeven` | 618 | none |
| `MinecraftFiveBold` | 625 | none |
| `MinecraftFiveBoldSpaced` | 625 | none |

They contain **no CJK glyphs at all** (max codepoint `U+FB02`), so every Chinese
character renders as a missing-glyph box, no matter how correct the strings are.
The widget imports `MinecraftSeven` and `MinecraftFiveBoldSpaced` for its text.

The three fonts in `fonts/` already carry CJK coverage, merged in while keeping
the original Minecraft letterforms, metrics and family/style names:

| | Glyphs | Size |
|---|---|---|
| `MinecraftSeven.otf` | 7470 | 1.53 MB |
| `MinecraftFiveBold.otf` | 7363 | 1.49 MB |
| `MinecraftFiveBoldSpaced.otf` | 7363 | 1.49 MB |

**Coverage is GB2312 — 6 763 hanzi plus CJK punctuation — not just the 149
characters this translation happens to use.** That was a deliberate choice: pet
and companion damage is on your roadmap, and a 149-character subset would have
had no glyphs for exactly the words that feature needs. Sized options measured
against `MinecraftFiveBold`:

| Set | Size | `同伴` `宠物` `随从` `召唤` `队友` |
|---|---|---|
| 149 chars (this translation only) | 0.06 MB | **absent** |
| **6 763 chars (GB2312, shipped)** | **1.49 MB** | present |
| 20 902 chars (full CJK block) | 5.05 MB | present |

GB2312 was picked because it is derived programmatically from the codec rather
than from a hand-typed word list, so it is reproducible and auditable.

If you would rather ship the small variant, regenerate from
`translations/chars-required.txt` instead of `chars-zh-CN.txt`; both files are in
the repo, and the same script produces either.

`upem` is 1000 in both the mod fonts and Noto Sans SC, so no rescaling was needed
and the CJK advance width is 1000 (full-width), which sits correctly next to the
860-wide Latin glyphs.

Drop the fonts over the existing font assets (same object names, same paths) —
the widget's existing references then resolve to CJK-capable faces.

To regenerate, with a local Noto Sans SC:

```
python tools/merge_cjk_font.py --target <font.otf> \
    --chars-file translations/chars-zh-CN.txt --out <out.otf>
python tools/merge_cjk_font.py --verify <out.otf> --chars-file translations/chars-zh-CN.txt
```

`tools/merge_cjk_font.py --help` documents it. The CJK source is
`Noto Sans SC (Regular)`, SIL Open Font License 1.1 — see `LICENSES/`.

One codepoint in `chars-zh-CN.txt` is intentionally not merged: `U+3000`
(ideographic space). It is whitespace, so the merger's `isspace()` filter drops
it, and nothing is lost — a space needs no outline.

### 3. A rebuild

Cook the project and pack it exactly as `build_mod.py` in the Blueprint Mod
Template already does. No build change is required; the strings and fonts are
the only new content.

---

## Suggested implementation (smallest diff in the author's project)

1. Keep the English strings as they are, and add a language check.
   The game's current language is readable from `GetGameUserSettings` /
   `Culture` — or simpler, expose the strings through a small `Settings`-style
   indirection and pick the table at Begin Play.
2. Copy the Chinese values from the TSVs into that table.
3. Replace the three font assets with the ones in `fonts/`.
4. Rebuild.

If the author prefers to keep it even simpler and ship a **separate Chinese
build** instead of a language switch, only step 2 and 3 are needed: paste the
Chinese text straight into `ModInfo` and the widget literals, drop in the
fonts, rebuild.

---

## What was verified, and what was not

Verified by reading the shipped container byte by byte:

* the exact 27 `ModInfo` strings and 10 `WBP_DamageProbe` strings, with the
  FString framing (`int32 length+1` immediately before the body, NUL after)
* the three fonts, their glyph counts, their empty CJK coverage, and their
  family/style names
* that the merged fonts contain all 149 needed codepoints alongside the
  original glyphs (`tools/merge_cjk_font.py` output was re-parsed and checked)
* that the translated strings, once written, re-read with correct
  framing — i.e. the translation data in this repo is self-consistent

Not verified (cannot be, from outside):

* that the game renders the result correctly in situ — that needs the author's
  cook and a copy of the game

About the damage sources (from the shipped widget's name table):

* the mod hooks `SW.Event.DealtDamage` globally, and carries
  `Coop0`/`Coop1`/`Coop2` slots plus `PartyNames`/`GetPartySystem`, so **party
  damage is already handled**;
* no `Pet`/`Minion`/`Summon`/`Companion` identifier exists anywhere in the
  assets, which matches the author's statement in the mod comments that
  **companion damage is not implemented yet and is planned**.

That second point is exactly why the fonts in this repo carry the full GB2312
repertoire instead of only the characters the current translation uses. When
companion damage lands and the UI needs strings like `同伴伤害` / `宠物伤害`, the
glyphs will already be there.

---

## Credit / provenance

* Damage Meter by **sucmerp** — <https://www.nexusmods.com/minecraftdungeons2/mods/93>
* Blueprint Loader by **Dokucraft (ewanhowell)**
* CJK glyph source: **Noto Sans SC**, SIL Open Font License 1.1
* Packing tooling: **retoc** and **repak** by trumank

Nothing here redistributes the mod's own binaries. The fonts are provided as
drop-in replacements for assets the author already ships; they are derived from
the author's own font files plus OFL-licensed CJK outlines.
