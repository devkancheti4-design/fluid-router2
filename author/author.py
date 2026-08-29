"""AUTHOR THE SIX LANES. THE ENGINE WRITES EVERY EXPRESSION.

What is supplied here, and nothing else:

  six content-bearing bug classes
  which observation bit carries each
  the order they must be handled in

What is authored: every expression below, and every verdict. The engine is
Sphere; it is not in this repository. Without it this script exits cleanly and
the laws in law/law.json still verify with verify/verify.c, which has no
dependencies at all.

A content-bearing bug is one where the code RUNS, RETURNS A NUMBER, and the
NUMBER IS WRONG. No crash, no exception. The failure is in the content, which
is why nothing in a stack trace finds it.
"""
import os, sys, json, time, ast

ENGINE = os.environ.get('SPHERE_ENGINE')
if not ENGINE or not os.path.isdir(ENGINE):
    print('SPHERE_ENGINE is not set. The engine is proprietary and not in this repo.')
    print('The authored laws are in law/law.json and verify with:')
    print('    cc -O2 -o checklaws verify/verify.c && ./checklaws')
    sys.exit(0)
sys.path.insert(0, ENGINE)

import organism_inf.sphere as SP
from organism_inf.sphere import sphere_synthesize
from organism_inf.synth import _OPS, s32, _eval

for _k in range(1, 9):
    _OPS.setdefault('>>%d' % _k, (1, '({a} >> %d)' % _k,
                                  lambda a, _b, k=_k: s32(s32(a) >> k)))
    _OPS.setdefault('<<%d' % _k, (1, '({a} << %d)' % _k,
                                  lambda a, _b, k=_k: s32(s32(a) << k)))

def shield(**kw):
    for f in ('LIN', 'BIT', 'XOR', 'SHF', 'SGN'):
        SP.FAMILIES[f] = tuple(kw.get(f, ())); SP._FAM_CONSTS[f] = ()

def E(e, x):
    """the engine's own evaluator. a hand-rolled one that wraps only the final
    result is the EVALUATOR bug this repo classifies - do not write one."""
    return _eval(e, s32(x))

# ------------------------------------------------------------------ SUPPLY --
#  bit   class         what a body observes                      repair
#   7    NOPROGRESS    the last repair did not move the mask     abandon
#   6    DEGENERATE    the posed targets take one value          widen the domain
#   5    TRUNCATED     exact on the posed domain, wrong on real  span the real domain
#   4    EVALUATOR     grader semantics differ from the machine  grade at machine semantics
#   3    FOLDED        harness scores right and wrong the same   non-cancelling harness
#   2    CIRCULAR      the observation equals the target         drop the feature
BITS = [7, 6, 5, 4, 3, 2]
NAME = ['NOPROGRESS', 'DEGENERATE', 'TRUNCATED', 'EVALUATOR', 'FOLDED', 'CIRCULAR']
WHAT = ['the last repair did not move the mask',
        'the posed targets take one value',
        'exact on the posed domain, wrong on the real one',
        'grader semantics differ from the machine on this data',
        'the harness scores a right and a wrong implementation the same',
        'the posed observation equals the target']
FIX  = ['abandon: not in this taxonomy', 'widen the posed domain',
        'span the real domain', 'grade at machine semantics',
        'non-cancelling harness', 'drop the feature']

MAT = {'BIT': ('&', '|', '~'), 'XOR': ('^',),
       'LIN': ('+', '-', 'neg', '+1', '-1'), 'SGN': ('>>31',),
       'SHF': tuple('>>%d' % k for k in range(1, 9))
              + tuple('<<%d' % k for k in range(1, 7))}
CONSTS = (1,)

print('=' * 96)
print('SIX LANES      supply is the six classes, their bits, and their order')
print('=' * 96)
print('  %-4s %-12s %-38s %5s  %s' % ('slot', 'class', 'authored by the engine', 'ops', 'verdict'))
print('  ' + '-' * 90)

LANES = []; NOTES = []
t0 = time.time()
for i, b in enumerate(BITS):
    rows = [(s32(x), s32((1 << i) if (x >> b) & 1 else 0)) for x in range(256)]
    got = None
    for k in range(1, 6):
        shield(**MAT)
        r = sphere_synthesize(rows, holdout=rows, intent='any', max_size=k,
                              consts=CONSTS, extra_ops=(), on_event=None)
        if r.found and all(E(r.expr, x) == y for x, y in rows):
            got = r; break
    if got is None:
        print('  %-4d %-12s ABSTAINED' % (i, NAME[i])); sys.exit(1)
    LANES.append(got.expr); NOTES.append(got.note)
    ops = sum(isinstance(z, (ast.BinOp, ast.UnaryOp))
              for z in ast.walk(ast.parse(got.expr, mode='eval').body))
    print('  %-4d %-12s %-38s %5d  %s' % (i, NAME[i], got.expr, ops, got.note))
    sys.stdout.flush()
print('  ' + '-' * 90)
print('  [%.2f s]' % (time.time() - t0))
print()

# EMIT, HALT and ADVANCE were authored earlier, for "which token do I write
# next", and are reused here unchanged. This is their sixth domain.
EMIT    = '(x & (-x))'
HALT    = '((x - (x - 1)) + ((-x) >> 31))'
ADVANCE = '(x - (x & (-x)))'

def mask(sig): return sum(E(e, sig) for e in LANES)
def slot(m):
    low = E(EMIT, m); i = 0
    while low >> 1: low >>= 1; i += 1
    return i

wrong = 0
for x in range(256):
    live = [i for i, b in enumerate(BITS) if (x >> b) & 1]
    want = -1 if not live else min(live)
    m = mask(x)
    have = -1 if E(HALT, m) else slot(m)
    if want != have: wrong += 1
print('  dispatch over all 256 observation states: %d wrong' % wrong)

json.dump({'lanes': LANES, 'notes': NOTES, 'bits': BITS, 'names': NAME,
           'what': WHAT, 'fix': FIX,
           'emit': EMIT, 'halt': HALT, 'advance': ADVANCE,
           'states_checked': 256, 'wrong': wrong},
          open(os.path.join(os.path.dirname(__file__), '..', 'law', 'law.json'), 'w'),
          indent=1)
print('  written to law/law.json')
