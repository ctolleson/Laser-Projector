"""
make_demo.py -- generate example .ild animations with ilda.FrameBuilder.

  python3 make_demo.py            # writes cube.ild, lissajous.ild, timing_test.ild
"""
import math
import random

import ilda
import strokefont as sf
from ilda import FrameBuilder, Frame, RED, GREEN, CYAN, BLUE, MAGENTA, WHITE, YELLOW

# --- measured projector profile ----------------------------------------------
# Field 2 of a playlist line is the SCAN RATE IN KPPS. Proven by listing one
# 500-point clock six times at 8/12/16/20/24/30: refresh ran 14.2 -> 47.4 Hz,
# where an ignored field would have pinned all six at 26.2 Hz.
#
#   frame_time = OVERHEAD + points / (SCAN_EFFICIENCY * kpps * 1000)
#
# fits those six within 3.5%. The head delivers ~92% of what it is asked for and
# was still scaling at 30 -- it is NOT a 15 kpps projector. Earlier work here
# measured "15 kpps" only because every playlist line happened to say 15.
SCAN_EFFICIENCY = 0.917   # delivered points/sec per requested kpps
OVERHEAD = 0.00226        # sec of fixed cost per frame
SCAN_KPPS = 30            # what sync'd playlists request (field 2)
POINT_RATE = SCAN_EFFICIENCY * SCAN_KPPS * 1000
BUDGET = 1000             # points/frame -> ~26 Hz at 30 kpps


def refresh_hz(points, kpps=None):
    """Refresh this projector achieves for a frame, at a given field-2 value."""
    k = SCAN_KPPS if kpps is None else kpps
    return 1.0 / (OVERHEAD + points / (SCAN_EFFICIENCY * k * 1000.0))


