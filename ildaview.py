"""
ildaview.py -- preview .ild files without a projector.

  python3 ildaview.py file.ild                 # contact sheet -> file.png
  python3 ildaview.py file.ild --gif --fps 15  # animation     -> file.gif
  python3 ildaview.py file.ild --frame 7       # single frame
"""
import sys, os, argparse
from PIL import Image, ImageDraw
import ilda


def render(frame, size=400, bg=(6, 6, 10), width=2, glow=True):
    """Draw one frame the way a projector would: lit segments only."""
    img = Image.new('RGB', (size, size), bg)
    dr = ImageDraw.Draw(img)
    s = (size - 10) / 65536.0
    to = lambda x, y: (size / 2 + x * s, size / 2 - y * s)   # +Y is up
    prev = None
    for x, y, z, st, c in frame:
        cur = to(x, y)
        if prev is not None and not (st & ilda.BLANK):
            col = ilda.PALETTE[c & 63]
            if glow:
                dr.line([prev, cur], fill=tuple(v // 3 for v in col), width=width + 3)
            dr.line([prev, cur], fill=col, width=width)
        prev = cur
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('path')
    ap.add_argument('--gif', action='store_true')
    ap.add_argument('--fps', type=float, default=15)
    ap.add_argument('--frame', type=int)
    ap.add_argument('--size', type=int, default=400)
    ap.add_argument('--cols', type=int, default=6)
    ap.add_argument('-o', '--out')
    a = ap.parse_args()

    frames = ilda.read(a.path)
    stem = a.out or os.path.splitext(a.path)[0]
    pts = [len(f) for f in frames]
    print(f"{a.path}: {len(frames)} frames, {sum(pts)} points "
          f"({min(pts)}-{max(pts)} per frame)")

    if a.frame is not None:
        out = stem + f'_f{a.frame}.png'
        render(frames[a.frame], a.size).save(out)
    elif a.gif:
        out = stem + '.gif'
        imgs = [render(f, a.size) for f in frames]
        imgs[0].save(out, save_all=True, append_images=imgs[1:],
                     duration=int(1000 / a.fps), loop=0, optimize=True)
    else:
        out = stem + '.png'
        n = min(len(frames), a.cols * 4)
        idx = [int(i * (len(frames) - 1) / max(1, n - 1)) for i in range(n)]
        cell = a.size // 2
        rows = (n + a.cols - 1) // a.cols
        sheet = Image.new('RGB', (a.cols * cell, rows * cell), (0, 0, 0))
        for k, i in enumerate(idx):
            sheet.paste(render(frames[i], cell, width=1),
                        ((k % a.cols) * cell, (k // a.cols) * cell))
            ImageDraw.Draw(sheet).text(((k % a.cols) * cell + 4,
                                        (k // a.cols) * cell + 4),
                                       str(i), fill=(120, 120, 120))
        sheet.save(out)
    print("wrote", out)


if __name__ == '__main__':
    main()
