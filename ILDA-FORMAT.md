# Laser projector file formats — reverse-engineered spec

Derived from `projector-files/` (20 `.ild`, 1 `.prg`, 1 `.bac`) and verified by
a byte-exact round trip: `ilda.py` re-reads and rewrites all 20 files to
**identical SHA-256** (3,525 frames, 2,245,807 points, zero trailing bytes).

The `.ild` files are the **ILDA Image Data Transfer Format** — an open industry
standard, not a vendor format. Every file here uses **Format 0**.

---

## 1. `.ild` — the animation files

A file is a chain of `[32-byte header][N × 8-byte point records]` blocks, one
per frame, ending with a header whose record count is **0**. All integers are
**big-endian, signed** (network byte order — not x86 order).

### 1.1 Frame header (32 bytes)

| Off | Size | Field | Observed in these files |
|----:|-----:|-------|-------------------------|
| 0   | 4    | Magic `"ILDA"` | always |
| 4   | 3    | Reserved, zero | always `00 00 00` |
| 7   | 1    | **Format code** | always `0` = 3D, indexed colour |
| 8   | 8    | Frame name (ASCII, space-padded) | varies **per frame**: `EARTH1.DE3`, `EARTH2.DE3`… |
| 16  | 8    | Company name (ASCII) | often a continuation of the name field |
| 24  | 2    | **Record count N** | 1–1867; `0` marks end of file |
| 26  | 2    | Frame number | sequential from 0 in all 3,525 frames |
| 28  | 2    | Total frames | equals the real frame count |
| 30  | 1    | Projector / scanner head | always `0` |
| 31  | 1    | Reserved | always `0` |

Name and company are really one 16-char string in most of these files
(`"LCMax Fr" + "ame 1   "` = `LCMax Frame 1`). Don't assume they're independent.

**The record count is authoritative** — use it to find the next header. Frame
sizes vary within a file, so blocks are not evenly spaced.

**Format codes** (only 0 appears here): 0 = 3D indexed, 1 = 2D indexed,
2 = colour-palette block, 4 = 3D true-colour BGR, 5 = 2D true-colour BGR.

### 1.2 Point record — Format 0 (8 bytes)

| Off | Type | Field |
|----:|------|-------|
| 0 | int16 BE | **X** −32768…32767, +X right |
| 2 | int16 BE | **Y** −32768…32767, **+Y up** |
| 4 | int16 BE | **Z** −32768…32767, +Z toward viewer |
| 6 | uint8    | **Status bits** |
| 7 | uint8    | **Colour index** 0–63 |

**Status bits** — only two are used, and only three byte values ever occur
across 2.2M points: `0x00` (1,569,666), `0x40` (673,223), `0xC0` (2,918).

- **bit 6 `0x40` = blank.** Beam **off** while moving *to* this point.
  Blanking describes the segment *arriving at* the point, not leaving it.
- **bit 7 `0x80` = last point of frame.** Advisory. 17 of 20 files set it;
  `aa.ild`, `west.ild` and `ian.ild` never do. **Trust the record count, not
  this bit** — but do set it when writing, since some players rely on it.

`aa.ild` (2012) and `ian.ild` (2017) are the collection's outliers: they are
the only files that skip the LAST flag *and* the only ones with frames ending
on a lit point (6 frames). `aa.ild` also contains a degenerate **1-point
frame**. Written by a looser tool than the rest — worth knowing if you parse
third-party content, since a strict parser will trip on them.

**Colour index** selects from the ILDA 64-colour default palette (index 0 red …
16 yellow, 24 green, 31 cyan, 40 blue, 48 magenta, 56 white). No file here
carries its own Format-2 palette block, so the projector's built-in palette
applies. By convention blanked points also carry colour 0, but the blanking bit
is what actually controls the beam.

**Z is real, not padding** — 32% of points use it (`SNOW`, `earthrot`,
`Aurora17`, `Aurora51` are ~99% 3D). If your projector ignores Z, X/Y still
render correctly.

---

## 2. `.prg` — the playlist, and `.bac` — its backup

Plain ASCII, one entry per line, comma-separated:

```
<filename>,<field2>,<field3>[,i]
```

```
aa.ild,15,1
Aurora14.ild,8,15
Aurora17.ild,10,2,i
```

Verified details:

- **Line endings are CRLF**, except `Picture.prg`'s *first* line, which ends
  with a bare LF — so the player tolerates both.
- **Filenames are case-insensitive.** 11 of 18 entries differ in case from the
  actual file (`swirl.ild` → `SWIRL.ild`, `747-01.ILD` → `747-01.ild`).
  Consistent with a FAT-formatted SD card.
- **Whitespace is tolerated**: `Aurora51.ild,10,1 ` has a trailing space.
- The file ends with four blank CRLF lines; all 18 referenced files exist.
- `.bac` is the **previous playlist**, kept automatically. `Picture.bac`
  (dated 3 Nov 2012) lists only `west.ild` — the same day `west.ild` was
  created — and `Picture.prg` is dated one day later. So editing the playlist
  rotates the old one to `.bac`.

### What the numbers mean

**Field 3 = repeat count** (confidence: high). It scales inversely with
animation length exactly as a loop count should: the 14-frame `Aurora14` is the
only entry with 15 repeats, while every 255+ frame file gets 1.

