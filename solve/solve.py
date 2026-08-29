"""SIXTEEN HELD-OUT JOBS. MEASURE, DISPATCH, REPAIR, RE-MEASURE, UNTIL HALT.

The law in law/law.json was authored from six bug classes. Every job here is a
DIFFERENT instance of those classes in a DIFFERENT domain, plus six clean runs,
two multi-bug runs, two jobs of a class the law has NO SLOT for, and two jobs on
a 16-bit domain instead of an 8-bit one. The law has never seen any of them.

NOTHING IS ASSERTED. Every observation bit is MEASURED by running the job:

  DEGENERATE  the posed targets take one value
  TRUNCATED   the authored law is exact on the posed domain and wrong on the real one
  EVALUATOR   the grader's semantics differ from the machine's on this data
  FOLDED      the harness gives a correct and an incorrect implementation the same score
  CIRCULAR    the posed observation equals the target
  NOPROGRESS  the repair the law itself chose did not move the mask

SOLVED is not "named correctly". SOLVED means the run that was wrong became
right: the final law is exact on the REAL domain, under MACHINE semantics, with
a harness that can tell a correct implementation from a wrong one.

The truth column is printed for the reader. The law never sees it.
"""
import os, sys, json, time

HERE = os.path.dirname(os.path.abspath(__file__))
LAW = json.load(open(os.path.join(HERE, '..', 'law', 'law.json')))

ENGINE = os.environ.get('SPHERE_ENGINE')
if not ENGINE or not os.path.isdir(ENGINE):
    print('SPHERE_ENGINE is not set. The engine is proprietary and not in this repo.')
    print('Each job authors a law, so this harness needs it. The dispatch itself,')
    print('and the recorded traces of this exact run, verify with no dependencies:')
    print('    cc -O2 -o checklaws verify/verify.c && ./checklaws')
    sys.exit(0)
sys.path.insert(0, ENGINE)

import signal
import organism_inf.sphere as SP
from organism_inf.sphere import sphere_synthesize
from organism_inf.synth import _OPS, s32, _eval

for _k in (1,2,3,4,5,6,7,8,16,20,24):
    _OPS.setdefault('>>%d' % _k, (1, '({a} >> %d)' % _k,
                                  lambda a, _b, k=_k: s32(s32(a) >> k)))
    _OPS.setdefault('<<%d' % _k, (1, '({a} << %d)' % _k,
                                  lambda a, _b, k=_k: s32(s32(a) << k)))

def shield(**kw):
    for f in ('LIN', 'BIT', 'XOR', 'SHF', 'SGN'):
        SP.FAMILIES[f] = tuple(kw.get(f, ())); SP._FAM_CONSTS[f] = ()
def E(e, x): return _eval(e, s32(x))

class Budget(Exception): pass
signal.signal(signal.SIGALRM, lambda a, b: (_ for _ in ()).throw(Budget()))

def engine(rows, mat, k, consts, seconds):
    """one call under a hard wall-clock kill. a budget checked only BETWEEN
    ladder rungs commits to whatever the current rung costs; measured cost grew
    about 30x per rung, so a 5 s budget once committed to a 1008 s call."""
    shield(**mat)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        r = sphere_synthesize(rows, holdout=rows, intent='any', max_size=k,
                              consts=consts, extra_ops=(), on_event=None)
        return r
    except Budget:      return None
    except MemoryError: return None
    finally:            signal.setitimer(signal.ITIMER_REAL, 0)

# --------------------------------------------------------------- THE LAW ----
LANES, NAME, BITS = LAW['lanes'], LAW['names'], LAW['bits']
EMIT, HALT, ADVANCE = LAW['emit'], LAW['halt'], LAW['advance']
def mask(sig):  return sum(E(e, sig) for e in LANES)
def halted(m):  return E(HALT, m) != 0
def slot(m):
    low = E(EMIT, m); i = 0
    while low >> 1: low >>= 1; i += 1
    return i

