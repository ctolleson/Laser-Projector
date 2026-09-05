"""
ilda.py -- read and write ILDA Image Data Transfer Format files (.ild),
matching the dialect used by the projector-files/ collection: Format 0
(3D, indexed colour), big-endian, 64-colour default palette.

Reverse-engineered from and verified byte-exact against all 20 .ild files
in projector-files/ (3525 frames, 2.24M points, zero trailing bytes).
"""
import struct

# --- ILDA default 64-colour palette -----------------------------------------
PALETTE = [
    (255,0,0),(255,16,0),(255,32,0),(255,48,0),(255,64,0),(255,80,0),
    (255,96,0),(255,112,0),(255,128,0),(255,144,0),(255,160,0),(255,176,0),
    (255,192,0),(255,208,0),(255,224,0),(255,240,0),(255,255,0),(224,255,0),
    (192,255,0),(160,255,0),(128,255,0),(96,255,0),(64,255,0),(32,255,0),
    (0,255,0),(0,255,36),(0,255,73),(0,255,109),(0,255,146),(0,255,182),
    (0,255,219),(0,255,255),(0,227,255),(0,199,255),(0,170,255),(0,142,255),
    (0,113,255),(0,85,255),(0,56,255),(0,28,255),(0,0,255),(32,0,255),
    (64,0,255),(96,0,255),(128,0,255),(160,0,255),(192,0,255),(224,0,255),
    (255,0,255),(255,32,255),(255,64,255),(255,96,255),(255,128,255),
    (255,160,255),(255,192,255),(255,224,255),(255,255,255),(255,224,224),
    (255,192,192),(255,160,160),(255,128,128),(255,96,96),(255,64,64),(255,32,32),
]
RED, ORANGE, YELLOW, GREEN, CYAN, BLUE, MAGENTA, WHITE = 0, 8, 16, 24, 31, 40, 48, 56

# --- what this projector actually reproduces ------------------------------
# Measured off a filmed palette chart (all 64 indices, IMG_4650.MOV).
#
# The head resolves only the seven saturated corners of the RGB cube. EVERY
# other index -- all 57 gradient entries -- renders identically, as white. So
# the palette's careful red->orange->yellow ramp does not exist here: indices
# 1..15 are not shades of orange, they are all just white.
#
# Its green is also dim next to red and blue, which is why white reads as pale
# magenta and cyan reads as blue-violet. Those two are still distinguishable
# from each other, but neither looks like its name.
#
#   index  standard        measured RGB      appearance
#   0      red             [161, 62,  69]    red
#   16     yellow          [149, 96,  68]    yellow
#   24     green           [ 85,129,  57]    green
#   31     cyan            [ 79, 82, 170]    blue-violet (green too dim)
#   40     blue            [ 65, 47, 161]    blue
#   48     magenta         [119, 54, 141]    magenta
#   56     white           [130, 72, 141]    pale magenta (green too dim)
#   other  (gradients)     [131, 73, 141]    white -- identical to 56
#
# ORANGE (8) is NOT in that set: it is a gradient entry and comes out white.
SUPPORTED = (0, 16, 24, 31, 40, 48, 56)

SUPPORTED_NAMES = {
    0: 'red', 16: 'yellow', 24: 'green', 31: 'cyan (reads blue-violet)',
    40: 'blue', 48: 'magenta', 56: 'white (reads pale magenta)',
}


def is_supported(index):
    """True if this projector reproduces `index` as a distinct colour."""
    return (index & 63) in SUPPORTED


def unsupported_colors(frames):
    """Colour indices used by lit points that this projector renders as white."""
    bad = set()
    for fr in frames:
        for x, y, z, s, c in (fr.points if isinstance(fr, Frame) else fr):
            if not (s & BLANK) and not is_supported(c):
                bad.add(c & 63)
    return sorted(bad)

# --- status byte bits --------------------------------------------------------
BLANK = 0x40    # bit 6: laser off while moving to this point
LAST  = 0x80    # bit 7: final point of the frame