**Field 2 = a timing parameter, either frames-per-second or display seconds**
(confidence: unresolved). Its values are `{8, 10, 15, 18, 20}` — equally
plausible as a frame rate or as a per-clip duration, and the file contents
can't distinguish the two. `Picture.bac` looks like someone testing exactly
this: the same `west.ild` listed four times as `15,1 / 20,1 / 10,2 / 15,1,i`.

> **Resolve it in two minutes.** Copy `timing_test.ild` (60 frames, one
> revolution of a clock hand) to the card with a playlist of
> `timing_test.ild,10,1` and time one revolution:
> **~6 s → field 2 is fps** (60 frames ÷ 10). **~1 s, clip lasting ~10 s →
> field 2 is seconds.**

**The `,i` flag is unknown** (appears on `Aurora17`, `Aurora26`, and the last
`.bac` line). 16 of 18 entries omit it — so omit it unless you're testing.

---

## 3. Writing content the scanners can actually draw

Galvanometer mirrors have mass. A geometrically correct point list still looks
wrong on the wall unless it respects how they move. Measured from the reference
files (units are of 65,536 full scale):

| Practice | Measured in the reference files |
|---|---|
| **Cap the lit step size** | median 709, p90 1561, p99 2285, max 3780. Subdivide long lines. |
| **Blanked jumps may be larger** | median 1586, up to full-scale — but still interpolate them. |
| **Dwell on repeated points** | 106,377 repeat runs; most commonly 4 points, often 12+. |
| **Dwell after unblanking** | `PeaceDo` frame 0 opens with 4 blanked points at the start position, then 6 lit ones, before moving. |
| **End every frame blanked** | 3519/3525 frames. The 6 exceptions are all in `aa.ild` / `ian.ild` (see below). |
| **Budget points per frame** | median 655, max 1867. Points/frame × fps must stay under the projector's point rate (typically 20–30 kpps). At 20 kpps and 20 fps that's ~1000 points. Overrun and the projector slows the frame rate — the animation drags and flickers. |

`ilda.FrameBuilder` applies all of this automatically.

---

## 3a. Measuring your projector's point rate

`timing_test.ild` alone gives you the **frame rate**, not the point rate — it
draws one revolution of a clock hand per 60 frames, so timing one revolution
tells you how fast frames advance. To get points-per-second you need to find
where the projector runs out of headroom.

`make_demo.py` writes a ladder for this: `rate400.ild`, `rate800.ild`,
`rate1600.ild`, `rate3200.ild`, `rate6400.ild`. Each is the *same* clock padded
to a different points-per-frame count. The padding is blanked dwell points,
which cost the scanner exactly as much time as lit ones — the beam still has to
travel — so the picture is identical at every step and the only variable is
scan cost.

**Procedure**

1. Copy the five `rate*.ild` files to the card with one playlist line each,
   all with identical parameters (e.g. `rate400.ild,15,1`).
2. Time **one full revolution** of the hand in each, with a phone stopwatch.
   The red index mark at 12 o'clock is the start and end.
3. Tabulate. While the projector has headroom the revolution time is **flat**.
   Once `points/frame × fps` exceeds its point rate it can no longer keep up and
   the time grows **in proportion** to points/frame. That knee is the answer.

**Reading the result** — on any file past the knee:

```
points per second  ≈  points_per_frame × 60 / revolution_seconds
```

A worked example. Suppose you measure:

| File | pts/frame | Revolution |
|---|---:|---:|
| `rate400` | 400 | 4.0 s |
| `rate800` | 800 | 4.0 s |
| `rate1600` | 1600 | 4.0 s |
| `rate3200` | 3200 | 6.4 s |
| `rate6400` | 6400 | 12.8 s |

Flat through 1600, then doubling. The projector is saturated at 3200:
`3200 × 60 / 6.4 = 30,000 pps` — a 30 kpps head. The flat region also tells you
the frame rate is `60 / 4.0 = 15 fps`, which independently confirms field 2 of
the playlist is **frames per second** (the line said `15`).

That second reading is a bonus: **the ladder settles the playlist-field question
at the same time**, because a flat revolution time means frames are advancing at
a fixed rate you can read straight off.

Then size your own animations so `points/frame × fps` stays under the measured
rate, with some margin.

---

## 4. Toolkit

| File | Purpose |
|---|---|
| `ilda.py` | Read/write library + `FrameBuilder`. Round-trips all 20 reference files byte-exact. |
| `ildaview.py` | Preview to PNG contact sheet or animated GIF — check work without the projector. |
| `make_demo.py` | Generates `starfield.ild`, `psg.ild` (rotating text), `cube.ild` (3D, uses Z), `lissajous.ild`, `timing_test.ild`, and the `rate*.ild` ladder. |
| `strokefont.py` | Single-stroke vector font (A–Z, 0–9, punctuation) for laser text. |
| `test_roundtrip.py` | The correctness proof: rewrites all 20 reference files byte-exact and checks the invariants above. Run `python3 test_roundtrip.py`. |

```python
import ilda, math
from ilda import FrameBuilder, CYAN

frames = []
for f in range(60):
    a = 2 * math.pi * f / 60
    fb = FrameBuilder()                      # handles blanking, dwell, interpolation
    fb.polyline([(26000 * math.cos(t + a), 26000 * math.sin(t + a))
                 for t in [2 * math.pi * i / 5 for i in range(6)]],
                color=CYAN, closed=True)     # a spinning pentagon
    frames.append(fb.build())

ilda.write('spin.ild', frames, name='SPIN', company='ME', last_flag=True)
```

Preview it, then copy to the card and add a playlist line:

```
python3 ildaview.py spin.ild --gif --fps 20
```