# --------------------------------------------------------------- THE BODY ---
FULL = {'BIT': ('&', '|', '~'), 'XOR': ('^',),
        'LIN': ('+', '-', 'neg', '+1', '-1'), 'SGN': ('>>31',),
        'SHF': tuple('>>%d' % k for k in (1,2,3,4,5,6,7,8,16,24))
               + tuple('<<%d' % k for k in (1,2,3,4,5,6,7,8,16,24))}
LEAN = {'BIT': ('&',), 'XOR': (), 'LIN': ('-',), 'SGN': (), 'SHF': ('>>1',)}
CS = (0, 1, 2, 3, 7, 15, 85, 127, 128, 255, 4369, 21845, 32767, 65535)

def author(rows, mat):
    for k in range(1, 5):
        r = engine(rows, mat, k, CS, 10.0)
        if r is None: return None
        if r.found and all(E(r.expr, x) == y for x, y in rows): return r.expr
    return None

def score(cand, ref, dom, method):
    """does this harness distinguish a correct implementation from a wrong one?"""
    a = 0
    for i, x in enumerate(dom):
        u, v = cand(x) & 255, ref(x) & 255
        if method == 'naive':      a ^= u; a ^= v          # cancels on a permutation
        else: a = (a * 31 + (i + 1) * u - (i + 1) * v) & 0xffffffff
    return a

def measure(J, prev):
    posed, real = J['posed'], J['real']
    grader, method = J['grader'], J['timing']
    tgt = (lambda x: J['ref'](x)) if grader == 'python' else (lambda x: s32(J['ref'](x)))
    rows = [(s32(x), s32(tgt(x))) for x in posed]
    sig = 0
    if len(set(y for _, y in rows)) <= 1:                     sig |= 1 << 6
    if all(x == y for x, y in rows):                          sig |= 1 << 2
    if grader == 'python' and any(J['ref'](x) != s32(J['ref'](x)) for x in posed):
        sig |= 1 << 4
    if J['wrong'] is not None and \
       score(J['ref'], J['ref'], real, method) == \
       score(J['wrong'], J['ref'], real, method):             sig |= 1 << 3
    e = author(rows, J['mat'])
    if e is not None:
        if all(E(e, x) == y for x, y in rows) and \
           any(E(e, x) != s32(J['ref'](x)) for x in real):    sig |= 1 << 5
    if prev is not None and (sig & 0x7c) == (prev & 0x7c) and (sig & 0x7c):
        sig |= 1 << 7
    return sig, e

REPAIR = [
 lambda J: J.update(abandon=True),
 lambda J: J.update(posed=list(J['real'])[:len(J['posed']) * 2] or list(J['real'])),
 lambda J: J.update(posed=list(J['real'])),
 lambda J: J.update(grader='machine'),
 lambda J: J.update(timing='blocked'),
 lambda J: J.update(dead=True),
]

# ------------------------------------------------------------- THE JOBS -----
def band(x):   return 1 if x >= 128 else 0
def over(x):   return x << 24                      # overflows int32 for x >= 128
def scr(x):    return (x ^ 85) & 255
def scrw(x):   return ((x + 1) ^ 85) & 255         # a permutation of scr's outputs
def nib(x):    return (x >> 4) & 1
def popcnt(x): return bin(x & 255).count('1')
_st = {'n': 0}
def flaky(x):
    _st['n'] += 1
    return (x & 1) ^ (_st['n'] & 1)                # same input, different answer
W = list(range(0, 65536, 257))                     # 256 spanning rows of a 16-bit domain
def w_ok(x):    return (x >> 8) & 255
def w_trunc(x): return 1 if x >= 32768 else 0

def J(name, ref, posed, real, mat=FULL, grader='machine', timing='blocked',
      wrong=None, truth=''):
    return dict(name=name, ref=ref, posed=posed, real=real, mat=mat, grader=grader,
                timing=timing, wrong=wrong, truth=truth, dead=False, abandon=False)

