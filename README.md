# Laser Projector — ILDA toolkit

Reverse-engineered file formats for an ILDA laser projector, plus a Python
toolkit for authoring your own animations.

The projector's `.ild` files turned out to be the **ILDA Image Data Transfer
Format** — an open industry standard rather than a vendor format — so content
authored here works on other laser hardware too. The accompanying `.prg` files
are plain-text playlists.

**[ILDA-FORMAT.md](ILDA-FORMAT.md) is the full specification**, covering the
frame header, the point record, the status bits, the playlist format, and the
scanner-safety practices measured from real content.

## Toolkit

| File | Purpose |
|---|---|
| `ilda.py` | Read/write library plus `FrameBuilder`, which applies the blanking, interpolation and dwell-point discipline that real scanners need. |
| `ildaview.py` | Preview to a PNG contact sheet or animated GIF — check work without the projector. |
| `make_demo.py` | Example animations: `starfield`, `psg` (rotating text reveal), `cube` (3D), `lissajous`, `timing_test`, plus the `rate*` point-rate ladder. |
| `strokefont.py` | Single-stroke vector font (A–Z, 0–9, punctuation). A laser can't use a normal font — TrueType glyphs are filled outlines, so tracing one draws a hollow letter. |
| `test_roundtrip.py` | The correctness proof. |

## Correctness

The format model is established by round trip: every reference file is parsed
and rewritten to an **identical SHA-256** — 20 files, 3,525 frames, 2,245,807
points. Nothing is unaccounted for or silently normalised.

```
python3 test_roundtrip.py
```

That test is what caught the per-frame name/company header fields and the EOF
header's own metadata, both of which a naive reader drops.

## Usage

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

```bash
python3 make_demo.py                          # build the example animations
python3 ildaview.py spin.ild --gif --fps 20   # preview before sending to hardware
```

Then copy the `.ild` to the projector's card and add a playlist line
(`spin.ild,15,1`).

### Watch the point budget

Points-per-frame × fps must stay under the projector's point rate (typically
20–30 kpps). Exceed it and the hardware doesn't error — it just slows down, and
the animation drags and flickers. Reference content runs a median of 655 points
per frame.

To measure your own projector's rate, `make_demo.py` writes a ladder of files
(`rate400.ild` … `rate6400.ild`): the same clock animation padded to different
point counts with blanked dwells, which cost scan time but draw nothing. Time
one revolution of each; the point where revolution time stops being flat is your
limit. Full procedure in
[ILDA-FORMAT.md](ILDA-FORMAT.md#3a-measuring-your-projectors-point-rate).

## Requirements

Python 3 and Pillow (for `ildaview.py` only; `ilda.py` is dependency-free).

## Note on `projector-files/`

These are the projector's own bundled reference files, included so the
byte-exact round-trip proof is reproducible by anyone who clones the repo.

They are **third-party content, not original work in this repository**, and
several carry copyright notices embedded in their frame header fields:

| File | Embedded notice |
|---|---|
| `PeaceDo.ild` | `(c) 2001 Laser F…` / `L. Michael Rober…` |
| `SNOW.ild` | `© LDG` (in all 255 frames) |
| `x3.ild` | `MediaLas` |
| `Aurora*`, `SWIRL*`, `TRAIN2`, `earthrot`, `SPRT2` | `.DE3` commercial show-library content |

They are present here for format research and interoperability only. Rights
remain with their respective owners; if you are an owner and want a file
removed, please open an issue.

The toolkit itself (`ilda.py`, `ildaview.py`, `make_demo.py`,
`test_roundtrip.py`, `ILDA-FORMAT.md`) is original work.