RECORD_SIZE = {0: 8, 1: 6, 2: 3, 4: 10, 5: 8}
FULL = 32767    # coordinate extent; usable range is -32768..32767


class Frame:
    """One frame: a list of (x, y, z, status, colour_index) tuples.

    `name` and `company` are the frame's own 8-byte header fields.  Real files
    vary these per frame -- authoring tools often number them ("EARTH1.DE3",
    "EARTH2.DE3") -- so they are stored unstripped to survive a round trip.
    """
    def __init__(self, points=None, name="", company=""):
        self.points = list(points or [])
        self.name = name
        self.company = company

    def __len__(self):
        return len(self.points)

    def __iter__(self):
        return iter(self.points)

    def bounds(self):
        xs = [p[0] for p in self.points]; ys = [p[1] for p in self.points]
        return (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, 0, 0)


class Show(list):
    """A list of Frames plus the trailing EOF header's own fields."""
    eof_name = "        "
    eof_company = "        "
    eof_frame_number = 0


def _field(b):
    return b.decode('latin1')


def _pad(s):
    return s.encode('latin1', 'replace')[:8].ljust(8, b' ')


def read(path):
    """Parse an .ild file into a Show (list of Frame). Raises on bad input."""
    data = open(path, 'rb').read()
    show, off = Show(), 0
    while off + 32 <= len(data):
        h = data[off:off + 32]
        if h[0:4] != b'ILDA':
            raise ValueError(f"{path}: bad magic at offset {off}: {h[:4]!r}")
        fmt = h[7]
        if fmt not in RECORD_SIZE:
            raise ValueError(f"{path}: unsupported format code {fmt} at {off}")
        n, fnum, total, head, _res = struct.unpack('>HHHBB', h[24:32])
        if n == 0:                       # EOF sentinel: a header with 0 records
            show.eof_name = _field(h[8:16])
            show.eof_company = _field(h[16:24])
            show.eof_frame_number = fnum
            return show
        if fmt != 0:
            raise NotImplementedError(
                f"{path}: only format 0 is implemented (found format {fmt})")
        base = off + 32
        pts = [struct.unpack_from('>hhhBB', data, base + i * 8) for i in range(n)]
        show.append(Frame(pts, _field(h[8:16]), _field(h[16:24])))
        off = base + n * 8
    raise ValueError(f"{path}: ran out of data without an EOF header")


def write(path, frames, name=None, company=None, last_flag='auto',
          eof_name=None, eof_company=None, eof_frame_number=None):
    """Write frames as a Format 0 .ild file terminated by an EOF header.

    name/company     override every frame's header fields (default: keep each
                     frame's own, or blank for raw point lists).
    last_flag        'auto' keeps whatever bit 7 the points already carry;
                     True forces it on the final point of each frame (what most
                     authoring tools do); False clears it everywhere.
    eof_*            fields for the trailing EOF header.
    """
    src = frames if isinstance(frames, Show) else None
    out = bytearray()
    total = len(frames)
    for i, fr in enumerate(frames):
        pts = list(fr.points) if isinstance(fr, Frame) else list(fr)
        if not pts:
            raise ValueError(f"frame {i} is empty; a 0-record header ends the file")
        if len(pts) > 65535:
            raise ValueError(f"frame {i} has {len(pts)} points (max 65535)")
        if last_flag is True:
            pts = [(x, y, z, (s | LAST) if j == len(pts) - 1 else (s & ~LAST), c)
                   for j, (x, y, z, s, c) in enumerate(pts)]
        elif last_flag is False:
            pts = [(x, y, z, s & ~LAST, c) for x, y, z, s, c in pts]
        fn = name if name is not None else getattr(fr, 'name', '')
        fc = company if company is not None else getattr(fr, 'company', '')
        out += b'ILDA' + b'\x00\x00\x00\x00' + _pad(fn) + _pad(fc)
        out += struct.pack('>HHHBB', len(pts), i, total, 0, 0)
        for x, y, z, s, c in pts:
            out += struct.pack('>hhhBB', _clamp(x), _clamp(y), _clamp(z), s, c & 63)
    en = eof_name if eof_name is not None else (src.eof_name if src else '')
    ec = eof_company if eof_company is not None else (src.eof_company if src else '')
    ef = eof_frame_number if eof_frame_number is not None else \
         (src.eof_frame_number if src else 0)
    out += b'ILDA' + b'\x00\x00\x00\x00' + _pad(en) + _pad(ec)
    out += struct.pack('>HHHBB', 0, ef, total, 0, 0)
    open(path, 'wb').write(bytes(out))
    return len(out)