R = list(range(256))
JOBS = [
 J('parity, posed even',        lambda x: x & 1, list(range(0,256,2)), R, truth='DEGENERATE'),
 J('half-flag, posed 0..127',   band, list(range(128)), R, truth='DEGENERATE+TRUNCATED'),
 J('nibble bit, posed 0..31',   nib, list(range(32)), R, truth='TRUNCATED'),
 J('x<<24 graded in python',    over, R, R, grader='python', truth='EVALUATOR'),
 J('scramble, xor harness',     scr, R, R, timing='naive', wrong=scrw, truth='FOLDED'),
 J('predict x from x',          lambda x: x, R, R, truth='CIRCULAR'),
 J('x<<24, posed 0..127',       over, list(range(128)), R, grader='python', truth='CLEAN'),
 J('nibble 0..31 + xor harness', nib, list(range(32)), R, timing='naive',
   wrong=lambda x: 1 - nib(x), truth='TRUNCATED+FOLDED'),
 J('lowest set bit, clean',     lambda x: x & (-x) & 255, R, R, truth='CLEAN'),
 J('complement, clean',         lambda x: x ^ 255, R, R, truth='CLEAN'),
 J('bit 3, clean',              lambda x: (x >> 3) & 1, R, R, truth='CLEAN'),
 J('add one, clean',            lambda x: (x + 1) & 255, R, R, truth='CLEAN'),
 J('flaky reference',           flaky, R, R, truth='NO SLOT: nondeterministic'),
 J('starved material',          popcnt, R, R, mat=LEAN, truth='NO SLOT: lean material'),
 J('16-bit, clean',             w_ok, W, W, truth='CLEAN'),
 J('16-bit, truncated',         w_trunc, [x for x in W if x < 32768], W,
   truth='DEGENERATE+TRUNCATED'),
]

print('=' * 100)
print('SIXTEEN HELD-OUT JOBS      the law never sees the truth column')
print('=' * 100)
print('  %-28s %-24s %-28s %s' % ('job', 'truth', 'what the law did', 'outcome'))
print('  ' + '-' * 96)
T0 = time.time(); solved = cried = abandoned = dead = 0
TRACES = []
for j in JOBS:
    _st['n'] = 0
    sig, expr = measure(j, None); m = mask(sig)
    steps = []; sigs = [sig]
    for _ in range(8):
        if halted(m): break
        s = slot(m); steps.append(NAME[s]); prev = sig
        REPAIR[s](j)
        if j['dead'] or j['abandon']: break
        sig, expr = measure(j, prev); m = mask(sig); sigs.append(sig)
    ok = False
    if not j['dead'] and not j['abandon'] and halted(m) and expr is not None:
        bad = sum(1 for x in j['real'] if E(expr, x) != s32(j['ref'](x)))
        blind = j['wrong'] is not None and \
                score(j['ref'], j['ref'], j['real'], j['timing']) == \
                score(j['wrong'], j['ref'], j['real'], j['timing'])
        ok = (bad == 0 and not blind)
    out = ('SOLVED' if ok else 'ABANDONED' if j['abandon'] else
           'DEAD' if j['dead'] else 'not solved')
    solved += ok; abandoned += j['abandon']; dead += j['dead']
    if j['truth'] == 'CLEAN' and steps: cried += 1
    print('  %-28s %-24s %-28s %s' % (j['name'][:28], j['truth'][:24],
          (' -> '.join(steps) or 'CLEAN, no repair')[:28], out))
    sys.stdout.flush()
    TRACES.append({'job': j['name'], 'truth': j['truth'], 'sigs': sigs,
                   'steps': steps, 'outcome': out, 'law': expr})
print('  ' + '-' * 96)
print('  solved %d of %d    abandoned %d    unsalvageable %d    false alarms on clean %d   [%.1f s]'
      % (solved, len(JOBS), abandoned, dead, cried, time.time() - T0))
json.dump(TRACES, open(os.path.join(HERE, '..', 'traces', 'traces.json'), 'w'), indent=1)
print('  observation traces written to traces/traces.json')
