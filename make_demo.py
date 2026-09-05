"""
make_demo.py -- generate example .ild animations with ilda.FrameBuilder.

  python3 make_demo.py            # writes cube.ild, lissajous.ild, timing_test.ild
"""
import math
import random

import ilda
from ilda import FrameBuilder, Frame, RED, GREEN, CYAN, BLUE, MAGENTA, WHITE, YELLOW

R = 26000            # keep well inside +/-32767 so nothing clips


# ---------------------------------------------------------------- cube -------
CUBE_V = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
CUBE_E = [(0,1),(1,3),(3,2),(2,0), (4,5),(5,7),(7,6),(6,4), (0,4),(1,5),(2,6),(3,7)]

def cube(nframes=72, side=15000):
    frames = []
    for f in range(nframes):
        a = 2 * math.pi * f / nframes
        b = a * 0.6
        ca, sa, cb, sb = math.cos(a), math.sin(a), math.cos(b), math.sin(b)
        pv = []
        for x, y, z in CUBE_V:
            x, y, z = x * side, y * side, z * side
            x, z = x * ca - z * sa, x * sa + z * ca        # yaw
            y, z = y * cb - z * sb, y * sb + z * cb        # pitch
            d = 2.2 / (2.2 + z / side)                     # weak perspective
            pv.append((x * d, y * d, z))
        fb = FrameBuilder()
        for i, j in CUBE_E:
            fb.polyline([pv[i], pv[j]], color=CYAN)
        frames.append(fb.build())
    return frames


# ----------------------------------------------------------- lissajous -------
def lissajous(nframes=90, steps=180):
    frames = []
    for f in range(nframes):
        ph = 2 * math.pi * f / nframes
        pts = [(R * math.sin(3 * t + ph), R * math.sin(4 * t))
               for t in [2 * math.pi * i / steps for i in range(steps + 1)]]
        fb = FrameBuilder(max_step=1200)
        fb.polyline(pts, color=(MAGENTA if f % 2 else GREEN))
        frames.append(fb.build())
    return frames


# --------------------------------------------------------- timing test -------
def timing_test(nframes=60):
    """A hand that makes exactly ONE revolution over 60 frames.

    Time one full revolution on the projector to decode field 2 of Picture.prg:
      entry "timing_test.ild,10,1"
        revolution takes ~6 s  -> field 2 is FRAMES PER SECOND (60/10)
        revolution takes ~1 s and the clip runs ~10 s -> field 2 is SECONDS
    """
    frames = []
    for f in range(nframes):
        fb = FrameBuilder()
        # dial: 12 tick marks
        for k in range(12):
            t = 2 * math.pi * k / 12
            c, s = math.cos(t), math.sin(t)
            fb.polyline([(R * 0.80 * c, R * 0.80 * s), (R * c, R * s)],
                        color=(RED if k == 3 else BLUE))  # k==3 is 12 o'clock
        # hand, clockwise from 12 o'clock
        t = math.pi / 2 - 2 * math.pi * f / nframes
        fb.polyline([(0, 0), (R * 0.7 * math.cos(t), R * 0.7 * math.sin(t))],
                    color=WHITE)
        frames.append(fb.build())
    return frames


# ----------------------------------------------------------- starfield ------
def starfield(nframes=120, nstars=36, seed=3):
    """Warp-speed starfield: stars stream outward from the centre.

    Each star is a streak, not a dot -- a laser renders a dot as a stationary
    dwell, which is dim and wastes points, while a streak is what the scanner
    is good at and what reads as motion.

    Radius is driven directly off the star's phase rather than by projecting a
    literal 1/z depth. True perspective spends most of a star's life at small
    radius, which piles half the frame's points into a crowded blob around the
    centre -- accurate, but a poor trade when the whole frame is ~900 points.
    A mild power curve keeps the outward acceleration while spreading the
    stars evenly across the field.

    Both distributions are stratified rather than random: phases are spaced
    1/nstars apart (with jitter) so the radial spread stays even, and angles
    step by the golden angle so the field never clumps to one side. The pairing
    between them is then shuffled -- without that the two sequences correlate
    and the field collapses into a phyllotaxis rosette.

    Seamless by construction: phase wraps 1 -> 0, moving a star from the edge
    (where it is leaving the frame) to the centre, so the projector's repeat
    count produces no visible jump.

    `nstars` is the point-budget dial: each star costs ~26 points, and
    points/frame x fps must stay under the projector's point rate. 36 stars is
    ~960 points, i.e. ~19 kpps at 20 fps -- safe on a 20 kpps head. Raise it if
    yours scans faster.
    """
    rnd = random.Random(seed)
    GOLDEN = math.pi * (3 - math.sqrt(5))          # ~137.5 deg
    MIN_R = R * 0.10                               # innermost visible radius
    MIN_STREAK = 900                               # shortest visible streak
    TRAIL = 2.5                                    # streak length, in frames
    CURVE = 1.25                                   # >1 = accelerate outward

    # Stratify both, then shuffle to break the correlation between them.
    # Deriving angle and phase from the same index makes every star's radius a
    # function of its angle, which draws a phyllotaxis rosette -- pretty, but
    # plainly not a starfield.
    angles = [i * GOLDEN for i in range(nstars)]
    phases = [(i + rnd.random()) / nstars for i in range(nstars)]
    rnd.shuffle(phases)
    stars = list(zip(angles, phases))

    def radius(u):
        return MIN_R + (R - MIN_R) * (u ** CURVE)

    frames = []
    for f in range(nframes):
        t = f / nframes
        fb = FrameBuilder(max_step=1400)
        drawn = []
        for ang, phase in stars:
            u = (phase + t) % 1.0
            r = radius(u)
            r_tail = radius(max(0.0, u - TRAIL / nframes))
            r_tail = min(r_tail, r - MIN_STREAK)   # keep every star a line
            if r_tail < MIN_R * 0.5:
                continue                            # just respawned at centre
            c, s = math.cos(ang), math.sin(ang)
            colour = WHITE if u > 0.66 else (CYAN if u > 0.33 else BLUE)
            drawn.append((ang, (r_tail * c, r_tail * s), (r * c, r * s), colour))

        # Sweep the beam around by angle so it never crosses the frame between
        # neighbouring stars -- this is what keeps the blanked travel cheap.
        drawn.sort()
        for _, tail, head, colour in drawn:
            fb.polyline([tail, head], color=colour)
        frames.append(fb.build())
    return frames


if __name__ == '__main__':
    for fn, nm in ((cube, 'cube'), (lissajous, 'lissajous'),
                   (starfield, 'starfield'), (timing_test, 'timing_test')):
        fr = fn()
        n = ilda.write(f'{nm}.ild', fr, name=nm.upper()[:8], company='CLAUDE',
                       last_flag=True)
        pts = [len(x) for x in fr]
        print(f"{nm+'.ild':18s} {len(fr):3d} frames  "
              f"{min(pts)}-{max(pts)} pts/frame  {n} bytes")
