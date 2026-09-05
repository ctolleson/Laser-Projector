"""
make_demo.py -- generate example .ild animations with ilda.FrameBuilder.

  python3 make_demo.py            # writes cube.ild, lissajous.ild, timing_test.ild
"""
import math
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


if __name__ == '__main__':
    for fn, nm in ((cube, 'cube'), (lissajous, 'lissajous'), (timing_test, 'timing_test')):
        fr = fn()
        n = ilda.write(f'{nm}.ild', fr, name=nm.upper()[:8], company='CLAUDE',
                       last_flag=True)
        pts = [len(x) for x in fr]
        print(f"{nm+'.ild':18s} {len(fr):3d} frames  "
              f"{min(pts)}-{max(pts)} pts/frame  {n} bytes")
