"""
bongocat.py -- the bongo cat meme as a laser animation.

Geometry is traced from the project's own sprite frames
(BongoCat/bongo-cat-stm32/docs/frame_*.png) rather than redrawn by eye. The
first hand-drawn attempt got the anatomy wrong: it put the paws on the body as
free-floating circles, when in the original they are the ends of the arms and
part of the body silhouette, and the belly line runs between them.

Each sprite is thinned to a centreline, traced into polylines and simplified,
which turns ~330 lit pixels into ~27 strokes of ~75 vertices -- cheap enough to
scan at a high refresh while still matching the original drawing.
"""
import math

import ilda
from ilda import FrameBuilder, WHITE
from trace_bitmap import load_png, strokes

DOCS = '/Users/ctolleson/Documents/Claude/BongoCat/bongo-cat-stm32/docs/'
SPRITES = {
    'A': 'frame_paws_on_air.png',
    'L': 'frame_left_paw_on_table.png',
    'R': 'frame_right_paw_on_table.png',
    'B': 'frame_paws_on_table.png',
}


def _order(sts):
    """Greedy nearest-neighbour stroke order, to cut blanked travel.

    Every stroke costs a blanked jump plus dwell at both ends, so with 27 of
    them the travel between strokes dominates the frame, not the drawing.
    """
    rest = list(sts)
    out = []
    cur = (0.0, 0.0)
    while rest:
        best, rev, bd = None, False, None
        for i, s in enumerate(rest):
            for r, end in ((False, s[0]), (True, s[-1])):
                d = (end[0]-cur[0])**2 + (end[1]-cur[1])**2
                if bd is None or d < bd:
                    best, rev, bd = i, r, d
        s = rest.pop(best)
        if rev:
            s = s[::-1]
        out.append(s)
        cur = s[-1]
    return out


def _load():
    """Traced strokes per state, plus the shared bbox so nothing jitters."""
    raw = {k: strokes(load_png(DOCS + f)) for k, f in SPRITES.items()}
    pts = [p for sts in raw.values() for s in sts for p in s]
    x0 = min(p[0] for p in pts); x1 = max(p[0] for p in pts)
    y0 = min(p[1] for p in pts); y1 = max(p[1] for p in pts)
    return {k: _order(v) for k, v in raw.items()}, (x0, y0, x1, y1)


def frames(pattern=('L', 'R', 'L', 'R', 'B', 'L', 'R', 'B'),
           beat=30, hit=12, colour=WHITE, width=58000):
    """Render the drum pattern. Between strikes the cat returns to paws-up.

    `beat` is in FRAMES, and on this projector frames advance at the refresh
    rate -- which for a frame this cheap is well over 60 Hz. Tempo is therefore
    a matter of frame count: 30 frames a beat runs eight beats in ~3.4 s, about
    140 BPM.
    """
    art, (x0, y0, x1, y1) = _load()
    scale = width / (x1 - x0)
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0

    def to_laser(p):
        # image y runs down, laser y runs up
        return ((p[0] - cx) * scale, (cy - p[1]) * scale)

    out = []
    for step in pattern:
        for f in range(beat):
            state = step if f < hit else 'A'
            fb = FrameBuilder(max_step=1500, dwell_start=3, dwell_end=2,
                              dwell_blank=2)
            for s in art[state]:
                fb.polyline([to_laser(p) for p in s], color=colour)
            out.append(fb.build())
    return out


if __name__ == '__main__':
    fr = frames()
    n = ilda.write('bongocat.ild', fr, name='BONGOCAT', company='CLAUDE',
                   last_flag=True)
    pts = [len(f) for f in fr]
    import make_demo as m
    print(f"bongocat.ild  {len(fr)} frames  {min(pts)}-{max(pts)} pts/frame  "
          f"{n} bytes  -> {m.refresh_hz(max(pts), 30):.1f} Hz at 30 kpps, "
          f"{len(fr)/m.refresh_hz(max(pts), 30):.2f}s per cycle")
