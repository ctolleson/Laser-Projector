"""
trace_bitmap.py -- turn 1-pixel-wide line art into polylines a laser can draw.

The bongo cat frames ship as ASCII bitmaps. Hand-copying them by eye loses the
shape (my first attempt drew the paws as free-floating circles, when in the
original they are the ends of the arms and part of the body silhouette). This
follows the actual pixels instead.

Pixels are 8-connected into a graph; paths are walked from endpoints first, so
open strokes come out whole, then any leftover cycles are picked up. Each path
is simplified with Douglas-Peucker, which is what keeps the point count low
enough to scan without changing the drawing.
"""


def parse_frames(path):
    """Read the `=== name ===` blocks of a frames.txt into {name: [rows]}."""
    out, name, rows = {}, None, []
    for line in open(path):
        line = line.rstrip('\n')
        if line.startswith('==='):
            if name: out[name] = rows
            name = line.strip('= ').split(' (')[0]
            rows = []
        elif name is not None:
            rows.append(line)
    if name: out[name] = rows
    return out


def pixels(rows):
    return {(x, y) for y, r in enumerate(rows) for x, c in enumerate(r) if c != ' '}


_N8 = [(-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1)]


def load_png(path, block=4):
    """Downsample the 4x-scaled PNG back to its native 1-pixel-per-cell grid."""
    from PIL import Image
    im = Image.open(path).convert('L')
    W, H = im.size
    px = im.load()
    # Sample the centre of each block, not "any sub-pixel set". The latter
    # fattens every stroke to two cells wide, and a 2-cell line traces as two
    # parallel paths -- which is what a doubled outline in the render means.
    out = set()
    c = block // 2
    for gy in range(H // block):
        for gx in range(W // block):
            if px[gx*block+c, gy*block+c] > 128:
                out.add((gx, gy))
    return out


def thin(px):
    """Zhang-Suen thinning: reduce strokes to one pixel wide.

    The source art draws many strokes two cells thick. Tracing that directly
    walks up one side and back down the other, which is why long lines came out
    as parallel fragments. Thinning first gives the tracer an actual centreline
    to follow.
    """
    px = set(px)
    # neighbours in Zhang-Suen order: N, NE, E, SE, S, SW, W, NW
    off = [(0,-1),(1,-1),(1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1)]

    def nb(p):
        return [1 if (p[0]+dx, p[1]+dy) in px else 0 for dx, dy in off]

    while True:
        removed = False
        for step in (0, 1):
            marked = []
            for p in px:
                n = nb(p)
                B = sum(n)
                if not (2 <= B <= 6):
                    continue
                A = sum(1 for i in range(8)
                        if n[i] == 0 and n[(i+1) % 8] == 1)
                if A != 1:
                    continue
                # n[0]=N n[2]=E n[4]=S n[6]=W
                if step == 0:
                    if n[0]*n[2]*n[4] or n[2]*n[4]*n[6]:
                        continue
                else:
                    if n[0]*n[2]*n[6] or n[0]*n[4]*n[6]:
                        continue
                marked.append(p)
            if marked:
                px -= set(marked)
                removed = True
        if not removed:
            break
    return px


def trace(px):
    """Walk the pixel set into polylines, consuming each pixel once.

    Edge-consumption does not work on 8-connected line art: a diagonal run has
    redundant shortcut edges between its own pixels, so walking edges shatters
    every line into two-pixel fragments. Consuming pixels, and at each step
    preferring the neighbour most in line with the current heading, follows the
    stroke the way it was drawn.
    """
    nbr = {p: [(p[0]+dx, p[1]+dy) for dx, dy in _N8
               if (p[0]+dx, p[1]+dy) in px] for p in px}
    unvisited = set(px)
    paths = []

    def grab(start):
        path = [start]
        unvisited.discard(start)
        cur, d = start, None
        while True:
            cand = [q for q in nbr[cur] if q in unvisited]
            if not cand:
                break
            if d is None:
                nxt = cand[0]
            else:
                def align(q):
                    v = (q[0]-cur[0], q[1]-cur[1])
                    L = (v[0]*v[0] + v[1]*v[1]) ** 0.5
                    return (d[0]*v[0] + d[1]*v[1]) / L
                nxt = max(cand, key=align)
            d = (nxt[0]-cur[0], nxt[1]-cur[1])
            path.append(nxt)
            unvisited.discard(nxt)
            cur = nxt
        return path

    # True endpoints first, so open strokes come out as single runs.
    ends = sorted([p for p in px if len(nbr[p]) == 1])
    for p in ends:
        if p in unvisited:
            paths.append(grab(p))
    while unvisited:
        paths.append(grab(min(unvisited)))
    # Keep single-pixel runs. The face marks are 1-2 cells and thin down to a
    # lone pixel; dropping them loses the cat's expression, which is most of
    # what makes it read as bongo cat at all. They become short dashes below.
    return paths


def _perp(p, a, b):
    (px_, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return ((px_-ax)**2 + (py-ay)**2) ** 0.5
    t = max(0.0, min(1.0, ((px_-ax)*dx + (py-ay)*dy) / (dx*dx + dy*dy)))
    return ((px_ - (ax+t*dx))**2 + (py - (ay+t*dy))**2) ** 0.5


def simplify(path, eps=0.9):
    """Douglas-Peucker: drop vertices that do not change the drawn shape."""
    if len(path) < 3:
        return path
    worst, idx = 0.0, 0
    for i in range(1, len(path) - 1):
        d = _perp(path[i], path[0], path[-1])
        if d > worst:
            worst, idx = d, i
    if worst <= eps:
        return [path[0], path[-1]]
    return simplify(path[:idx+1], eps)[:-1] + simplify(path[idx:], eps)


def strokes(px, eps=0.9, dot=0.45):
    """Traced, thinned, simplified polylines. Lone pixels become short dashes."""
    out = []
    for p in trace(thin(px)):
        if len(p) == 1:
            (x, y) = p[0]
            out.append([(x - dot, y), (x + dot, y)])
        else:
            out.append(simplify(p, eps))
    return out
