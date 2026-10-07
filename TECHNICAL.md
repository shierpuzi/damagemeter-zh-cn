# Technical notes — Damage Meter (MCD2) package format

Written down while translating the mod from the outside, because none of this is
documented anywhere. Everything here was verified by reading the shipped
container byte by byte, and each claim says how it was checked. If any of it is
wrong, the check that produced it is stated so it can be repeated.

Container under discussion: `DamageProbe_P.utoc` (1133 B) + `DamageProbe_P.ucas`
(719729 B) + `DamageProbe_P.pak` (9597 B), from Damage Meter 1.2.0.

---

## 1. The three files, and which one the game actually uses

| File | What it holds |
|---|---|
| `DamageProbe_P.pak` | a legacy UE pak holding the cooked `ModInfo` / `ModActor` **class** structures |
| `DamageProbe_P.utoc` + `.ucas` | an IoStore container holding the **data** assets (`ModInfo`, `ModActor`, fonts, widget) |
| `DamageMeter.dll` | a native hook DLL (MinHook); not involved in the text |

Evidence for the split: the `.pak` byte range for `ModInfo` contains the property
names (`Description`, `ModName`, `Settings`, ...) and class paths, but **none** of
the visible text — `Damage Meter`, `Window appearance` and friends are absent
from the whole 9597-byte pak. All of them sit in the `.ucas`.

Practical consequence: **the text lives in the IoStore container**, so any
localisation has to end up in a rebuilt `.utoc` + `.ucas`.

---

## 2. Container layout (`retoc info` reports: 8 chunks, 7 packages)

`retoc unpack` extracts 7 assets; the 8th chunk is the `ContainerHeader`.

### Chunk order and sizes

Proven by rebuilding the `.ucas` payload in this order and getting a
byte-identical file:

| # | Asset | Offset | Size |
|---|---|---|---|
| 0 | `MinecraftSeven` | 0 | 29759 |
| 1 | `ModActor` | 29759 | 9423 |
| 2 | `ModInfo` | 39182 | 18195 |
| 3 | `BP_DamageMeterSession` | 57377 | 1997 |
| 4 | `MinecraftFiveBold` | 59374 | 50723 |
| 5 | `MinecraftFiveBoldSpaced` | 110097 | 47519 |
| 6 | `WBP_DamageProbe` | 157616 | 561793 |
| 7 | `ContainerHeader` | 719409 | 320 |

Chunks are contiguous, no padding, no compression (`compression_methods: []`).

### utoc regions

| Range | Contents |
|---|---|
| `0x00..0x90` | header: magic `-==--==--==--==-`, version 8, header size 0x90, chunk count 8 |
| `0x90..0xF0` | 8 chunk descriptors, 12 bytes each: `u64 hash` then `u32 chunkType` (**big-endian** on disk, so `01 00 00 00` is type 1, `06 00 00 00` is type 6 = ContainerHeader) |
| `0xF0..0x140` | reserved / zero |
| `0x140..0x210` | per-chunk size and offset fields (see below) |
| `0x1C0..0x450` | FileIndex / DirectoryIndex |
| `0x450..0x46D` | trailer |

### Size / offset fields

**Not a plain array.** The values are interleaved and the two 16-bit halves are
byte-swapped. Established by mutating one 4-byte field at a time and asking
`retoc unpack-raw` to read the container back, observing which asset's extracted
length or content changed:

| Field | Location |
|---|---|
| chunk `i` size | `0xF8 + 20*i` |
| chunk `i` offset | `0x14C + 20*i` |

Checked for `i = 0..5` and for the WBP chunk; the mutant values read back as
`old + 16`, which is why the effect was first mistaken for a live offset.

**This is why the container could not be rebuilt from outside.** Both the size
and the offset table must be rewritten when a chunk changes length, and the
layout above was only pinned down after the fact. `retoc pack-raw` rebuilds the
container but emits 7 chunks and drops the `ContainerHeader`, which the shipped
container has and the game reads for package metadata.

---

## 3. Asset payload format

The container assets are **unversioned cooked packages**, not the standard
versioned `.uasset` a project source tree holds. Their first four bytes are small
values (`00 00 00 00`, `01 00 00 00`), not the package tag `0x9E2A83C1`.

Consequences:

* `retoc to-zen` refuses them with
  `does not have a split exports file` /
  `Package file magic mismatch: 1 (expected 2653586369)`.
* `retoc to-legacy` also fails on them (`Extracted 0 (7 failed)`).
* The Blueprint Mod Template's own `Templates/ModInfo.uasset` behaves the same
  way, because it is the **source** asset, which must be cooked first.

`build_mod.py` in the template makes the container like this:

```
cook(versioned)    -> header assets (ModActor, ModInfo) for the .pak
cook(unversioned)  -> staging (ModActor, ModInfo, fonts, WBP)
retoc to-zen --version UE5_6 staging  -> <Mod>_P.utoc (+ a stub .pak, deleted)
repak pack --version V11 header_root  -> <Mod>_P.pak
```