R = 26000            # keep well inside +/-32767 so nothing clips
TEXT_W = 46000       # target width of the widest text line
FOCAL = 62000        # perspective distance for Y-axis rotation


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
def timing_test(nframes=60, ticks=12, label=None):
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
        for k in range(ticks):
            t = 2 * math.pi * k / ticks
            c, s = math.cos(t), math.sin(t)
            fb.polyline([(R * 0.80 * c, R * 0.80 * s), (R * c, R * s)],
                        color=(RED if k == ticks // 4 else BLUE))  # index at 12 o'clock
        # hand, clockwise from 12 o'clock
        t = math.pi / 2 - 2 * math.pi * f / nframes
        fb.polyline([(0, 0), (R * 0.7 * math.cos(t), R * 0.7 * math.sin(t))],
                    color=WHITE)
        if label:
            # Ladder steps draw the same clock, so stamp an index -- otherwise
            # you cannot tell which file is on the wall while timing it.
            u = R * 0.09
            for s in sf.strokes(label):
                fb.polyline([(x * u - R * 0.92, y * u - R * 0.92)
                             for x, y in s], color=RED)
        frames.append(fb.build())
    return frames


# ----------------------------------------------------------- starfield ------
def starfield(nframes=120, nstars=40, seed=3):
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

    `nstars` is the point-budget dial: each star costs ~26 points. At 40 stars
    a frame is ~1050 points, which refreshes at ~25 Hz once the playlist asks
    for 30 kpps. Halve it if you drop SCAN_KPPS back to 15.
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
            # Two tiers, not three: this head renders cyan and blue almost
            # identically (its green is too dim for cyan to read as cyan), so a
            # white/cyan/blue depth ramp collapses to white/blue/blue on the
            # wall. White vs blue is the only pair that actually separates.
            colour = WHITE if u > 0.5 else BLUE
            drawn.append((ang, (r_tail * c, r_tail * s), (r * c, r * s), colour))

        # Sweep the beam around by angle so it never crosses the frame between
        # neighbouring stars -- this is what keeps the blanked travel cheap.
        drawn.sort()
        for _, tail, head, colour in drawn:
            fb.polyline([tail, head], color=colour)
        frames.append(fb.build())
    return frames


# ---------------------------------------------------------- text reveal -----
def text_reveal(lines=('PRODUCT', 'SECURITY', 'GUILD'), nframes=148,
                colour=GREEN, hold=54, spin_in=32, stagger=13, spin_out=30,
                tail_beat=4):
    """Three stacked lines that rotate in about the vertical axis, hold, exit.

    Rotation is about Y, so a line at 90 degrees is edge-on and collapses to a
    vertical bar -- which on a laser is not "invisible" but a bright vertical
    streak, every point in the line stacked on one column. Lines are therefore
    skipped entirely while near edge-on, which also hands their point budget
    back to the lines that are actually readable.

    That skip is what makes the loop seamless: the exit ends past edge-on and
    the entry starts past edge-on, so nothing is drawn across the wrap.

    Drawn in GREEN because it is one of the few indices this projector renders
    truly (see ilda.SUPPORTED). Any of ilda.SUPPORTED works; white comes out
    pale magenta here, not white.
    """
    text = [t.upper() for t in lines]
    unit = TEXT_W / max(sf.line_width(t) for t in text)   # one scale for all
    gap = unit * 9.5                                       # baseline spacing
    y0 = gap * (len(text) - 1) / 2.0

    def placed(i, t):
        """Glyph strokes for line i, centred, in projector units."""
        w = sf.line_width(t) * unit
        oy = y0 - i * gap - unit * sf.CAP / 2.0
        return [[(x * unit - w / 2.0, y * unit + oy) for x, y in s]
                for s in sf.strokes(t)]

    geom = [placed(i, t) for i, t in enumerate(text)]

    def ease(u):                       # ease-out cubic: fast in, settles gently
        return 1 - (1 - u) ** 3

    def angle(i, f):
        """This line's rotation in radians: 90 deg = edge-on, 0 = facing."""
        start = i * stagger
        if f < start:
            return math.pi / 2
        if f < start + spin_in:
            return math.pi / 2 * (1 - ease((f - start) / spin_in))
        out = stagger * (len(text) - 1) + spin_in + hold
        if f < out:
            return 0.0
        if f < out + spin_out:
            return -math.pi / 2 * ease((f - out) / spin_out)
        return -math.pi / 2

    frames = []
    for f in range(nframes):
        fb = FrameBuilder(max_step=1700, dwell_start=3, dwell_end=2,
                          dwell_blank=2)
        for i, strokes in enumerate(geom):
            a = angle(i, f)
            ca, sa = math.cos(a), math.sin(a)
            if abs(ca) < 0.12:
                continue               # edge-on: a bright bar, not a word
            for s in strokes:
                proj = []
                for x, y in s:
                    z = x * sa
                    k = FOCAL / (FOCAL + z)          # weak perspective
                    proj.append((x * ca * k, y * k, z))
                fb.polyline(proj, color=colour)
        if not fb.pts:                 # every line edge-on: park the beam
            fb.move_to(0, 0)
        frames.append(fb.build())

    # The edge-on skip means the reveal starts and ends with frames that draw
    # nothing. Trailing blanks are dead air on a projector that loops, so keep
    # only a short beat between repeats.
    def draws(fr):
        return any(not (p[3] & ilda.BLANK) for p in fr.points)

    first = next(i for i, fr in enumerate(frames) if draws(fr))
    last = max(i for i, fr in enumerate(frames) if draws(fr))
    return frames[first:last + 1 + tail_beat]


# ------------------------------------------------- point-rate measurement ----
def pad_to(frame, n):
    """Pad a frame to exactly n points with blanked dwells at the parked spot.

    Blanked points cost the scanner exactly as much time as lit ones -- the
    beam still has to travel. So padding raises a frame's scan cost without
    changing a pixel of what you see, which is what lets a ladder of files
    isolate the projector's point rate from everything else.
    """
    pts = list(frame.points)
    if n < len(pts):
        raise ValueError(f"frame already has {len(pts)} points, cannot pad to {n}")
    x, y, z, s, c = pts[-1]
    pts[-1] = (x, y, z, s & ~ilda.LAST, c)              # demote the old last
    pts += [(x, y, z, ilda.BLANK, 0)] * (n - len(pts) - 1)
    pts.append((x, y, z, ilda.BLANK | ilda.LAST, 0))
    return ilda.Frame(pts, frame.name, frame.company)


def pointrate_ladder(counts=(300, 400, 500, 650, 900)):
    """Clock-hand files at increasing points/frame, for finding the point rate.

    The first sweep (400..6400) established the shape: this head is point-limited
    across the whole range, with no flat region, at roughly 16 kpps. These counts
    bracket the usable working range instead, to pin POINT_RATE and OVERHEAD
    down where frames are actually authored. Heavy steps also measure badly --
    at 6400 points the lit burst is such a small share of the frame that a
    camera rarely catches it.

    Each file is the same one-revolution-per-60-frames clock, padded to a
    different point count. Time one revolution of each: while the projector has
    headroom the revolution time stays flat, and once points/frame x fps exceeds
    its point rate the time grows in proportion. The knee is the answer:

        points per second ~= points_per_frame x 60 / revolution_seconds

    measured on any file past the knee.
    """
    # A lean base (4 ticks, ~200 points) so the ladder can start below the
    # knee of a slow projector; padding supplies the rest.
    out = {}
    for idx, n in enumerate(sorted(counts), start=1):
        base = timing_test(ticks=4, label=str(idx))
        out[n] = [pad_to(f, n) for f in base]
    return out


# ------------------------------------------------------- palette chart ------
def palette_chart(per_group=8, hold=40):
    """Swatches for all 64 palette indices, labelled, 8 at a time.

    The ILDA standard palette says index 56 is white and 40 is blue. On this
    projector 56 comes out magenta and 40 comes out purple, while 0 (red) and
    31 (cyan) look correct -- so its table is NOT the standard one, and colours
    picked from the spec will not be the colours on the wall.

    Film this, read off what each numbered bar actually looks like, and the
    result is the projector's real palette. Then author against that.
    """
    frames = []
    for g in range(64 // per_group):
        base = g * per_group
        made = []
        for row in range(per_group):
            idx = base + row
            y = R * 0.72 - row * (R * 1.5 / per_group)
            fb_strokes = []
            # the swatch: a bold bar drawn in the index under test
            fb_strokes.append(([(-R * 0.30, y), (R * 0.62, y)], idx))
            # its number, drawn in a colour we already trust (red reads true).
            # Glyph height is 7u and must clear the row pitch, or the labels
            # collide and the chart is unreadable.
            u = (R * 1.5 / per_group) / 7.0 * 0.68
            for s in sf.strokes(f"{idx:02d}"):
                fb_strokes.append(([(x * u - R * 0.86, y + (yy - 3.5) * u)
                                    for x, yy in s], RED))
            made.append(fb_strokes)
        for _ in range(hold):
            fb = FrameBuilder(max_step=2600, dwell_start=3, dwell_end=2,
                              dwell_blank=2)
            for row in made:
                for pts, col in row:
                    fb.polyline(pts, color=col)
            frames.append(fb.build())
    return frames


# ------------------------------------------------------- full text show -----
def _place(lines, unit=None):
    """Glyph strokes for stacked, centred lines, in projector units."""
    text = [t.upper() for t in lines]
    unit = unit or TEXT_W / max(sf.line_width(t) for t in text)
    gap = unit * 9.5
    y0 = gap * (len(text) - 1) / 2.0
    out = []
    for i, t in enumerate(text):
        w = sf.line_width(t) * unit
        oy = y0 - i * gap - unit * sf.CAP / 2.0
        out.append([[(x * unit - w / 2.0, y * unit + oy) for x, y in s]
                    for s in sf.strokes(t)])
    return out


def _persp(x, y, z):
    k = FOCAL / (FOCAL + z)
    return (x * k, y * k, z)


# Each effect maps a line's 2D stroke to 3D for progress u in 0..1.
# `li` is the line index, so effects can stagger down the block.

def _fx_hold(pts, li, u):
    return [(x, y, 0) for x, y in pts]


def _fx_wave(pts, li, u, amp=2400, wavelen=26000.0, cycles=2.5):
    k = 2 * math.pi / wavelen
    ph = 2 * math.pi * u * cycles - li * 0.8
    return [(x, y + amp * math.sin(x * k + ph), 0) for x, y in pts]


def _fx_breathe(pts, li, u, cycles=2, a=0.17):
    s = 1.0 + a * math.sin(2 * math.pi * u * cycles)
    return [(x * s, y * s, 0) for x, y in pts]


def _fx_spin_z(pts, li, u):
    a = 2 * math.pi * u
    c, s = math.cos(a), math.sin(a)
    return [(x * c - y * s, x * s + y * c, 0) for x, y in pts]


# Near edge-on a rotated line collapses to a single column (or row) -- on a
# laser that is not "thin", it is every point of the line stacked into one
# bright bar. These return None so the renderer drops the line entirely.
# The test has to be on the ROTATION ANGLE, not on the resulting geometry:
# a collapsed line and a legitimately vertical stroke (the stem of an I or L)
# look identical once projected.
EDGE_ON = 0.12


def _fx_spin_y(pts, li, u, turns=1):
    a = 2 * math.pi * u * turns - li * 0.55      # stagger: never all edge-on
    ca, sa = math.cos(a), math.sin(a)
    if abs(ca) < EDGE_ON:
        return None
    return [_persp(x * ca, y, x * sa) for x, y in pts]


def _fx_flip_x(pts, li, u, turns=1):
    a = 2 * math.pi * u * turns - li * 0.55
    ca, sa = math.cos(a), math.sin(a)
    if abs(ca) < EDGE_ON:
        return None
    return [_persp(x, y * ca, y * sa) for x, y in pts]


def _fx_enter(pts, li, u):
    """Swing in from edge-on, eased, staggered per line."""
    p = min(1.0, max(0.0, u * 3.0 - li * 0.62))
    a = math.pi / 2 * (1 - (1 - p) ** 3)
    ca, sa = math.cos(a), math.sin(a)
    if abs(ca) < EDGE_ON:
        return None
    return [_persp(x * ca, y, x * sa) for x, y in pts]


def _fx_exit(pts, li, u):
    p = min(1.0, max(0.0, u * 3.0 - (2 - li) * 0.62))
    a = -math.pi / 2 * (1 - (1 - p) ** 3)
    ca, sa = math.cos(a), math.sin(a)
    if abs(ca) < EDGE_ON:
        return None
    return [_persp(x * ca, y, x * sa) for x, y in pts]


def _write_on(geom, u):
    """Reveal strokes in drawing order, cutting the last one mid-path."""
    total = 0.0
    lens = []
    for line in geom:
        for s in line:
            L = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(s, s[1:]))
            lens.append(L); total += L
    want = total * u
    out = [[] for _ in geom]
    k = 0
    for li, line in enumerate(geom):
        for s in line:
            L = lens[k]; k += 1
            if want <= 0:
                continue
            if want >= L:
                out[li].append(s); want -= L
                continue
            # partial stroke: walk the path until the budget runs out
            acc = 0.0; part = [s[0]]
            for a, b in zip(s, s[1:]):
                seg = math.hypot(b[0] - a[0], b[1] - a[1])
                if acc + seg <= want:
                    part.append(b); acc += seg
                else:
                    f = (want - acc) / seg if seg else 0
                    part.append((a[0] + (b[0] - a[0]) * f,
                                 a[1] + (b[1] - a[1]) * f))
                    break
            if len(part) > 1:
                out[li].append(part)
            want = 0
    return out


def text_show(lines=('PRODUCT', 'SECURITY', 'GUILD'), colour=MAGENTA):
    """A longer show: the text written on, then put through several effects.

    Drawn in MAGENTA (index 48), one of the seven colours this projector
    reproduces truly -- and the only saturated one that is neither a primary
    nor washed out by its dim green.

    Effects are stroke transforms, so none of them add points: the frame stays
    at the same ~635-point cost throughout, and the refresh stays near 22 Hz.
    The wave displaces whole glyphs rather than rippling within them, which is
    what keeps it free -- bending a letter would need the strokes subdivided,
    and every extra vertex is scan time this projector does not have.
    """
    geom = _place(lines)

    # (effect, frames). Starts from nothing and ends at nothing, so it loops.
    plan = [
        ('write', 74), ('hold', 20),
        ('wave', 104), ('hold', 12),
        ('breathe', 68),
        ('spin_y', 92), ('hold', 12),
        ('flip_x', 88), ('hold', 12),
        ('spin_z', 84), ('hold', 20),
        ('exit', 44),
    ]
    fx = {'hold': _fx_hold, 'wave': _fx_wave, 'breathe': _fx_breathe,
          'spin_z': _fx_spin_z, 'spin_y': _fx_spin_y, 'flip_x': _fx_flip_x,
          'exit': _fx_exit}

    frames = []
    for name, n in plan:
        for f in range(n):
            u = f / n
            fb = FrameBuilder(max_step=1700, dwell_start=3, dwell_end=2,
                              dwell_blank=2)
            src = _write_on(geom, u) if name == 'write' else geom
            xf = _fx_hold if name == 'write' else fx[name]
            for li, line in enumerate(src):
                for s in line:
                    p3 = xf(s, li, u)
                    if p3 is None:
                        continue                  # edge-on: would be a bar
                    fb.polyline(p3, color=colour)
            if not fb.pts:
                fb.move_to(0, 0)
            frames.append(fb.build())

    # The exit ends past edge-on, so the tail draws nothing. Keep a short beat
    # between repeats and drop the rest.
    def draws(fr):
        return any(not (p[3] & ilda.BLANK) for p in fr.points)

    last = max(i for i, fr in enumerate(frames) if draws(fr))
    return frames[:last + 5]


# ---------------------------------------------------------- raccoon ---------
def _ellipse(cx, cy, rx, ry, n, rot=0.0):
    c, s = math.cos(rot), math.sin(rot)
    out = []
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        out.append((cx + x * c - y * s, cy + x * s + y * c))
    return out


def _arc_pts(cx, cy, rx, ry, a0, a1, n):
    return [(cx + rx * math.cos(math.radians(a)), cy + ry * math.sin(math.radians(a)))
            for a in (a0 + (a1 - a0) * i / n for i in range(n + 1))]


def _raccoon_strokes():
    """A raccoon face as (stroke, z) pairs, drawn in a -100..100 box.

    Two things separate a raccoon from a cat, and both matter more than detail:
    the ears are small and ROUND (pointed triangles read as feline instantly),
    and the bandit mask is a single band that bridges across the nose rather
    than two separate eye rings.

    Features carry real depth. Under Y-axis rotation a flat drawing collapses
    to one bright column at 90 degrees; a forward-set muzzle and nose turn that
    into a readable profile instead, so the spin never blanks.
    """
    S = []
    S.append((_ellipse(0, 4, 58, 46, 20), 0))                     # head
    for sgn in (-1, 1):
        # Ear bases sit ON the head outline (the ellipse passes through y=40
        # at x=36); any higher and they read as detached horns.
        S.append((_arc_pts(sgn * 36, 40, 19, 19, 175, 5, 9), -7))   # ear, round
        S.append((_arc_pts(sgn * 36, 41, 10, 10, 172, 8, 6), -5))   # inner ear

    # The mask: one band across both eyes, dipping at the bridge of the nose.
    mask = [(-53, 16), (-48, 27), (-33, 33), (-16, 30), (-6, 22),
            (0, 17), (6, 22), (16, 30), (33, 33), (48, 27), (53, 16),
            (49, 5), (34, -3), (17, 0), (6, 6), (0, 8), (-6, 6),
            (-17, 0), (-34, -3), (-49, 5), (-53, 16)]
    S.append((mask, 6))
    for sgn in (-1, 1):
        S.append((_ellipse(sgn * 27, 15, 7.5, 7.5, 8), 9))         # eye

    S.append((_ellipse(0, -26, 25, 17, 14), 12))                   # muzzle
    S.append(([(-8, -13), (8, -13), (0, -23), (-8, -13)], 18))     # nose
    S.append(([(0, -23), (0, -31)], 15))                           # philtrum
    S.append(([(-13, -38), (-6, -31), (0, -31), (6, -31), (13, -38)], 14))
    S.append(([(0, 50), (0, 32)], 2))                              # brow stripe
    for sgn in (-1, 1):
        S.append(([(sgn * 52, 8), (sgn * 66, 13)], 4))             # cheek fur
        S.append(([(sgn * 55, -4), (sgn * 70, -4)], 4))
        S.append(([(sgn * 21, -24), (sgn * 50, -20)], 10))         # whiskers
        S.append(([(sgn * 21, -30), (sgn * 52, -33)], 10))

    # Shift the face left to make room, then add the ringed tail -- the single
    # most identifiable raccoon feature, and affordable now that the playlist
    # asks for 30 kpps instead of 15.
    S = [([(x - 26, y + 6) for x, y in st], z) for st, z in S]

    def tail_pt(t, off):
        # Base sits clear of the head (its outline reaches x=32 after the
        # shift, cheek fur to x=44), so the tail sweeps out from behind rather
        # than across the face.
        cx = 38 + 62 * t
        cy = -50 + 52 * t + 28 * math.sin(math.pi * t)
        # outward normal of the centreline, for the tapering width
        dx, dy = 62.0, 52 + 28 * math.pi * math.cos(math.pi * t)
        L = math.hypot(dx, dy)
        w = 25 * (1 - 0.42 * t)
        return (cx - dy / L * off * w, cy + dx / L * off * w)

    n = 12
    upper = [tail_pt(i / n, 0.5) for i in range(n + 1)]
    lower = [tail_pt(i / n, -0.5) for i in range(n + 1)]
    S.append((upper + lower[::-1] + [upper[0]], -12))          # tail outline
    for t in (0.24, 0.44, 0.64, 0.84):                          # rings
        S.append(([tail_pt(t, 0.5), tail_pt(t, -0.5)], -11))
    return S


def raccoon(nframes=210, scale=182.0):
    """A raccoon spinning about the vertical axis, cycling through colours.

    Colour steps through ilda.SUPPORTED -- the seven indices this projector
    actually reproduces. Cycling the full 64 would spend most of the loop on
    gradient entries that all render as the same white.

    nframes is 7 colours x 30 frames and exactly one revolution, so colour and
    rotation both land together and the loop is seamless.
    """
    strokes = _raccoon_strokes()
    per_colour = nframes // len(ilda.SUPPORTED)
    frames = []
    for f in range(nframes):
        a = 2 * math.pi * f / nframes
        ca, sa = math.cos(a), math.sin(a)
        colour = ilda.SUPPORTED[(f // per_colour) % len(ilda.SUPPORTED)]
        fb = FrameBuilder(max_step=1500, dwell_start=3, dwell_end=2,
                          dwell_blank=2)
        for pts, z0 in strokes:
            p3 = []
            for x, y in pts:
                x3, z3 = x * scale, z0 * scale
                xr = x3 * ca + z3 * sa
                zr = -x3 * sa + z3 * ca
                k = FOCAL / (FOCAL + zr * 0.55)
                p3.append((xr * k, y * scale * k, zr))
            fb.polyline(p3, color=colour)
        frames.append(fb.build())
    return frames


# --------------------------------------------- playlist field 2 experiment ---
def kpps_test(values=(8, 12, 16, 20, 24, 30), points=500):
    """Identical clocks stamped with, and listed under, different field-2 values.

    Field 3 of a playlist line is now confirmed to be a repeat count. Field 2 is
    still open -- but it is NOT frames per second: every entry in the last test
    said 15 while the projector ran psg at 20.9 Hz and rate300 at 39.9 Hz, both
    exactly as its point rate predicts. It ignored the number completely as a
    frame rate.

    The live hypothesis is that field 2 sets the SCAN RATE in kpps. The measured
    point rate came out at 15,040 pts/sec against a playlist that said 15 -- a
    0.3% match that is hard to read as coincidence. The original factory
    Picture.prg used 8/10/15/18/20, all plausible kpps ratings, and Picture.bac
    listed one file four times at different values, which looks exactly like
    somebody sweeping this setting.

    Every file here is the same clock padded to the same point count, so scan
    rate is the only variable. Each is stamped with the value its playlist line
    carries. If the hypothesis holds, refresh should track field 2:

        8 -> 14.7 Hz   12 -> 21.3 Hz   16 -> 27.4 Hz
       20 -> 33.5 Hz   24 -> 39.0 Hz   30 -> 45.6 Hz

    If field 2 is ignored instead, all six run at the same ~26.6 Hz.
    """
    out = {}
    for v in values:
        base = timing_test(ticks=4, label=str(v))
        out[v] = [pad_to(f, points) for f in base]
    return out


if __name__ == '__main__':
    for fn, nm in ((cube, 'cube'), (lissajous, 'lissajous'),
                   (starfield, 'starfield'), (text_show, 'psg'),
                   (palette_chart, 'palette'), (raccoon, 'raccoon'),
                   (timing_test, 'timing_test')):
        fr = fn()
        n = ilda.write(f'{nm}.ild', fr, name=nm.upper()[:8], company='CLAUDE',
                       last_flag=True)
        pts = [len(x) for x in fr]
        print(f"{nm+'.ild':18s} {len(fr):3d} frames  "
              f"{min(pts)}-{max(pts)} pts/frame  {n} bytes")

    print()
    for v, fr in sorted(kpps_test().items()):
        nm = f'k{v:02d}'
        ilda.write(f'{nm}.ild', fr, name=nm.upper()[:8], company='CLAUDE',
                   last_flag=True)
        print(f"{nm+'.ild':18s} {len(fr):3d} frames  {len(fr[0])} pts/frame  "
              f"(list as {nm}.ild,{v},2)")

    print()
    for count, fr in sorted(pointrate_ladder().items()):
        nm = f'rate{count}'
        ilda.write(f'{nm}.ild', fr, name=nm.upper()[:8], company='CLAUDE',
                   last_flag=True)
        print(f"{nm+'.ild':18s} {len(fr):3d} frames  "
              f"{len(fr[0])} pts/frame  (ladder step)")
