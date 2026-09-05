"""
bongocat.py -- the bongo cat meme as a laser animation.

Traced from the reference frames in BongoCat/bongo-cat-stm32/docs: the cat sits
behind a table edge that runs diagonally down to the right, and alternately
slaps it with each paw.

Two things make this cheap enough to draw at a high refresh:

  * The table edge doubles as the cat's lower outline. The body is an OPEN path
    that starts and ends exactly on the table line, so the beam never retraces
    a segment it has already drawn.
  * Impact dashes are only emitted on the frames where a paw is actually down,
    so the frame cost rises only during a hit.
"""
import math

import ilda
from ilda import FrameBuilder, WHITE

# Art spans x -115..115 and y -30..53. Scale so the width nearly fills the
# projector's +/-32767, and shift so the composition sits centred vertically.
SCALE = 243.0
Y_SHIFT = -11.5
TABLE = ((-115.0, 18.0), (115.0, -30.0))


def _table_y(x):
    (x0, y0), (x1, y1) = TABLE
    return y0 + (x - x0) * (y1 - y0) / (x1 - x0)


# Body: an open path from the table on the left, over the ear, down to the
# table on the right. Both ends sit ON the table line by construction.
BODY = [
    (-58, 6.1), (-52, 14), (-44, 21), (-33, 28), (-20, 34), (-8, 40),
    (0, 46), (4, 53),                                   # ear tip
    (9, 44), (16, 39), (26, 34), (37, 28), (47, 22), (54, 17),
    (57, 20), (62, 22), (66, 16),                       # right ear notch
    (68, 8), (69, -2), (68, -10), (64, -16), (60, -18.5),
]

# Drawn a little heavier than the reference sprite: at this size a laser
# swallows one- or two-unit marks, and the face is what makes it read as a cat.
# Sits about a third of the way along the body, matching the reference -- and
# clear of the right paw, which occupies x 13..35 when raised.
FACE = [
    [(-26, 14), (-26, 20)],                             # left eye
    [(-15, 12), (-15, 18)],                             # right eye
    [(-9, 9), (-6, 5.5), (-3, 9), (0, 5.5), (3, 9)],    # mouth
]

# Paw travel: up (raised) -> down (on the table).
PAWS = {
    'left':  {'up': (-46, 13), 'down': (-55, 3.5)},
    'right': {'up': (24, -1), 'down': (17, -12)},
}


def _ellipse(cx, cy, rx, ry, n=12):
    return [(cx + rx * math.cos(2 * math.pi * i / n),
             cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]


def _paw(cx, cy):
    """A paw: rounded blob plus two toe splits along its lower edge."""
    out = [_ellipse(cx, cy, 11, 8.5, 12)]
    out.append([(cx - 4, cy - 7.7), (cx - 4, cy - 3)])
    out.append([(cx + 3, cy - 8.1), (cx + 3, cy - 3.5)])
    return out


def _impact(cx, cy):
    """Dashes radiating from a struck paw -- only drawn on hit frames."""
    out = []
    for deg, r0, r1 in ((205, 12, 20), (250, 11, 19), (295, 12, 20)):
        a = math.radians(deg)
        out.append([(cx + r0 * math.cos(a), cy + r0 * math.sin(a)),
                    (cx + r1 * math.cos(a), cy + r1 * math.sin(a))])
    return out


def frames(pattern=('L', 'R', 'L', 'R', 'B', 'L', 'R', 'B'),
           beat=30, hit=12, colour=WHITE):
    """Render the drum pattern. 'L'/'R' strike one paw, 'B' strikes both.

    `beat` is in FRAMES, and on this projector frames advance at the refresh
    rate -- which for a frame this cheap is ~70 Hz. Timing the drumming is
    therefore a matter of frame count, not of a frame-rate setting: at 30 frames
    a beat, eight beats run 3.4 s, about 139 BPM. Shorten it and the cat plays
    faster.
    """
    out = []
    for step in pattern:
        for f in range(beat):
            down = {'left': False, 'right': False}
            if f < hit:
                if step in ('L', 'B'): down['left'] = True
                if step in ('R', 'B'): down['right'] = True

            fb = FrameBuilder(max_step=1400, dwell_start=3, dwell_end=2,
                              dwell_blank=2)
            S = lambda pts: [(x * SCALE, (y + Y_SHIFT) * SCALE) for x, y in pts]

            fb.polyline(S([TABLE[0], TABLE[1]]), color=colour)
            fb.polyline(S(BODY), color=colour)
            for m in FACE:
                fb.polyline(S(m), color=colour)
            for name, pos in PAWS.items():
                cx, cy = pos['down' if down[name] else 'up']
                for st in _paw(cx, cy):
                    fb.polyline(S(st), color=colour)
                if down[name]:
                    for st in _impact(cx, cy):
                        fb.polyline(S(st), color=colour)
            out.append(fb.build())
    return out


if __name__ == '__main__':
    fr = frames()
    n = ilda.write('bongocat.ild', fr, name='BONGOCAT', company='CLAUDE',
                   last_flag=True)
    pts = [len(f) for f in fr]
    import make_demo as m
    print(f"bongocat.ild  {len(fr)} frames  {min(pts)}-{max(pts)} pts/frame  "
          f"{n} bytes  -> {m.refresh_hz(max(pts), 30):.1f} Hz at 30 kpps")