So a working `.utoc` requires the **cooked unversioned** assets, which only an
Unreal Engine 5.6.1 cook of the author's project can produce. That is the single
blocking dependency; nothing about the translation itself needs it.

---

## 4. String framing

Visible text is stored as UE FString bodies:

```
[ ... ][ int32 length+1 ][ body bytes ][ 0x00 ]
```

* `length+1` sits exactly four bytes before the body and counts the body plus its
  NUL terminator. **It is the value the engine consumes.**
* The byte right after `body` is always `0x00`.

Verified by scanning both `ModInfo` and `WBP_DamageProbe`; in the original
container 41 framed strings exist in `ModInfo` and 10 in `WBP_DamageProbe`, and
every visible UI string is among them.

Because the declared length is authoritative, a replacement may be a different
byte length as long as that dword is rewritten too. That is what
`tools/apply_translation.py` does. Writing the Chinese text made the asset
*shorter* overall (18195 → 18172 bytes), which is why simply keeping the original
container offsets was not an option.

### What must NOT be translated

The internal setting identifiers are also stored as framed strings:

```
position_x  position_y  window_scale  background_opacity  meter_opacity
show_dps  show_max_dps  show_timer  auto_reset  dps_mode
toggle_key  reset_key
```

They are the keys the widget uses to read and write settings. Translating them
silently breaks the settings page. The shipped tables exclude them.

---

## 5. Fonts

Three CFF/OTF faces ship inside the container, carved out as plain `OTTO` files:

| Asset | Original glyphs | Max codepoint | CJK |
|---|---|---|---|
| `MinecraftSeven` | 618 | `U+FB02` | none |
| `MinecraftFiveBold` | 625 | `U+FB02` | none |
| `MinecraftFiveBoldSpaced` | 625 | `U+FB02` | none |

* `unitsPerEm` is **1000**, the same as Noto Sans SC, so CJK outlines need no
  rescaling and land on a 1000-unit (full-width) advance next to 860-unit Latin.
* The widget imports `MinecraftSeven` and `MinecraftFiveBoldSpaced` for its text
  (found in the widget's name table and its five font-object references), so
  **both** need CJK coverage or Chinese renders as boxes however correct the
  strings are.
* Original name tables are inconsistent — `familyName` is `Minecraft` while
  `fullName` is `Minecraft Seven` / `Minecraft Five Bold` — and the widget's
  `TypefaceFontName` does not match either exactly, yet the mod renders, so the
  engine tolerates the mismatch. `tools/merge_cjk_font.py` therefore **preserves
  the original name table verbatim** rather than normalising it, so nothing about
  the existing resolution changes.

### How much CJK coverage to merge

The mod has no companion/pet damage yet (confirmed by the author), so the font
repertoire had to be chosen with future UI strings in mind rather than only
today's translation. Measured against `MinecraftFiveBold`:

| Character set | Codepoints | Merged size | Covers `同伴 宠物 随从 召唤 队友` |
|---|---|---|---|
| current translation only | 149 | 0.06 MB | no |
| **GB2312 (shipped)** | **6 818** | **1.49 MB** | yes |
| full CJK Unified Ideographs block | 20 902 | 5.05 MB | yes |

GB2312 is generated programmatically (iterate `0xB0A1..0xF7FE` through the
`gb2312` codec) rather than from a hand-typed frequency list, so the set is
reproducible and auditable. `translations/chars-required.txt` holds the 149
characters strictly needed today for anyone who prefers the small build.

`U+3000` (ideographic space) appears in `chars-zh-CN.txt` but is intentionally
not merged: it is whitespace, so the merger's `isspace()` filter drops it, and a
space needs no outline.

---

## 6. Damage sources (from the shipped widget's name table)

| Identifier | Count | Meaning |
|---|---|---|
| `SW.Event.DealtDamage` | 4 | global "damage was dealt" event — the main source |
| `Coop0` / `Coop1` / `Coop2` | 10 each | three tracked co-op players |
| `PartyNames`, `GetPartySystem` | 2 / 1 | party membership and names |
| `ReceiveFinalDamageNumber`, `NDC_DamageNumber` | 1 / 4 | the game's own floating damage-number pipeline |
| `SW.GameplayMessage.DungeonBossKill` | 1 | boss-kill detection |
| `Pet` / `Minion` / `Summon` / `Companion` | 0 | **absent** |

So **party damage is already implemented**. Pet/companion damage has no separate
identifier anywhere in the assets, which matches the author's statement in the
mod comments that **companion damage is not implemented yet and is planned**.
Whether companion hits currently land in the damage total (they go through the
same global `DealtDamage` event) cannot be determined without running the game;
either way, splitting them into their own row is a mod change, not a translation
change.

---

## 7. What could not be done from outside

1. **Repacking the container.** Needs the cooked unversioned assets, i.e. an
   Unreal Engine 5.6.1 cook of the author's project (see §3).
2. **Verifying the result in situ.** Needs the game plus a rebuilt mod.
3. **Editing the `.pak`.** Its `ModInfo` is a different (versioned, full package)
   serialisation from the container's; a window-by-window comparison found no
   shared byte run, so the container's bytes cannot be pasted into it.
