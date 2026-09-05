"""
test_roundtrip.py -- proof that ilda.py's model of the format is complete.

Every reference file is parsed and rewritten; the result must be byte-identical.
Any field we failed to understand, or silently normalised, shows up as a
mismatch. Also checks the scanner-safety invariants the reference content obeys.

  python3 test_roundtrip.py
"""
import glob
import hashlib
import math
import os
import sys

import ilda

REF_DIR = 'projector-files'


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


class Skip(Exception):
    """Raised when a check needs reference files that aren't present."""


def _reference_files():
    files = sorted(glob.glob(os.path.join(REF_DIR, '*.ild')))
    if not files:
        raise Skip(f"no reference files in {REF_DIR}/ -- see README")
    return files


def test_roundtrip():
    """Read + rewrite every reference file; require byte-exact output."""
    files = _reference_files()
    tmp = '/tmp/_ilda_roundtrip.ild'
    frames = points = 0
    bad = []
    for p in files:
        show = ilda.read(p)
        ilda.write(tmp, show)                 # defaults preserve everything
        frames += len(show)
        points += sum(len(f) for f in show)
        if sha(p) != sha(tmp):
            orig, new = open(p, 'rb').read(), open(tmp, 'rb').read()
            i = next((k for k in range(min(len(orig), len(new)))
                      if orig[k] != new[k]), min(len(orig), len(new)))
            bad.append(f"{p}: len {len(orig)}/{len(new)}, first diff at byte {i}")
    os.path.exists(tmp) and os.remove(tmp)
    assert not bad, "round trip not byte-exact:\n  " + "\n  ".join(bad)
    print(f"  round trip: {len(files)} files, {frames} frames, "
          f"{points} points -- all byte-identical")


def test_parse_consumes_whole_file():
    """Header record counts must account for every byte, with no slack."""
    for p in _reference_files():
        show = ilda.read(p)
        consumed = sum(32 + len(f) * 8 for f in show) + 32   # + EOF header
        actual = os.path.getsize(p)
        assert consumed == actual, f"{p}: parsed {consumed} of {actual} bytes"
    print("  structure: every file consumed exactly, no trailing bytes")


# aa.ild and ian.ild are the outliers of the collection (2012/2017, written by
# a different tool): they never set the LAST flag, and they are the only files
# with frames that end on a lit point. Everything else is strictly conforming.
NONCONFORMING = {'aa.ild', 'ian.ild'}


def test_reference_invariants():
    """The conventions ilda.FrameBuilder reproduces really do hold."""
    ends_blanked = total = 0
    strays = []
    for p in _reference_files():
        for i, f in enumerate(ilda.read(p)):
            total += 1
            if f.points[-1][3] & ilda.BLANK:
                ends_blanked += 1
            elif os.path.basename(p) not in NONCONFORMING:
                strays.append(f"{p} frame {i}")
    assert not strays, "frames ending lit outside the known outliers: " + ", ".join(strays)
    print(f"  invariant: {ends_blanked}/{total} frames end blanked; the "
          f"{total - ends_blanked} exceptions are all in {sorted(NONCONFORMING)}")


def test_last_flag_outliers():
    """The LAST flag is advisory -- record it as a known-optional field."""
    for p in _reference_files():
        show = ilda.read(p)
        sets_flag = any(f.points[-1][3] & ilda.LAST for f in show)
        expected = os.path.basename(p) not in NONCONFORMING | {'west.ild'}
        assert sets_flag == expected, (
            f"{p}: LAST flag {'set' if sets_flag else 'absent'}, expected otherwise")
    print("  invariant: LAST flag present everywhere except aa/ian/west.ild")


def test_generated_output_is_scanner_safe():
    """Anything we generate must stay inside the measured step/point budgets."""
    import make_demo
    P99_LIT_STEP = 2285        # 99th percentile of lit steps in the reference set
    MAX_PTS = 1867             # largest frame in the reference set
    for name, build in (('cube', make_demo.cube),
                        ('lissajous', make_demo.lissajous),
                        ('starfield', make_demo.starfield),
                        ('timing_test', make_demo.timing_test)):
        worst = 0
        for f in build():
            assert len(f) <= MAX_PTS, f"{name}: {len(f)} points in one frame"
            assert f.points[-1][3] & ilda.BLANK, f"{name}: frame ends lit"
            assert f.points[-1][3] & ilda.LAST, f"{name}: frame missing LAST flag"
            for a, b in zip(f.points, f.points[1:]):
                if not (b[3] & ilda.BLANK):
                    worst = max(worst, math.hypot(b[0] - a[0], b[1] - a[1]))
        assert worst <= P99_LIT_STEP, f"{name}: lit step {worst:.0f} > {P99_LIT_STEP}"
        print(f"  generated: {name} ok (max lit step {worst:.0f})")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items())
             if k.startswith('test_') and callable(v)]
    failed = skipped = 0
    for t in tests:
        print(f"{t.__name__}:")
        try:
            t()
        except Skip as e:
            skipped += 1
            print(f"  SKIP: {e}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL: {e}")
    passed = len(tests) - failed - skipped
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped")
    sys.exit(1 if failed else 0)