def _clamp(v):
    return max(-32768, min(32767, int(round(v))))


# --- authoring helpers -------------------------------------------------------
# Defaults measured from the reference files: lit steps have a median of ~709
# and a 99th percentile of ~2285 units, and paths dwell on repeated points at
# path ends and after blanked jumps so the galvos can settle.

class FrameBuilder:
    """Builds a scanner-friendly frame from polylines.

    Inserts the blanked travel moves, interpolation and dwell points that real
    ILDA content uses -- without them a projector smears corners and draws
    faint tails between shapes.
    """
    def __init__(self, max_step=900, blank_step=3000,
                 dwell_start=6, dwell_end=4, dwell_blank=4, dwell_corner=0):
        self.pts = []
        self.max_step = max_step        # max distance between lit points
        self.blank_step = blank_step    # max distance between blanked points
        self.dwell_start = dwell_start  # repeats after switching the beam on
        self.dwell_end = dwell_end      # repeats before switching it off
        self.dwell_blank = dwell_blank  # repeats at each end of a blanked jump
        self.dwell_corner = dwell_corner
        self.cur = None

    def _emit(self, x, y, z, status, color, times=1):
        for _ in range(times):
            self.pts.append((_clamp(x), _clamp(y), _clamp(z), status, color & 63))
        self.cur = (x, y, z)

    def _interp(self, a, b, status, color, step):
        (x0, y0, z0), (x1, y1, z1) = a, b
        d = max(abs(x1 - x0), abs(y1 - y0), abs(z1 - z0))
        n = max(1, int(d / step + 0.999))
        for i in range(1, n + 1):
            t = i / n
            self._emit(x0 + (x1-x0)*t, y0 + (y1-y0)*t, z0 + (z1-z0)*t, status, color)

    def move_to(self, x, y, z=0):
        """Blanked travel to (x, y, z)."""
        if self.cur is None:
            self._emit(x, y, z, BLANK, 0, self.dwell_blank)
            return
        if self.cur == (x, y, z):
            return
        self._emit(*self.cur, BLANK, 0, self.dwell_blank)
        self._interp(self.cur, (x, y, z), BLANK, 0, self.blank_step)
        self._emit(x, y, z, BLANK, 0, self.dwell_blank)

    def polyline(self, verts, color=WHITE, closed=False):
        """Draw a lit path through verts -- (x,y) or (x,y,z) tuples."""
        v = [(p[0], p[1], p[2] if len(p) > 2 else 0) for p in verts]
        if len(v) < 2:
            return self
        if closed and v[0] != v[-1]:
            v.append(v[0])
        self.move_to(*v[0])
        self._emit(*v[0], 0, color, self.dwell_start)
        for a, b in zip(v, v[1:]):
            self._interp(a, b, 0, color, self.max_step)
            if self.dwell_corner:
                self._emit(*b, 0, color, self.dwell_corner)
        self._emit(*v[-1], 0, color, self.dwell_end)
        return self

    def build(self):
        """Finish the frame: park the beam blanked and set the last-point flag."""
        if not self.pts:
            raise ValueError("frame has no points")
        if not (self.pts[-1][3] & BLANK):
            x, y, z = self.cur
            self._emit(x, y, z, BLANK, 0, self.dwell_blank)
        p = self.pts[-1]
        self.pts[-1] = (p[0], p[1], p[2], p[3] | LAST, p[4])
        return Frame(self.pts)
